---
trigger: always_on
description: "ALL ABOUT BRAIN Fresh-Room Single-Owner & Ephemeral Subagent Charter (R83 v3): 0k fresh chatroom per episode/task, clean ephemeral Vision Reviewer subagents for Gate 1/2 (zero image buildup in main context), CDP serial lock, and compact CLI discipline."
---

# Governance & Operating Architecture (`R83 v3` — `Fresh-Room` Single `always_on` SSOT)

## 1. `Fresh-Room` Single-Owner Model (`R83-1..4` — Replaces Retired 7-Room Routing)
- **1 Task / 1 Episode = 1 Fresh Chatroom (`0k` Start)**: Start every episode production, code upgrade, or audit in a fresh conversation (`0k` context) and close on completion (`0` standing multi-day rooms, `0` `chatrooms.json`, `0` cross-room `send_message` ping-pong, `0` `agy -p`).
- **Context Ceiling (`<= 120k`)**: Checkpoint state (`main.py ep status <id>`) and run `/compact` before reaching `120k` tokens.
- **Zero-Token Daily Ops**: Run daily KPI/watchdog/schedule checks headlessly via OS `crontab` (`scripts/run_daily_ops_headless.sh` -> `studio-report`, `studio-watchdog`, `qa-scheduler`, `0` LLM tokens).
- **Compact CLI First**: Default CLI QA outputs stay `<= 1.8 KB` (`--verbose-json` only when debugging). Use `main.py ep status <id>` and `main.py qa-summary --project <id>` instead of ad-hoc `python -c` state probes.

## 2. Independent Visual Review (`Gate 1` & `Gate 2`) & Immutable Locks (`R83-5..7`)
- **Zero Self-Signoff (`UNMANNED_QA_SIGNOFF_DEFAULT = False`)**: Main room auto-signoff and raw full-res PNG loading in main context are strictly banned.
- **Clean Ephemeral Vision Subagent (`Gate 1` Refs & `Gate 2` Final Cuts)**:
  1. Render `12-up` coarse sheets (`1536x1536` JPEG) + `<= 384px` suspect crops (`scripts/render_qa_sheets.py` / `posthoc-qa`).
  2. Invoke ONE fresh `Independent Visual Reviewer (Gate 1/2)` subagent (`Model="inherit"`, zero prior history) with ONLY sheet/crop paths and beat map.
  3. Record adversarial `Wrong / Exact Where / What Instead` + SHA-256 notes to `reference_semantic_review.json` / `posthoc_semantic_review.json`, then **immediately `kill` (`active=0`)** so `0` images remain in main context.
- **Immutable Safety Locks**: Never mutate/delete `Public` YouTube videos (`24+` live) or `canonical_assets/` (`99` SHA-locked slots). Export completed MP4s to `07_Youtube/final_shorts_<project_id>.mp4` and verify local QA + release receipt before `studio-upload`.

## 3. Ephemeral Subagent Guardrails (`R83-8`: `G1–G5`)
- **G1 (Serial Browser)**: Max `1` CDP `9222` worker via `cdp_tab_manager.py` (never close Tier-1 anchor tabs).
- **G2 (Model Tiering)**: `Model="flash"` allowed for mechanical search/log/schema chores; `Model="inherit"` required for VLM Gate 1/2, scripts, and core architecture.
- **G3 (Disjoint Writes)**: Parallel workers write to disjoint paths (`/dev/shm/aab_scratch` before atomic commit to `fuse.rclone`).
- **G4 (Lifecycle)**: `0` daemons, `0` polling loops — wait reactively and `kill` immediately after verify (`active=0`).
- **G5 (Cap)**: Max `2` concurrent `inherit` subagents (max `3` vision shards). Never add QA exemptions; fix `pipeline/*.py`.
