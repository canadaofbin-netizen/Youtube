---
trigger: model_decision
description: "Load when designing, prompting, or reviewing 3D brain anatomy keyframes/clips, Ep #31 6-Scale Flow Brain modes, per-region cutaway viewpoints, MNI152/Wikimedia guides, or color codes (R21, R38, R48, R53, R66, R81, R85, R85-R)."
---

# Brain Depiction Rules (`R21`, `R38`, `R48`, `R53`, `R66`, `R81`, `R85`, `R85-R`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Pacing: [hook_pacing_beatcard_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/hook_pacing_beatcard_rules.md) | Retired: [retired_rules_2026-11-18.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/_archive/retired_rules_2026-11-18.md)

## R85 & R85-R — `100%` Google Flow `31_O2CmlKOk` 6-Scale Brain (`Tier-1 #4 & #5`)
- **`100%` Flow Engine (`R85_BRAIN_RENDER_ENGINE = "google_flow"`)**: Render all on-screen brain cuts in Flow conditioned strictly on genuine `31_O2CmlKOk` anchors (`ep31_orig_mode1_head_9x16.png`, `ep31_orig_mode2_lateral_9x16.png`, `ep31_orig_mode2_dorsal_9x16.png`, `ep31_orig_mode2_vessel_macro_9x16.png`; 2nd-gen derivative anchors retired). Direct on-screen Blender rendering (`R84`) is retired (`0%`).
- **6 `31_O2CmlKOk` Visual Locks (`Q_R85_ep31_brain_fidelity` & `DQ_R85_ep31_brain_fidelity`)**:
  1. **Material**: Bright cool matte silver-white gypsum plaster (`#DCDFE3–#ECEFF2` / `#9CA5AC–#C3C9CE`, `S <= 48.0`, `V >= 152.0`, zero steel tint or wet gloss).
  2. **Sulcal Vessels**: Thick opaque sky-blue `#27D8FF` tubes tucked *inside* sulcal grooves (never thin lightning veins).
  3. **Zero AI VFX (`[r85_brain_banned_vfx]`)**: Ban `glow`, `neon`, `sparkle`, `particles`, `embers`, `bloom`, `light beam`, `ethereal`, `energy`, `smoke`, `haze`, `lightning`, `luminous`, `radiance`, `halo`, `aura`, `frosted-glass`, `optical-glass`.
  4. **Mode 1 Head**: Light-gray glossy mannequin head (`#C4CBD2–#E0E5EA`, `p75 >= 155.0`) + clear glass upper cranium cap.
  5. **Focal Highlight**: Paint target regions solid matte amber-gold, crimson, green, or slate `#68707A`; traveling signals = short opaque solid segments inside tubes.
  6. **Background**: Flat dark navy (`#040711`), zero vignette bloom (`halo_p90 <= 40.0`).
- **6-Scale Rotation**: Rotate `xray_head_dive`, `split_cutaway`, `sulcal_cyan_dive`, `vessel_csf_macro`, `1p_tract_canyon`, `3p_shutdown_or_top_bottom` (`Start+End` `VIDEO_FRAMES` via `Omni 1.2 Flash` `macaron_cookie` on `A vs B`; `0-credit` fallback `Veo 3.1 - Lite [Lower Priority]`).
- **Off-Screen Guides (`R85-R`)**: Condition on `NEUROANATOMY_CUTAWAY_MAP` Wikimedia plates + `/tmp/aab_real_refs/<project_id>/guides/` MNI152 guides (`0%` direct exposure).
- **Per-Region Viewpoints (`R85_ANATOMY_VIEWPOINT_RULES`)**: `hippocampus` = `inferior_lateral_cutaway`/`coronal_cutaway`; `thalamus`/`brainstem`/`csf` = `midsagittal_cutaway`; `insula` = `lateral_opercular_retracted` (`midsagittal` forbidden); `prefrontal cortex` = `anterior_three_quarter_lateral`.
- **Color Lock (`R21, R53, R66`)**: Fix 1 color legend/ep (`#27D8FF` cyan = vessels/CSF, amber-gold = active signal, crimson = suppression); `<= 0.08` neon spill; `R81` `PatrickHand` text only.

## R38 (Scoped) & R48 — Neuroanatomy & Claim Alignment
- Mechanical gears/clockwork/scales/shutters banned inside brain cuts (allowed in `R86` `story`/`metaphor` cuts). Structures must explain the spoken behavior (`R48`).
