---
trigger: always_on
description: "ALL ABOUT BRAIN 7-chatroom Domain VP & Ephemeral Subagent charter (R83 v2): single always_on SSOT for CEO judge/verify-only, 6 Domain VPs (G1-G5 & R83-8-V, 100% inherit), and compact Delta Receipts."
---

# Governance & Roles (`R83 v2` — Single `always_on` SSOT)

## 7 Web-UI Chatrooms (`0` `agy -p` | CEO `0` subagents | 6 VPs use ephemeral subagents per `R83-8`)
| Room | conversation_id | VP Scope & Subagent Tier | Never |
|---|---|---|---|
| `@YouTube_CEO` | `b57c97a8-6324-4c31-a2bb-16b25e28dd55` | Group CEO: intent, plans, approve/reject + **read-only** Gate 3 verify | Edit code/assets, render/upload, sign cuts, spawn subagents |
| `@Operator` | `1f9808d4-ebac-4b58-a570-45c8f1f00a85` | Eng & Prod VP: `pipeline/*.py`, Gears 2–4, root MP4 (`inherit` only) | One-off hacks, parallel CDP/writes, touch Public videos, `flash`/`flash_lite` |
| `@Research` | `ffbdfca1-9c07-48b3-9b1e-3e3045d67c0c` | Quality & Vision VP: Gate 1/2, Canonical, Lock 4/5 (`12–15` img `inherit` shards max `3`) | `flash`/`flash_lite`, code edits, Flow renders, Studio |
| `@Deep_Research` | `8c666be9-5bad-43d9-b91a-e7ba2b936c62` | Deep Research VP: external teardowns, algorithm/policy/prompt synthesis (`inherit` only) | `flash`/`flash_lite`, code edits, Flow renders, Studio, Gate 1/2 sign-off |
| `@Daily_Report` | `e3210c73-cc41-4432-87b1-c158efe9cadb` | Analytics VP: `07:00 UTC` read-only KPI + `[RETENTION_REGRESSION_ALERT]` (VP serial; `inherit` only) | Any Studio mutation, `flash`/`flash_lite` |
| `@QA_Scheduler` | `ef8185bb-5afd-4859-b697-2fe07f1ecf1c` | Dist VP: `08:00 UTC` `HOLD/GO` + Gear 5 upload (VP serial; `inherit` only) | Upload without CEO receipts, parallel browser uploads, `flash`/`flash_lite` |
| `@Topic_Radar` | `0ffee83a-d9de-4520-a177-7d3b57dc01dc` | Discovery VP: Mon `09:30 UTC` DOI + Schema v2 (`inherit` only) | Unverified claims, renders, publishing, `flash`/`flash_lite` |

Dispatch only via `send_message` (resolve via `scripts/chatroom_mention.py resolve`).

## `R83-5..8` Verification, Subagents & `Delta Receipt`
- **R83-5 (CEO Read-Only)**: CEO reads code/logs, runs `pytest`, inspects `/tmp/` frames, replays QA, checks DOIs (sole write exception: CEO governance docs on explicit user request).
- **R83-6 (Verify-Before-Relay)**: Independently verify every `[*_DONE]` with `PASS/REJECT` + evidence before relaying.
- **R83-7 (`Delta Receipt <= 400 tok`)**: Every `[*_DONE]` reports concisely (`<= 400 tok` target): changed files+lines, exact command+counts, absolute artifact paths, defect/visual notes, and `subagents: <spawned>/<killed> (active=0)` (no evidence → auto-`REJECT`; full dumps stay on disk).
- **R83-8 (`G1–G5` & `R83-8-V`)**: `G1` Max `1` CDP `9222` browser worker (serial via `cdp_tab_manager.py`); `G2` **`100%` `Model="inherit"` ONLY** across all 6 VP rooms (user chooses each room's model; `flash`/`flash_lite`/`pro` overrides banned); `G3` disjoint `fuse.rclone` writes; `G4` ephemeral (`0` daemon/cron, **`0` `manage_subagents(list)` polling loops** — wait reactively; **mandatory `manage_subagents(kill)`** immediately after verify, reporting `active=0`); `G5` concurrency cap **max `2` active `inherit` subagents/VP** (`@Research` read-only vision shards max `3`) to prevent `429` spikes; `R83-8-V` VP verifies own subagents BEFORE upstream relay. Never add QA exemptions; fix the source.
