---
trigger: model_decision
description: "Load when running or triaging dynamic_episode_qa (DQ1-DQ13, DQ8 suspect crops), prosody-qa (P7/P9), 4x3 intra-cut flicker checks, or posthoc-qa Gate 2 viewer sheets (R62-R64)."
---

# Episode QA Triage, Prosody & Gate 2 Review (`R62–R64`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Master QA: [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md) | Retired: [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## R62 — Dynamic Episode QA (`pipeline/episode_qa.py`) — 3-Tier Split
- **[Tier-1 Hard Blockers]**:
  - `DQ3_anatomy_to_brain_sync`, `DQ6_zero_clip_reuse`, `DQ7_continuous_motion_no_freeze`, `DQ9_zero_background_plaque`, `DQ10_subtitle_geometry_y64`, `DQ11_broadcast_audio_density`, `DQ13_transition_hygiene`, `DQ_Smooth_temporal_smoothness`, `DQ_Border_no_lens_intrusion`, `DQ_R85_flow_31_brain_only`, `DQ_R87_hook_and_arrow_lock`.
  - **`DQ8_zero_uncanny_skin_gore` (2-Tier Suspect Triage + Evidence Crops)**: Scans unscrimmed raw clips every `0.25s`, filters non-head pareidolia (`min_dim < 65px`, `L_med < 85`), classifies YuNet detections into **`HIGH_SUSPECT`** (`eye_3d_flesh_socket >= 0.35`, `cheek_pore_hf >= 0.55`, or non-hat `dark_hair_wrap >= 0.24` — **sole auto-regen / `DQ8` fail trigger**) vs **`MODERATE_SUSPECT`** (remaining YuNet head boxes), and saves annotated crops (`05_assembly/dq8_suspect_crops/*.png` + `05_assembly/dq8_suspect_contact_sheet.jpg`) for mandatory `Independent Visual Reviewer (Gate 1/2)` Gate 2 verdict.
- **[Tier-2 Advisory (`advisory_gates`, non-blocking)]**: `DQ2_clothed_cast_and_impact`, `DQ4_brisk_storyteller_wpm`, `DQ5_three_gear_cut_rhythm`, `DQ_R76_unified_brain_share`, `DQ_R79_human_character_motion`.
- **[Tier-3 Retired on `R85+`]**: `DQ1_literal_analogy_frame_sync`, `DQ12_three_distinct_thumbnails`, `DQ_CAMEO_single_minicortex`, `DQ_R76_brain_simulator_sq`, `DQ_R76_anti_noise_pacing`.

## R63 & R63-P — Per-Sentence Prosody (`pipeline/prosody_qa.py`)
- Native per-sentence `elevenlabs_v4` synthesis (`wsola_factor = 1.0`, zero word-splicing).
- **Prosody QA (`main.py prosody-qa`)**: `P7` (zero clipped/truncated speech), `P9` (zero dead air / ASR match), and `P_R87_s01_duration <= 3.50s` are **Tier-1 Blockers**; `P1–P6, P8, P10, P11` (`F0` span) are **Tier-2 Advisories**.

## R64 — Post-Hoc Clarity, `4×3` Flicker & `Independent Visual Reviewer (Gate 1/2)` Gate 2 (`pipeline/posthoc_qa.py`)
- Detects intra-cut `4×3` grid 1-frame luminance flicker spikes (exempting planned `whip_pan`/`portal_crash_zoom`/cut boundaries), renders Coarse-to-Fine `1536×1536` 12-up contact sheets (`posthoc_viewer_strips/sheet_*.jpg`) + `<=384×384` suspect crops, and requires SHA-256-bound `Independent Visual Reviewer (Gate 1/2)` Gate 2 sign-off in `05_assembly/posthoc_semantic_review.json` (`REVIEW_PENDING` until signed).
