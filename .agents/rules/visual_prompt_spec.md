---
trigger: model_decision
description: "Load when configuring Dual-Tier Google Flow engines (unified Omni 1.2 Flash single-anchor & Start+End vs Veo 3.1 Lite zero-credit), P0-1 audio/lip-sync guard, CDP tab isolation, or banned prompt tokens (R5, R14-B, R38)."
---

# Visual Prompt Spec & Dual-Tier Google Flow Engine (`R5`, `R14-B`, `R38`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Pacing & Arrows: [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md), [arrows_callouts_motion_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/arrows_callouts_motion_rules.md)

## R5 — Monthly Credit Dual-Tier Google Flow Engine (`--engine auto|omni|zero-credit`)
- **Unified Monthly-Credit Video (`credits > 0`)**: Single-Omni tier `FLOW_PRIMARY_VIDEO_MODEL` (`"Omni 1.2 Flash"`, `macaron_cookie`, API `gemini-omni-1.2-flash`) handles BOTH single-anchor `Ingredients` (`3s–15s`) AND `Start + End` `VIDEO_FRAMES` (`3s–10s`, `chip_count=2`).
- **2026-12-05 Retirements (`0` Fallback)**: `Omni 1.1 Flash` (`abra`), `Veo 3.1 - Fast`, `Veo 3.1 - Quality` retire `2026-12-05` — zero `Omni 1.1` fallback.
- **Zero-Credit Video Fallback (`credits == 0`)**: `"Veo 3.1 - Lite [Lower Priority]"` (`0` cr, `4s/6s/8s`, `Start + End`; `FLOW_ZERO_CREDIT_TEXT="Generating will use 0 credits"`). Never click `Add AI credits`.
- **Zero-Credit Keyframes**: Flow `Image` (`FLOW_ZERO_CREDIT_IMAGE_MODEL` = `"Nano Banana 2.1"`, `DEFAULT_REENACT_IMAGE_BACKEND="flow"`): `x1` 1st-pass (`FLOW_ZERO_CREDIT_IMAGE_BATCH_COUNT=1`), `x2` retry / `--refs <id> --force` Gate 1 regen (`FLOW_ZERO_CREDIT_IMAGE_RETRY_BATCH_COUNT=2`), `x2` `R65 v4` thumb (`FLOW_ZERO_CREDIT_IMAGE_THUMBNAIL_BATCH_COUNT=2`); fail-fast (`0` retry / `0` model hop) on `"unusual activity"`.
- **Room & Tab Hygiene**: Room `AAB_<project_id>` (`FLOW_AUTO_CLEANUP_ON_SUCCESS = False`); per-worker CDP `targetId` (`allocate_dedicated_flow_project_tab`); `ALLOW_EXTERNAL_PAID_APIS=False`, `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK=False`.

## R14-B, `P0-1` Silence/Lip-Sync Guard & Scoped R38 (`Tier-1 #9`)
- **`P0-1` Audio & Lip-Sync Negative Guard**: `FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD` (`pipeline/depiction_rules.py`) appends `"No voiceover, no narration, no background music, no lip movement."` cleanly behind `"Silent voice track."`, preserving `prompt_core.endswith("Silent voice track.")` and the `(18, 64)` word cap.
- **Global Bans**: `mobius`, `seamless loop`, `HUD`, `telemetry`, `ARRI`, `Alexa`, `all about brain`, `watermark`, `#hex` codes, `Camera Angle N`, physical camera/drone hardware nouns (`R77`), unallowlisted signage/plaque triggers (`R56`). *(`locked-off` / `tripod` allowed in `v7/v8`.)*
- **Scoped `R38`**: Mechanical gears/clockwork/scales/shutters & sparks banned inside brain cuts; everyday physical props (`scales, locks, sponges, doors, scissors`) allowed in `R86` `story`/`metaphor` cuts.
