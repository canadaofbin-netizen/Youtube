---
trigger: model_decision
description: "Load when configuring 30fps optical flow (R77), R78-M/H/V acting & Ep #31 anchors, R79-M 2-beat motion, R80/R87-A conditional #FF2525 3D contrast arrows vs Category K, or R81 XL PatrickHand callouts (R77-R81, R87-A)."
---

# Optical Flow, Acting, `R80/R87-A` Arrows & `R81` Callouts (`R77–R81`, `R87-A`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Brain: [brain_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/brain_depiction_rules.md) | Pacing: [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md)

## R77 & R77-N — `DISOpticalFlow` `30fps` & Lens-Border Ban (`Tier-1 #9 & #10`)
- Bidirectional half-res `cv2.DISOpticalFlow` `24->30fps` upsampling (`0%` frame-duplication judder, `>= 1.0x` natural speed unless slow-mo).
- Scrubs physical camera/drone/rig nouns (`[r77_hardware_ban]`, `"Radcliffe Camera"` exempt) and blocks dark fisheye/goggle bezels (`DQ_Border_no_lens_intrusion`).

## R78-M / R78-H / R78-V — Ep #31 Brain Start Lock, Acting & 5-Tone `Siren`
- **`R78-M`**: Locks brain cuts (`src_start_sec=0.0`) to genuine `31_O2CmlKOk` Mode 1 X-Ray Head or Mode 2 Silver-Gray (`#9CA5AC–#C3C9CE`) + `#27D8FF` sulcal cyan (`ep31_orig_mode1_head_9x16.png`, `ep31_orig_mode2_lateral_9x16.png`, `ep31_orig_mode2_dorsal_9x16.png`, `ep31_orig_mode2_vessel_macro_9x16.png`).
- **`R78-H`**: Active 2.5D vinyl micro-acting + functional glosses (`amygdala` = `"Emotional Center"`, `prefrontal cortex` = `"Reality-Checker"`).
- **`R78-V`**: 5-tone `Siren` gears (`surprised_lift`, `insider_reveal`, `hushed_suspense`, `deadpan_drop`, `action`); `P11` `F0` span is Tier-2.

## R79-M — Subject+Verb Integrity & State-A Lock
- Foreground `[Explicit Cast Subject] + [Physical Action Verb]` (`[r79m_missing_subject]`, `[r79m_missing_action_verb]`, `[r79m_dangling_truncation]`), crisp 2D black ink step-snap (`[r79m_ink_smudge_ban]`), rigid straight walls (`[r79m_wall_warp_ban]`). Motion floor (`DQ_R79`) is Tier-2; only freeze `DQ7` blocks.

## R80 & R87-A — Conditional `#FF2525` 3D Arrows vs `Category K` (`Tier-1 #8`, `pipeline/spatial_arrow_guide.py`)
- **`R87-A`**: Require explicit `spatial_arrow_eligible: bool` (never auto-seed `r80_mode=True` on non-spatial dossiers).
  - `False` (pharmacology/sleep/diet/pain/emotion/bias): Hard-bans `spatial_3d_arrow_diorama`; routes to `Category K` (`K01–K05`) tactile prop contrast + `K06/A12` dual-brain contrast.
  - `True` (navigation/doorway/maze): Requires `C01b–C03b` prop-anchored `#FF2525` 3D arrows (`adaptive_landmark_zigzag`, `fixed_linear_corridor`, `doorway_boundary_sever`, `dual_route_race_lanes`, `dual_speed_race_lanes`), named architecture, and bans single-arrow `fixed_linear_corridor` on binary comparison (`side by side`/`vs`).
- **Start+End Lock**: Lock `reference_image` + `end_reference_image` via `Omni 1.2 Flash` (`macaron_cookie`, `VIDEO_FRAMES` `3s–10s`; `0-credit` fallback `Veo 3.1 - Lite [Lower Priority]`).

## R81 — XL `PatrickHand` Brain Callouts & Zero-Drift (`Tier-1 #10`)
- `PatrickHand-Regular.ttf` box-free ink callouts (`82–84px` 1-line / `64–82px` 2-line stack), **`0px` underline strikethrough** (`ul_y = drawn_bbox[3] + 10px`), `1.0x` `DISOpticalFlow` + silhouette tracking.
