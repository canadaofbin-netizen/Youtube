---
name: youtube-produce
description: End-to-end ALL ABOUT BRAIN Shorts production (Gears 1-4: dossier -> script/plan -> Dual-Tier Google Flow refs & clips -> audio/EDL assembly -> full QA) and multi-episode batch orchestration.
---

# youtube-produce (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | [qa_gates_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/qa_gates_rules.md)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Core Contracts
- **Format Focus**: Shorts-first (`1080x1920 @ 30fps` `61.5–88.0s` `<= 88.0s` `R75` ceiling on active `shorts_expressive_v8` / `R68–R87`; legacy `24fps` `porcelain_cinematic_v7` & `PRE_R75_DURATION_GRANDFATHER_PROJECTS` preserved on frozen archives; hard ceiling `<= SHORTS_HARD_CEILING_SEC`). Defer `16:9` Longform until Shorts KPIs scale.
- **100% Google Flow Visuals (`R85` Ep #31 6-Scale Brain + `R87-A` Conditional Arrows + `R70-M` `2` Data Stamps + `R82` Dual-Speed Pacing)**: `DEFAULT_PRODUCTION_PROFILE="neuro_diorama"`, active `expressive_25d_v8` (`18–28` `VIDEO_FRAMES` clips under `R82`: `1.90–4.25s` 2-beat human cuts, mandatory `S01–S03` `120ft` institution drone, `4.20–6.80s` `42–58%` `100%` Google Flow `Ep #31` brain cuts conditioned on `ep31_orig_*` + off-screen `/tmp/` MNI152/Wikimedia guides with `0%` on-screen Blender renders, XL `R81` `82–84px` `PatrickHand` callouts, `0` mascot cameos, `2` `R70-M` `study` Data Stamps).
- **Solo `Siren` 5-Tone ElevenLabs `v4` Voice (`R76` / `R78-V`), Soundscape & Subtitles**: `elevenlabs_v4` (`eleven_v4`, `192kbps` MP3 + char alignment + SHA-256 cache, 3x transient retry, zero silent neural/Kokoro downgrade) locks `100%` Solo `Siren` (`el_siren_v4`, `eXpIbVcVbLo8ZJQDlDnl`, 5-tone `R78-V` gears verified by `P11`; `0` foil/secondary voices). `v8` preserves narrative lighting (`luma >= 26.0`, `dark_v35 <= 0.68`), documentary BGM + Foley (`-14.0 LUFS`), `0.00–2.20s` `118pt HookTitle` (`#FFE14A`), and `82pt` `Outline=5.5` `Shadow=1.5` `MarginV=510` `<= 3w` `#FFE600`-highlighted ASS subtitles (`DQ13` `<= 4` styled transitions). Never pitch-shift (`asetrate`/`afftdn`/`agate` banned).
- **Dual-Tier Monthly Credit Policy (R5)**: Auto-check Flow credits (`--engine auto`). Use unified `Omni 1.2 Flash` (`macaron_cookie`, `gemini-omni-1.2-flash`) for BOTH single-anchor `Ingredients` (`3s–15s`) AND `Start+End` `VIDEO_FRAMES` (`3s–10s`) while credits remain (`compute_dynamic_omni_episode_budget`); `Omni 1.1 Flash` (`abra`), `Veo 3.1 - Fast`, and `Veo 3.1 - Quality` retire `2026-12-05` (`0` `Omni 1.1` fallback). Fallback to `0-credit` `Veo 3.1 - Lite [Lower Priority]` (`4s/6s/8s`, `Start+End` supported, `<= 2` tabs) + `Nano Banana 2.1` (`x1` 1st-pass / `x2` retry & `--refs <id> --force` regen; `0`-retry fail-fast on `"unusual activity"`) when credits hit 0. Never click `Add AI credits`.
- **Flow Room & Tab Isolation**: Room `AAB_<project_id>` (`FLOW_AUTO_CLEANUP_ON_SUCCESS = False` — never delete rooms); claim dedicated `targetId` tabs (`cdp_tab_manager.py`) and never touch sibling tabs. Never overwrite `06_publish/upload_receipt.json` baselines.

## 2. Single-Episode Pipeline (`diorama-episode` / `reenact-produce`)
1. **Duplicate Check (R1, R34)**: Verify Psych DOI, `>=2015` Neuro DOI, and slug do not collide with `BCI_Shorts_Channel/projects/*/06_publish/metadata.json`.
2. **Gear 1 (`youtube-research`)**: `main.py dossier validate --slug <slug> --require-v2` + `main.py dossier audit-media --slug <slug> --write` + `main.py dossier seed --slug <slug> --style-profile expressive_25d_v8`.
3. **Gear 2 (`youtube-script`)**: Author `research_dossiers/<slug>/diorama_v8_expressive/{script.json,visual_plan.json,metadata.json}` -> `main.py prompt-gate --dir ...` (`"passed": true`).
4. **Precheck & Refs**: `main.py diorama-episode --slug <slug> --project <id> --pillar <pillar> --precheck-only`, then `main.py porcelain-refs --project <id> --slug <slug>` (`x1` 1st-pass; `--refs <id> --force` `x2` Gate 1 regen).
5. **Gear 3–4 Generation + Assembly + QA**:
   - `main.py diorama-episode --slug <slug> --project <id> --pillar <pillar> --engine auto --tabs 5` (or `reenact-produce` for Track A).
   - If using `R88-A` photos (`archival_inserts_manifest.json`) or `R89` muted `2–4s` experiment videos (`archival_videos_manifest.json` -> `render_archival_video_clips`: Mode 1 `split_sync` or Mode 2 `viewfinder_locator` inside `(80, 288, 908, 1218)`), render locally in Gear 4 (`0` Flow uploads, `Cut >= 2` / `>= 2.20s`, combined `<= 2` cuts & `<= 10%` share).
   - Re-assembly: `main.py diorama-assemble --project <id> [--preserve-audio] --force --posthoc-qa`.
   - Export final MP4 to `07_Youtube/final_shorts_<project_id>.mp4`.

## 3. Mandatory Gate Chain (Zero Threshold Weakening)
- `prompt-gate` -> `ref-qa` (Gate 1 `REVIEW_PENDING`) -> `verify` -> `autopsy` -> `episode-qa` (`DQ1–DQ13`, `DQ8` crops) -> `posthoc-qa` (`4×3` flicker + Coarse-to-Fine `1536×1536` Gate 2 `REVIEW_PENDING`) -> `prosody-qa` (`P7/P9/P_R87`) -> `thumbnail` (`R65 v4` `TQ4/6/7/8/9`) -> `qa-summary --project <id>` -> `kb sync --project <id>` (`pytest -v` `<60s` during iteration; `pytest -m slow` before delivery).
- Remediation: `P2`/`P_R87` tighten `S01/S02` + re-assemble; `P10` convert in-place sentence to `?`; `R64/DQ` weak cut `main.py diorama-flow --project <id> --clips <csv>` then re-assemble.

## 4. Multi-Episode Batch (`diorama-batch`)
- Balance 5 everyday domains & 7 pillars (`P1, R20`); never reuse Canonical PNGs directly as raw clips (`Semantic ID` 5-Guard).
- FUSE rule: use `rclone delete` / `rclone purge --fast-list` for bulk cleanup; avoid `rm -rf` or inline bash apostrophe quoting.
