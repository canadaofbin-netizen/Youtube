---
trigger: model_decision
description: "Load when choosing or validating clip camera moves, 120ft aerial campus drone shots, single-move-per-clip discipline, or Mode 1 -> Mode 2 cranium transitions (R66, R68, R72, R82, R85)."
---

# Camera Choreography Rules (`R66`, `R68`, `R72`, `R82`, `R85`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Pacing Spec: [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | Motion Spec: [arrows_callouts_motion_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/arrows_callouts_motion_rules.md) | Retired (`R14-D v4, R55`): [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## Active `v8` / `v7` Camera Discipline & `P1-4` Hero Low-Angle Framing
- **One Disembodied Move Per Clip**: Never chain conflicting moves (`orbit + whip-pan`), never write `Camera Angle N` labels, and maintain **`0` banned `"dolly"` or camera/drone/gimbal hardware nouns** in Flow prompts (`R77`).
- **`P1-4` Hero `~35–45%` Low-Angle & `push-in ↔ pull-back` Rhythm**: Hero human character cuts (`2–3` per episode) frame the subject at **`~35–45%` frame occupancy** with `hero_low_angle` subtle upward framing (keeping top `HookTitle` `Y=238–422px` and bottom ASS safe zones clear), alternating **`disembodied push-in ↔ smooth pull-back`** across consecutive cuts to sustain kinetic depth without hardware nouns.
- **True `120ft` Institution Aerial Drone (`Tier-1 #7`)**: `drone_aerial_approach`, `drone_landmark_ascend`, and `drone_high_orbit_drop` MUST maintain true ~120ft/30m aerial bird's-eye scale (`"120ft altitude, figures read as tiny dots"`), zero eye-level pedestrian walking verbs (`walk, stride, jog`), and `human_action_relay=False`.
- **Poised Brain Parallax (`R81`, `R82`)**: Brain cuts hold gentle `<= 12°–15°` single-plane parallax or slow push/pull (`0` frantic 90° spins) so `R81` callout leader lines track with zero drift.
- **Camera Ratio Targets (`Tier-2 Advisory`)**: `locked_tripod >= 15%` (`>= 35%` on `v7`), `orbital_3d_arc_sweep <= 30%`, `fpv_dive_glide <= 25%` are non-blocking design targets.
