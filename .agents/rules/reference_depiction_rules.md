---
trigger: model_decision
description: "Load when generating, staging, or auditing 9:16 reference image packs, R85 Ep #31 brain keyframes, Wikimedia/MNI152 structural guides, Semantic ID 5-Guard, or Gate 1 review (R44-M, R66, R67, R72-R, R85)."
---

# Reference Pack, `99` Canonical Slots & `Semantic ID` 5-Guard (`R66–R67`, `R72-R`, `R85`, `R88`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Refs: [real_world_drone_refs_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/real_world_drone_refs_rules.md) | Archive: [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## 1. `9:16` Keyframe Pack (`main.py refs` / `porcelain-refs`)
- `0-credit` Flow `Image` (`Nano Banana 2.1`): `x1` 1st-pass (`FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT=1`), `x2` CV retry / `--refs <id> --force` Gate 1 regen (`FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT=2`); fail-fast `0`-retry on `"unusual activity"`:
  - **World / Drone / `R80` Anchors**: `expressive_25d_v8` sheets + sanitized `/tmp/aab_real_refs/<project_id>/` guides (`Track B` `R72-R` / `Track A` `R67`). Closeups & `R80` arrows emit `Start+End`.
  - **`R85` Ep #31 Brain (`build_r85_31_brain_keyframe_spec`)**: `31_O2CmlKOk` plates (`ep31_orig_mode1_head_9x16.png`, `ep31_orig_mode2_lateral_9x16.png`, `ep31_orig_mode2_dorsal_9x16.png`, `ep31_orig_mode2_vessel_macro_9x16.png`) + `NEUROANATOMY_CUTAWAY_MAP` Wikimedia + off-screen `/tmp/aab_real_refs/<project_id>/guides/` MNI152 (`0%` direct exposure).

## 2. Provenance & `ref-qa` (`main.py ref-qa`, `Q1–Q11`)
- **Tier-1 Blockers**: `real_world_refs_manifest.json` open license (`PD/CC0/CC-BY/CC-BY-SA`, `source_url`, blocklist); `reference_provenance.json` on `03_visuals/reference_images/*.png`; `Q1` (`9:16`), `Q4` (`0` flesh leak), `Q7` (`0` burned text), `Q11` (`Independent Visual Reviewer (Gate 1/2)` Gate 1 `reference_semantic_review.json`; `auto_cv_verified_v7` banned).
- **Tier-2 Advisories**: `Q2, Q3, Q5, Q6, Q8/Q9, Q10`.

## 3. `84` Active + `15` Retired `R88` Slots (`99` Locked) & `Semantic ID` 5-Guard
- **Zero-Deletion Inventory**: `27` active `v1` (+ `15` retired `B01–B15` kept on disk: `status="retired_r88_cartoon_face"`, `selectable_for_new_episodes=false`) + `43` `v1_1` + `14` `v1_2` (`status="locked"`, `J04` deferred) = **`84` active selectable** (`99` SHA-256 locked + `1` deferred). `v8_ep13+` bans `B01–B15`; `select_canonical_character_slot` routes to faceless slots (`E06_laboratory_staged`, `E07_mri_suite_staged`, `E10_kitchen_staged`, `A01_mode1_translucent_head_lateral`).
- **`Semantic ID` 5-Guard**:
  1. **`0%` Raw Broadcast (`Ingredients`-Only)**: Canonical PNGs condition bespoke keyframes only — never output raw PNGs as video clips.
  2. **3 Deltas/Ep**: Swap `R72-R` lab (`120ft` drone), study prop, and DOI `study` Data Stamp each episode.
  3. **Hook Rotation**: Rotate `J01–J06` & `R87_OPENING_MODES` (never repeat back-to-back).
  4. **`R88` Faceless Cast & Frame-0 Lock**: Ban `B01–B15` & cartoon faces on `v8_ep13+`; use `K03`/`K05`/hands-only/silhouette `kf_r88_*` start frames (`B01–B04` also banned as direct start frames on `Ep #01–#12`).
  5. **Brain Legend & 6-Scale Arc**: Lock 1 color legend, rotate 6 scales, apply Act lighting (`scene_depiction_rules.md`).
