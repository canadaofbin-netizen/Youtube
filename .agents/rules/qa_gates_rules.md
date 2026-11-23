---
trigger: model_decision
description: "Load when running or updating QA gates (verify, prompt-gate, ref-qa, episode-qa, prosody-qa, posthoc-qa, thumbnail), Adversarial Gate 1/2 VLM reviews, Mute & Hide Name Test, or Flow provenance locks (R18-B, R25, R37, R85, R87)."
---

# Master QA Gates, Adversarial Review & Provenance (`R18-B`, `R25`, `R37`, `R85`, `R87`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Episode QA: [episode_qa_triage_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/episode_qa_triage_rules.md) | Semantic ID: [reference_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/reference_depiction_rules.md)

## 1. 12 Tier-1 Hard Blockers vs Tier-2 Advisories
1. **12 Tier-1 Blockers (Regen Source Only, Zero Exemptions)**:
   (1) Exact stats/species & `0` fake `"Concept"` badges (`R1, R70-M9, R85`); (2) `0%` photoreal skin/hair/beard (`DQ8 HIGH_SUSPECT` + Gate 2); (3) `0` ruin/sign/Rx + open-license (`PD/CC0/CC-BY/CC-BY-SA`) & `reference_provenance.json` (`R72-R, R85`); (4) Brain viewpoint/color lock (`R85`); (5) `0` filler & zero-delta repeats (`R86`); (6) `claim <-> scene/concrete_referent` match (`R86, R64`); (7) True `120ft` drone (`R82, R85`); (8) `R80` `#FF2525` arrow geometry preserved (`R80, R85`); (9) `0` AI text/lens border/ghost (`DQ9, DQ_Border, DQ13, Q7`); (10) `0` clip/dead-air (`P7, P9, DQ11`), freeze (`DQ7`), reuse (`DQ6`), overlap (`R70-M8, R81, DQ10, TQ4/8/9`); (11) `0` auto-signoff, prompt-copied, or stale SHA-256 reviews (`R64, R85`); (12) `Public` safety, `R4` AI disclosure, `No-Draft` warmup, `0` self-bounce (`R30-B, R35, R37, R75`).
2. **Tier-2 Advisory**: Minor vinyl ear/nose contour, `Q2/3/5/6/8/9/10`, `DQ2/4/5/R76_share/R79`, `P1–P6/P8/P10/P11`, `TQ1–TQ3`, `FK/sentence/jargon`, `1 vs 2` stamps.

## 2. `P0-3` Adversarial Gate 1/2, `"Mute & Hide Name Test"` & `R87` Locks
- `UNMANNED_QA_SIGNOFF_DEFAULT = False`: `porcelain-refs`, `diorama-flow`, `diorama-assemble`, `posthoc-qa` halt in `REVIEW_PENDING` (`exit 2`) until `@Research` inspects Coarse-to-Fine sheets (`1536×1536` 12-up + `<=384×384` crops) and signs `reference_semantic_review.json` (Gate 1) & `posthoc_semantic_review.json` (Gate 2).
- **Adversarial Defect-First Format (`P0-3`)**: Zero praise preamble; list largest defects first as **`Wrong / Exact Where / What Instead`**, verify the **`"Mute & Hide Name Test"`** (channel DNA unmistakable at `0.0s` muted & unnamed), and check `Semantic ID` uniqueness across recent episodes.
- **`R87` (`Ep #13+`)**: `prompt-gate` (`validate_r87_hook_contract`, `validate_r87_spatial_arrow_eligibility`, Lock 3), `episode-qa` (`DQ10` `82pt`+`HookTitle`, `DQ_R87_hook_and_arrow_lock`), `prosody-qa` (`P_R87_s01_duration <= 3.50s`), Lock 2 (`silent_3s_scroll_stop`, `narration_visual_logic_match`, `thumbnail_to_0s_promise_kept`), Lock 4 `+48h` `detect_retention_regression_alert`.

## 3. R18-B, R25 & R37 — Provenance, Single MP4 & Tab Lock
- **`R18-B` & `R37`**: `flow_provenance_receipt.json` (`AAB_<project_id>`, `FLOW_AUTO_CLEANUP_ON_SUCCESS=False`), `ALLOW_EXTERNAL_PAID_APIS=False`, `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK=False`, CDP `targetId` lease (`allocate_dedicated_flow_project_tab`).
- **`R25`**: Mirror `05_assembly/final_shorts_1080x1920.mp4` to `07_Youtube/final_shorts_<project_id>.mp4`.
