# Canonical Asset Library `v1.1` Lock & Unified `85`-Slot Pipeline Integration Report

- **Status**: **`APPROVED & SHA-256 LOCKED`** (`2026-11-18T22:43:24Z`)
- **Unified Active Library**: **`85` Approved Canonical Slots** (`v1` `42` slots untouched + `v1.1` `43` slots newly locked)
- **Live Adoption**: Immediately active for Phase 3 (`Ep10`, `Ep11`, `Ep12`) and all subsequent Shorts episodes via `version="auto"` (`v1+v1_1`).

## 1. Cryptographic Manifest Locks (`R83-7` Reproducible Evidence)
| Library | Manifest Path | Status | Slots | SHA-256 |
|---|---|---|---|---|
| **`Canonical v1` (Parent — Untouched)** | [v1/manifest.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1/manifest.json) | `approved` | `42 / 42` | `c9d2e271b8134363605890c289512ebd304ba09529260265f45bcbbc844a3892` |
| **`Canonical v1.1` (Expansion — Locked)** | [v1_1/manifest.json](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/BCI_Shorts_Channel/canonical_assets/v1_1/manifest.json) | `approved` (`sha256_locked: true`) | `43 / 43` | `ee9a179a0cad8c23246aac3b8b1459d1a2c2182a83991a5c78c14b75bcc883c2` |

### Key Locked Integrity Checks
- **`7` `@Research` Rank-1 Promotions Locked**:
  - `A16_eyes_optic_nerve_to_v1_pathway` → `cand_03.png` (`d033552c440ecb39...`)
  - `A17_brain_spinal_body_descending_xray` → `cand_02.png` (`d431c6d42ffc5078...`)
  - `E14_night_bedroom_staged` → `cand_02.png` (`40cf3e458b226ec1...`)
  - `E16_urban_street_sidewalk_staged` → `cand_02.png` (`f3026c8a58fc6c38...`)
  - `H01_padlocked_acrylic_plaster_brain_case` → `cand_02.png` (`a82c5d90fff98cff...`)
  - `H04_physical_red_x_over_simple_diagram_card` → `cand_03.png` (`d366af7c57c3f29e...`)
  - `I03_callout_safezone_brain_headroom_frame` → `cand_02.png` (`820c3bb73aa77da8...`)
- **`F04` CEO-Directed Pair 1 Locked (`sponge -> thalamus + CSF`)**:
  - Start (`cand_01_start.png`): `0d36df142cac2aa4515550c46cd2b8969c23bda703e7e010aee5f019e3ea171a`
  - End (`cand_01_end.png`): `7fc229c9af81a822d6d3b8411b2042486589a98b0e6940193b8d1610c2e0ffb6`
- **`F03a -> F03b` Exact Byte-Level Daisy-Chain Verified**:
  - `F03a_whole_brain_to_sulcal_vessel_macro` `end` == `F03b_sulcal_vessel_macro_to_1p_tract_canyon` `start` == `f9d7c46cdc1ba98c485444becc6dea236ab0b16a16ac2cb0a9b49f1d99c10bc5`
- **`23` `[EXCL]` Outlier Candidates Hard-Blocked**: `pipeline/canonical_assets.py` enforces hard rejection if any excluded candidate filename is requested or staged.

## 2. Pipeline Code Integration & Unit Test Verification
- Modified / Added Files:
  - [pipeline/config.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/config.py) (`CANONICAL_ASSETS_VERSIONS`, `REF_IMAGE_SOURCE_CANONICAL_V1_1`, `CANONICAL_REF_IMAGE_SOURCES`)
  - [pipeline/canonical_assets.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/canonical_assets.py) (unified `85`-slot `v1 + v1_1` auto-resolver, `start`/`end` pair staging via `resolve_canonical_transition_pair` & `stage_canonical_transition_pair_to_project`, `[EXCL]` hard-block, mixed `v1+v1_1` provenance SHA-256 verification)
  - [pipeline/porcelain_anchor_pack.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py), [pipeline/source_reenactment.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py), [pipeline/reference_image_qa.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py)
  - [pipeline/flow_ingredients.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_ingredients.py) (live compatibility upgrade for Google Flow's new `https://flow.google.com/asb/...=s512-rw` -> `=s0` full-resolution gallery URL migration)
  - [tests/test_canonical_assets_v1_1.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/tests/test_canonical_assets_v1_1.py)
- Test Command & Result:
  - `PYTHONPATH=. /home/canadaofbin/hermes-venv/bin/pytest tests/test_canonical_assets_v1_1.py tests/test_r85_r86_qa_honesty_and_semantic_beat.py tests/test_credit_safe_pipeline.py -q`
  - Result: **`27 passed in 46.78s`** (`exit 0`).
