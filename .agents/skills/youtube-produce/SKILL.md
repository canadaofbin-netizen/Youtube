---
name: youtube-produce
description: End-to-end ALL ABOUT BRAIN Shorts production (Gears 1-4: dossier -> script/plan -> Dual-Tier Google Flow refs & clips -> audio/EDL assembly -> full QA) and multi-episode batch orchestration.
---

# youtube-produce (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Core Contracts
- **Format Focus**: Shorts-first (`1080x1920 @ 24fps`, target `~90s` / `1m30s` fast-retention Shorts; hard ceiling `<= SHORTS_HARD_CEILING_SEC`). Defer `16:9` Longform until Shorts KPIs scale.
- **Style**: `DEFAULT_PRODUCTION_PROFILE="neuro_diorama"`, `DEFAULT_DIORAMA_STYLE_PROFILE="porcelain_cinematic_v7"` (R66 featureless matte-white oval-head porcelain figures + Contained Living 4-Color 3D Brain; Track A R67 archival reenactment / Track B R66-Anchor).
- **Voice & Prosody (R63-P)**: `emma_v7` (`en-US-EmmaMultilingualNeural`) + `dynamic_us_v7` native per-gear edge-tts rates (zero WSOLA, `kokoro-onnx` `af_bella` fallback; legacy `andrew_v7` `en-US-AndrewMultilingualNeural` preserved for Public `diorama_01..07` parity). Never pitch-shift (`asetrate` / `afftdn` / `agate` banned).
- **Dual-Tier Monthly Credit Policy (R5)**: Auto-check Flow AI credits (`--engine auto`). Use `Omni 1.1 Flash` while monthly credits remain; seamlessly switch to `0-credit` `Veo 3.1 - Lite [Lower Priority]` + `0-credit` `FLOW_ZERO_CREDIT_IMAGE_MODEL` (`x4` batch) when credits hit 0. Never click `Add AI credits`.
- **Google Flow Workspace & Multi-Agent Tab Isolation**:
  - Canonical project naming in Flow: `AAB_<project_id>` (one Flow project per `project_id`; delete temp/orphan Flow scratch projects after harvest).
  - Never hijack existing tabs: claim dedicated `targetId` tabs (`about:blank` -> Flow project URL), register tab ownership lock per worker, and close only tabs opened by the current worker.
- **Frozen Live Baseline**: Never overwrite projects with `06_publish/upload_receipt.json`.

## 2. Single-Episode Pipeline (`diorama-episode` / `reenact-produce`)
1. **Duplicate Check (R1, R34)**: Verify Psych DOI, `>=2015` Neuro DOI, and case slug do not collide with `BCI_Shorts_Channel/projects/*/06_publish/metadata.json`.
2. **Gear 1 (`youtube-research`)**: `main.py dossier validate --slug <slug> --require-v2` (`ready: true`) + `main.py dossier audit-media --slug <slug> --write`.
3. **Gear 2 (`youtube-script`)**: Author `research_dossiers/<slug>/diorama_v7_porcelain/{script.json,visual_plan.json,metadata.json}` -> `main.py prompt-gate --dir ...` (`passed: true, issues: []`).
4. **Precheck & Refs**:
   - `main.py diorama-episode --slug <slug> --project <id> --pillar <pillar> --precheck-only`
   - `main.py porcelain-refs --project <id> --slug <slug>` (Q1-Q10 `9:16` refs)
5. **Gear 3-4 Generation + Assembly + QA**:
   - Track B / Hybrid: `main.py diorama-episode --slug <slug> --project <id> --pillar <pillar> --engine auto --tabs 5`
   - Track A (R67): `main.py reenact-produce --slug <slug> --project <id> --pillar <pillar> --voice-preset emma_v7 --prosody-mode dynamic_us_v7`
   - Standalone re-assembly: `main.py diorama-assemble --project <id> [--preserve-audio] --force --posthoc-qa`

## 3. Mandatory Gate Chain (Zero Threshold Weakening)
- `prompt-gate` -> `ref-qa` (Q1-Q10) -> `verify` -> `autopsy` -> `episode-qa` (DQ1-DQ12) -> `posthoc-qa` (R64 clarity `>= POSTHOC_MIN_CUT_CLARITY_SCORE`) -> `prosody-qa` (P1-P10) -> `thumbnail` (TQ1-TQ7) -> `reenact-qa` (RQ1-RQ5 if Track A) -> `kb sync`.
- Remediation:
  - P2 hook timing: tighten S1/S2 words, re-run `diorama-assemble --force --posthoc-qa`.
  - P10 re-hook gap: convert in-place sentence to `?` re-hook (keep sentence count fixed so clip indices stay aligned).
  - R64/DQ weak cut: `main.py diorama-flow --project <id> --clips <csv>` then re-assemble.

## 4. Multi-Episode Batch (`diorama-batch`)
- Balance 5 everyday domains (`sleep`, `habits`, `memory`, `anxiety`, `relationships`) and 7 pillars (P1, R20).
- Run `main.py diorama-batch --projects <p1,p2,...> --engine auto` (or `--precheck-only` first).
- FUSE rule: use `rclone delete` / `rclone purge` (`--fast-list`) for bulk media cleanup; avoid `rm -rf` or inline bash apostrophe quoting.
