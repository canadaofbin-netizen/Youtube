# Ep12 (`v8_ep12_doorway_effect_memory`) — `R85` / `R86` + `Canonical v1+v1.1` Completion Report (**Phase 3 `4 / 4` Complete!**)

- **Title**: *How Walking Through Doorways Wipes Your Memory*
- **Primary DOI**: `10.1080/17470218.2011.571267` (Radvansky, Krawietz & Tamplin, *QJEP* 2011 — University of Notre Dame: Exp. 1/2 `23%` same-room walk vs `28%` doorway error rate; Exp. 3 `11%` stay room → `14%` 1 doorway → `16%` return room)
- **Secondary / Mechanism DOIs**: `10.1016/j.neuron.2017.06.041` (Baldassano et al., *Neuron* 2017), `10.1038/s41593-022-01020-w` (Zheng et al., *Nature Neuroscience* 2022 — human hippocampal boundary cells)
- **Root Master MP4**: [`final_shorts_v8_ep12_doorway_effect_memory_r85.mp4`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep12_doorway_effect_memory_r85.mp4)
  - Size: `70,160,603 bytes` (`1080x1920 @ 30.0fps`, `77.133s`, `23` unique cuts, `max_clip_reuse: 1`, `avg_cut_duration_sec: 3.354s`)
  - **`final_mp4_sha256`**: `6ff1f99faadb9650cd4676b6287600f58ae662d9e30daf9e0910e24f5cedc9c7`
  - **`edl_sha256`**: `17c20f6f9d2f7576f34a7780881118f6163144045348de152986a43fe378c699`
- **Multi-Platform Bundle**: `06_publish/multi_platform_bundle/` freshly regenerated (`video_clean.mp4` byte-identical `70,160,603 bytes`, `6` `4:5` carousel slides safe-zone PASS, `cover_9x16.png` safe-zone PASS, `youtube_quiz_post.json`)
- **Superseded Archive (Zero Deletion)**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/00_Old_Files_Archive/20261118_R82_R84_Superseded/final_shorts_v8_ep12_doorway_effect_memory_r82.mp4`

---

## 1. Global Pipeline Upgrades (`Pipeline-First`, Zero Regressions)
1. **Top-Down Doorway Partition Wall Geometry (`R80` `spatial_3d_arrow_diorama`)**:
   - Updated [`pipeline/flow_diorama_sharded_worker.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L936-L942) and [`pipeline/dynamic_episode_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L2082-L2089) so 90° top-down architectural floorplans with open central doorways (`seam ~ 0.62–0.82`) use `hsplit_cap = 0.92` on `spatial_3d_arrow_diorama` while keeping full edge-to-edge split screens (`>= 0.92`) and all other grammars (`>= 0.72`) strictly blocked.
   - Regression test added in [`tests/test_r80_spatial_arrow_diorama.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r80_spatial_arrow_diorama.py) (`6 passed`).
