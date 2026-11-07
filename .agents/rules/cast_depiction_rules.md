# Cast Depiction Rules (`R14-A`, `R45`, `R66`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Code: [`pipeline/flow_prompt_builder.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/flow_prompt_builder.py), [`pipeline/porcelain_anchor_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py), [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)

## R66 — Active `porcelain_cinematic_v7` Cast Contract (`PORCELAIN_V7_CAST_STYLE`)
- **Head & Surface**: Clothed articulated matte-white porcelain figures with **smooth featureless solid matte-white egg-shaped oval heads** — zero human skin/eyes/mouths (`PORCELAIN_V7_HUMAN_SKIN_MAX`, YuNet face gate = `0` faces) and **zero frosted-glass craniums** on `porcelain_cinematic_v7`.
- **Wardrobe & Continuity**: Era/role-matched solid matte fabric clothing (`ref_cast_<role>.png` conditioned on `ref_env_master.png`), ball-jointed porcelain hands, zero crowd clutter.
- **Acting**: Emotion and causality conveyed 100% via 2-Beat physical hand/arm/posture prop actions ([scene_depiction_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/scene_depiction_rules.md)). Animals render as articulated matte-white porcelain figures.

## R45 & R14-A — Visual Modes & Legacy v4/v5 Cast
- **`VISUAL_MODES` (`R45`)**: `BEHAVIORAL_PSYCH` (`0` brain clips), `HYBRID` (`<= 2` brain clips), `NEURO_BIOLOGY` (`<= 4` brain clips) (`MAX_BRAIN_CLIPS_BY_MODE`, `MODE_ROLE_SETTINGS`).
- **Legacy v4 (`R14-A`)**: Clothed articulated matte-white porcelain mannequins with translucent frosted-glass craniums (`Clip 1–3, 9–10`).
