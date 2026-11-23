# Ep11 (`v8_ep11_open_label_placebo_pain`) — `R85` / `R86` + `Canonical v1+v1.1` Completion Report

- **Title**: *Why Openly Fake Pills Still Cut Pain*
- **Primary DOI**: `10.1371/journal.pone.0015591` (Kaptchuk et al., *PLoS ONE* 2010 — Harvard Medical School, 80 IBS adults: `59%` open placebo vs `35%` no-pill control)
- **Secondary / Mechanism DOIs**: `10.1097/j.pain.0000000000000700` (Carvalho et al., *PAIN* 2016 — 97 chronic low-back pain adults, `~30%` usual & max pain drop), `10.1038/s41467-020-17654-y` (Guevarra et al., *Nature Communications* 2020)
- **Root Master MP4**: [`final_shorts_v8_ep11_open_label_placebo_pain_r85.mp4`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/final_shorts_v8_ep11_open_label_placebo_pain_r85.mp4)
  - Size: `71,503,683 bytes` (`1080x1920 @ 30.0fps`, `79.97s`, `24` unique cuts, `max_clip_reuse: 1`)
  - **`final_mp4_sha256`**: `35f1523f798b51dd189d47e37826f8c81ab9251b399d6abc383a101e121083df`
  - **`edl_sha256`**: `c2de9d1285df8ee82313109a1f72c5e1fa649b2f963d90d06677c55e74d4bacc`
- **Multi-Platform Bundle**: `06_publish/multi_platform_bundle/` freshly regenerated (`video_clean.mp4` byte-identical `71,503,683 bytes`, `6` `4:5` carousel slides, `cover_9x16.png` safe-zone PASS, `youtube_quiz_post.json`)
- **Superseded Archive (Zero Deletion)**: `/home/canadaofbin/gdrive/Kyubin_Yun_Workspace/00_Old_Files_Archive/20261118_R82_R84_Superseded/final_shorts_v8_ep11_open_label_placebo_pain_r82.mp4`

---

## 1. Key Pipeline, Scientific & Visual Upgrades Applied
1. **Global Pipeline Fix (`Pipeline-First`)**: Fixed outdoor `spatial_3d_arrow_diorama` campus lawns falsely tripping `neon_green_fluorescent_spill` in [`pipeline/flow_diorama_sharded_worker.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_diorama_sharded_worker.py#L951-L955) (`v8_green_cap = 0.48` for exterior arrow dioramas while keeping interior/brain strictly at `0.08`), locked with a regression test in [`tests/test_r80_spatial_arrow_diorama.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_r80_spatial_arrow_diorama.py) (`pytest`: `5 passed`).
2. **100% Google Flow Native `Omni 1.2 / 1.1 Flash` (`0` Veo Lite downgrades, `0` Blender screen renders)**:
   - Replaced all `8` legacy Blender brain clips (`C09, C10, C11, C12, C17, C18, C21, C22`) + `7` narrative/diagram clips (`C01, C03, C04, C05, C14, C19, C24`) using `22` SHA-256 locked `Canonical v1+v1.1` assets (including `H03_pulled_apart_empty_clear_capsule`, `A17_brain_spinal_body_descending_xray`, `A19_anterior_cingulate_amygdala_limbic_cutaway`, `I01`/`I02` chart backdrops), preserving `9` untouched clean cuts (`C02, C06, C07, C08, C13, C15, C16, C20, C23`).
   - Proactively caught & source-fixed `6` raw video defects before Gate 2 (`C01` soft bokeh `plaque=1`, `C05` hands-only empty capsule `Start+End` lock, `C09` intact Mode 1 head `Start+End` lock, `C11` organic pullback `Start+End` lock, `C19` uninhabited cream wall behind dark translucent `30%` `Usual & Max Back Pain Drop` Study gauge, `C22` continuous `orbital_3d_arc_sweep` `0` frozen frames) -> achieved **Gate 2 Round 1 `24 / 24` (`0` REJECT)**!!
3. **Frame-0 (`START`) Tracked `R81` Callouts**: Exact measured anatomical centroids locked on all `7` brain callouts (`C09, C10, C11, C17, C18, C21, C22` — with `C22` `Prefrontal Steady` gold left / `Pain Alarm Dimmed` slate right swapped for zero line crossing!).

---

## 2. Reproducible CLI QA & `@Research` Gate Receipts (`100% PASS`)
| Gate / Command | Result | Key Metrics / Receipt Path |
|---|---|---|
| `main.py prompt-gate --dir ...v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | `passed: true, issues: [], warnings: [], contract_compiled: true` |
| `main.py ref-qa --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | **`100.0/100`**, `36/36` (`[EP11_GATE1_SIGNED]` + `[EP11_GATE1_DELTA_SIGNED]`), `canonical_assets_provenance_audit: passed=True (22 locked v1+v1_1 files)`, `regenerate_image_ids: []` |
| `main.py episode-qa --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | **`95.0/100`**, **`12/12` gates PASS**, `pre_flow_issues: []` (`DQ_R85_ep31_brain_fidelity` `8/8`, `DQ_Smooth` PASS, `DQ8` `9/9` clean vinyl crops) |
| `main.py prosody-qa --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | **`11/11` gates PASS** (`79.97s`) |
| `main.py posthoc-qa --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | `passed: true`, `cv_passed: true`, **`24/24`**, **`mean_clarity_score: 96.8/100`** (`min: 95.2/100`), `weak_cut_count: 0`, `[EP11_GATE2_SIGNED]` Round 1 `0` REJECT |
| `main.py autopsy --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | **`100.0/100`**, `status: PASS`, **`defect_count: 0`**, `prescriptions: []`, `advisory_warnings: []` |
| `06_publish/thumbnail_qa_report.json` | **PASS** | `R65 v4` 50/50 split (`NO PILL: PAIN STAYS` vs `FAKE PILL: PAIN DROPPED?!`) |
| `main.py verify --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | **`295 / 295` artifacts `100% INTACT`** |
| `main.py multi-bundle --project v8_ep11_open_label_placebo_pain` | **PASS (`RC=0`)** | `video_clean.mp4` (`71,503,683 bytes`), `6` carousel slides, `cover_9x16.png` safe-zone PASS |

### Visual Proof Sheets
- Gate 2 Viewer Sheets `01–04`: [`ep11_gate2_viewer_sheet_01.jpg`](./ep11_gate2_viewer_sheet_01.jpg), [`02`](./ep11_gate2_viewer_sheet_02.jpg), [`03`](./ep11_gate2_viewer_sheet_03.jpg), [`04`](./ep11_gate2_viewer_sheet_04.jpg)
- `DQ8` `9/9` Clean Vinyl Face Crops: [`ep11_gate2_dq8_suspect_sheet.jpg`](./ep11_gate2_dq8_suspect_sheet.jpg)
- `@Research` Independent 5-Point Verification Board: [`ep11_gate2_final_proof_board.jpg`](../03_Research/ep11_gate2_final_proof_board.jpg)
