---
trigger: model_decision
description: "Load when auditing, rendering, or QA-checking R89 Split-Sync or Viewfinder archival and supplementary experiment video clips (R89)."
---

# `R89` Archival & Supplementary Experiment Video (`Split-Sync` & `Viewfinder`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/archival_video_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/archival_video_builder.py)

## 1. Zero-Fair-Use-Gambling 3-Tier Clearance (`audit_archival_video_eligibility`)
- **Tier 1 (`direct_insert_pd_cc0`)**: Verified `17 U.S.C. § 105` **intramural** federal agency recordings (`NIH intramural`, `NIMH`, `DARPA`, `NASA`, `NARA` — NEVER NIH/DARPA university grant clips), `CC0 1.0`, or verified `<= 1930` silent PD films.
- **Tier 2 (`direct_insert_cc_by`)**: Peer-reviewed `CC BY 4.0`/`3.0` supplementary movies (`PLOS Biology/ONE`, `eLife`, verified `PMC OA Subset` `<license>`, `Nature Comm`, or per-article-verified `PNAS`/`Science Advances`). Automatically reject `"excluded from"`, `"third party"`, `"permission"`, `"all rights reserved"` in caption/Rights notes (`R89_CAPTION_EXCLUSION_PATTERNS`).
- **Tier 3 Permanent Direct-Video Ban (`R67` Porcelain Reenactment)**: **All** Fair Use (`§ 107`) claims, `CC BY-NC`, `CC BY-ND`, `CC BY-NC-ND`, `CC BY-SA`, `Author Manuscript` / `"Free in PMC"`, user-tagged post-1930 `archive.org` `"Public Domain"`, TV/YouTube reuploads, living clinical patients/minors (`< 18`), and classic restricted clips (`Milgram`, `Gazzaniga "Joe"`, `Marshmallow`, `Strange Situation`, `Skinner Foundation / Harvard Film Archive`, `H.M.`, `Harlow`).

## 2. Hard Temporal, Audio, `0-Face` & UI Geometry Locks
- **Quota & Timing**: `2.0–4.0s` each (`R89_VIDEO_DURATION_RANGE`); combined **`R88-A + R89` `<= 2` cuts** and **`<= 10%` episode share** (`R89_COMBINED_ARCHIVAL_MAX_CUTS`, `R89_COMBINED_ARCHIVAL_MAX_DURATION_SHARE`); strictly **`Cut >= 2` & `start >= 2.20s`** (`0` overlap with Cut 1 `118pt HookTitle`).
- **Audio & Flow Provenance**: `100%` muted (`-an`, `audio_stream_count == 0`); `flow_upload_count == 0` (`Gear 4 PyAV` only); SHA-256 locked in `03_visuals/archival_videos_manifest.json`.
- **Privacy & Motion (`DQ7` / `DQ8`)**: Optional `crop_box` to isolate `0-Face` monitors/cursors/hands before scan; **`5.0 fps` multi-frame `YuNet < 0.42`**; `min_frame_diff >= 0.30`.
- **UI-Safe Viewports (`R89_SAFE_OUTER_BOX = (80, 288, 908, 1218)`)**:
  - **Mode 1 (`split_sync`)**: Top rounded video `(80, 288, 908, 728)` + `CC BY 4.0 § 3(a)` cropped/muted sync pill `(80, 735, 908, 767)` + synced `Ep #31` 3D brain stage `(80, 774, 908, 1218)`.
  - **Mode 2 (`viewfinder_locator`)**: Rounded dark-navy viewfinder `(80, 288, 908, 1058)` + `200×200` `A01` porcelain head locator badge `(94, 948, 294, 1148)` + credit pill `(312, 1084, 896, 1138)`.
- **Publish Attribution (`pipeline/publish.py`)**: Emit `Video credit: Adapted from <Lead Author> et al., <Journal> (<Year>), <Supp. Movie ID>, CC BY 4.0 (<URI>) — cropped & muted (<Article URL>).` ONLY for `direct_insert_cc_by` (`0` URLs for `PD/CC0`).