2. **Respect Explicit `single_start_frame_lock: True` (`Omni 1.2 Flash`)**:
   - Updated [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py#L2331-L2336) so `is_drift_vulnerable_r85` never overrides an explicit `single_start_frame_lock: True` back into degenerate `Start==End` (`Omni 1.1 Flash`). Verified `tests/test_flow_prompt_builder.py` (`9 passed`).
3. **`Canonical v1.1 I02` Dark-Headroom Study Chart Auto-Compact & Scrim Fix (`0px` Brain Overlap)**:
   - Updated [`pipeline/data_stamp_overlay.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/data_stamp_overlay.py), [`pipeline/charts/axes.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/axes.py), and [`pipeline/charts/compose.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/charts/compose.py):
     - Added `_measure_upper_chart_headroom_luma` (skips redundant `Y=0..66%` blur+dim scrim when upper headroom is already `#040711` dark studio void `< 24.0`, keeping the lower 3D brain razor-sharp & full brightness with zero brightness pop).
     - Added `_detect_dark_void_lower_subject_top_y` + `max_y_frac` compact layout so ALL Study charts (`line`, `bar_compare`, etc.) automatically compact strictly above the detected lower brain crown with `>= 46 px` pure `#040711` breathing room (`Ep12` verified: `C11` `+80 px`, `C21` `+48 px`, `0 px` overlap!).
   - Regression tests added in [`tests/test_data_stamp_validation.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_data_stamp_validation.py) + [`tests/test_chart_engine.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_chart_engine.py) (`12 passed`).
4. **`R85` `expressive_xray_brain` ROI Parity in `DQ7` & `posthoc-qa`**:
   - Synced legacy pre-`R85` `brain_simulator_3d`-only ROI & luma checks to include `expressive_xray_brain` in [`pipeline/dynamic_episode_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/dynamic_episode_qa.py#L1918) and [`pipeline/posthoc_semantic_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/posthoc_semantic_qa.py#L1785) (bumped disk cache key to `v8_r85_v4_xray_roi`, synced lines `1930` & `2221`). Verified `tests/test_dynamic_episode_qa.py` + `tests/test_posthoc_qa_and_knowledge_hub.py` (`12 passed`).
5. **100% Paid Google Flow `Omni 1.2 Flash` / `Omni 1.1 Flash` Production (`0` Veo Lite, `0` Blender)**:
   - Replaced all `8` legacy Blender brain clips (`C08, C09, C10, C11, C16, C17, C20, C21`) + `6` narrative/diagram clips (`C03, C05, C12, C15, C19, C23`) using `21` SHA-256 locked `Canonical v1+v1.1` assets, preserving `9` untouched clean cuts (`C01, C02, C04, C06, C07, C13, C14, C18, C22`).
   - Proactively source-fixed `C09` (cortex text leak -> `v2` spotless) and `C17` (dark canyon -> `v2` bright `luma 165–183`), locked all `6` Frame-0 (`START`) tracked `R81` callouts (`C08, C09, C10, C16 [stacked_vstack=True, silver-slate right pointer], C17, C20`), and verified `C15` crimson 3D bar halting cleanly right at the oak doorway threshold with `100%` empty upper room (`97.4/100`).

---

## 2. Reproducible CLI QA & `@Research` Gate Receipts (`100% PASS`)
| Gate / Command | Result | Key Metrics / Receipt Path |
|---|---|---|
| `main.py prompt-gate --dir ...v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | `passed: true, issues: [], warnings: [], contract_compiled: true` |
| `main.py ref-qa --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | **`100.0/100`**, `34/34` (`[EP12_GATE1_SIGNED]`), `canonical_assets_provenance_audit: passed=True (21 locked v1+v1_1 files)`, `video_continuity_checked: true`, `regenerate_image_ids: []` |
| `main.py episode-qa --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | **`95.0/100`**, **`12/12` gates PASS**, `pre_flow_issues: []` (`DQ3` PASS, `DQ6` `max_clip_reuse=1`, `DQ7` `freeze_cuts=[]`, `DQ8` `high_suspect_cuts=[]`, `9/9` clean vinyl crops) |
| `main.py prosody-qa --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | **`11/11` gates PASS** (`77.133s`, `-14.3 LUFS`, `-1.6 dBTP`, `f0_span=14.829 st`, `lift_vs_drop=3.533 st`, `ASR >= 0.978`) |
| `main.py posthoc-qa --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | `passed: true`, `cv_passed: true`, **`23/23`**, **`mean_clarity_score: 96.9/100`** (`min: 94.4/100`), `weak_cut_count: 0`, `[EP12_GATE2_SIGNED]` (`valid: true, issues: [], rejected_cuts: []`) |
| `main.py autopsy --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | **`100.0/100`**, `status: PASS`, **`defect_count: 0`**, `prescriptions: []`, `advisory_warnings: []` |
| `06_publish/thumbnail_qa_report.json` | **PASS** | `R65 v4` 50/50 split (`SAME ROOM` vs `MIND WIPED?!`) |
| `main.py verify --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | **`267 / 267` artifacts `100% INTACT`** |
| `main.py multi-bundle --project v8_ep12_doorway_effect_memory` | **PASS (`RC=0`)** | `video_clean.mp4` (`70,160,603 bytes`), `6` carousel slides safe-zone PASS, `cover_9x16.png` safe-zone PASS |

### Visual Proof Sheets
- Gate 2 Round 2 Viewer Sheets `01–04`: [`ep12_gate2_r2_viewer_sheet_01.jpg`](./ep12_gate2_r2_viewer_sheet_01.jpg), [`02`](./ep12_gate2_r2_viewer_sheet_02.jpg), [`03`](./ep12_gate2_r2_viewer_sheet_03.jpg), [`04`](./ep12_gate2_r2_viewer_sheet_04.jpg)
- `C11` & `C21` `0px`-Overlap 5-Point Compact Chart Proof Board: [`ep12_gate2_r2_c11_c21_compact_charts_proof.jpg`](./ep12_gate2_r2_c11_c21_compact_charts_proof.jpg)
- `DQ8` `9/9` Clean Vinyl Face Crops: [`ep12_gate2_dq8_suspect_sheet.jpg`](./ep12_gate2_dq8_suspect_sheet.jpg)
- `@Research` Independent `1080x1920` Proof Board: [`ep12_gate2_final_c11_c21_zero_overlap_proof.jpg`](../03_Research/ep12_gate2_final_c11_c21_zero_overlap_proof.jpg)
