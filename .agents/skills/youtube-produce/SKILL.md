---
name: youtube-produce
description: End-to-end ALL ABOUT BRAIN Shorts production (Gears 1-4: dossier -> script/plan -> Dual-Tier Google Flow refs & clips -> audio/EDL assembly -> full QA) via the Fresh-Room state machine.
---

# youtube-produce (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Core Production Locks (`R68–R89`)
- **Format & Visuals**: Shorts-first (`1080x1920 @ 30fps`, `61.5–88.0s` `R75` ceiling on `shorts_expressive_v8`; `16:9` Longform on HOLD). `18–28` unique `VIDEO_FRAMES` clips (`R82`): `1.90–4.25s` 2-beat `R88` faceless porcelain human cuts, `S01–S03` `120ft` institution drone, `4.20–6.80s` (`42–58%`) `100%` Google Flow `Ep #31` 6-scale brain cuts (`0%` Blender screen render), XL `82–84px` `PatrickHand` callouts, `<= 2` `R70-M` `study` Data Stamps.
- **Audio & Subtitles**: `elevenlabs_v4` (`eleven_v4`) Solo `Siren` (`el_siren_v4`, `eXpIbVcVbLo8ZJQDlDnl`, 5-tone `R78-V` gears; `0` pitch-shift `asetrate`/`afftdn`/`agate`), stereo BGM (`-14.0 LUFS`), `0.00–2.20s` `118pt HookTitle` (`#FFE14A`), and `82pt` `Outline=5.5` `Shadow=1.5` `MarginV=510` `<= 3w` `#FFE600` ASS subtitles (`DQ13` `<= 4` styled transitions).
- **Dual-Tier Monthly Credit Policy (`R5`)**: `--engine auto` uses unified `Omni 1.2 Flash` (`Ingredients` `3–15s` + `Start+End` `3–10s`) while credits remain (`Omni 1.1` / `Veo Fast/Quality` retired), falling back to `0-credit` `Veo 3.1 - Lite [Lower Priority]` (`<= 2` tabs) + `Nano Banana 2.1` (`x1` 1st-pass / `x2` `--refs <id> --force` retry; `0`-retry fail-fast on `"unusual activity"`). Never click `Add AI credits`.
- **Flow Room & Tab Isolation**: Persistent room `AAB_<project_id>` (`FLOW_AUTO_CLEANUP_ON_SUCCESS = False`); isolated `targetId` tabs (`cdp_tab_manager.py`); never mutate published `upload_receipt.json` projects.

## 2. Single-Episode State Machine (`main.py ep`)
1. **Duplicate Check (`R1`, `R34`)**: Verify Psych DOI, `>=2015` Neuro DOI, and slug do not collide with `BCI_Shorts_Channel/projects/*/06_publish/metadata.json`.
2. **Gear 1 (`youtube-research`)**: `main.py dossier validate --slug <slug> --require-v2` + `main.py dossier audit-media --slug <slug> --write` + `main.py dossier seed --slug <slug> --style-profile expressive_25d_v8`.
3. **Gear 2 (`youtube-script`)**: Author `diorama_v8_expressive/{script.json,visual_plan.json,metadata.json}` -> `main.py prompt-gate --dir <dir>` (`"passed": true`).
4. **Gate 1 Keyframe Pack**: `main.py ep status <id>` -> `main.py ep run <id> --until gate1` (or `main.py refs --project <id> --slug <slug>`). Review `1536x1536` `12-up` sheet via fresh `Independent Visual Reviewer (Gate 1/2)` subagent (`kill` immediately after signing `reference_semantic_review.json`).
5. **Gear 3–4 Flow, Archival Cuts, Assembly & Gate 2**:
   - `main.py ep run <id> --until gate2` (runs Flow clips, auto-renders `03_visuals/archival_inserts_manifest.json` `R88-A` & `archival_videos_manifest.json` `R89` `split_sync`/`viewfinder_locator` locally with `0` Flow uploads, assembles, runs Max-RAM Single-Pass 8-Core QA, and releases RAM `speed_cache`).
   - After independent Gate 2 review signs `posthoc_semantic_review.json`, run `main.py ep run <id> --until ready` -> generates `R65 v4` thumbnail, mirrors `07_Youtube/final_shorts_<project_id>.mp4`, verifies SHA-256 manifest, and writes `05_assembly/ceo_verify_receipt.json`.

## 3. Mandatory Gate Chain & Remediation
- `prompt-gate` -> `ref-qa` (Gate 1) -> `verify` -> `autopsy` -> `episode-qa` (`DQ2–DQ13`, `DQ8` crops) -> `posthoc-qa` (`4×3` flicker + Gate 2) -> `prosody-qa` (`P7/P9`, `P_R87_s01_duration`) -> `thumbnail` (`TQ4/6/7/8/9`) -> `qa-summary --project <id>` -> `kb sync --project <id>`.
- Targeted regen: `main.py flow --project <id> --clips <csv>` then `main.py assemble --project <id> --preserve-audio --force --posthoc-qa`.
- FUSE hygiene: use `rclone delete` / `rclone purge --fast-list` for bulk Drive cleanup; never reuse Canonical PNGs directly as video clips (`Semantic ID` 5-Guard).
