# Camera Choreography Rules (`R14-D`, `R55`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Prompts: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md), [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) | Code: [`pipeline/depiction_rules.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/depiction_rules.py)

## Active Schema v7 Camera Rig (`DIORAMA_V7_CAMERA_MOVES` — `R63` / `R66`)
- **Orthogonal Documentary Rig**: Tripod lock-off floor `>= DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO` (`0.35`, target `~0.40`), zoom/push-pull ceiling `<= DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO` (`0.30`); `PORCELAIN_V7_MIN_CUT_SEC..PORCELAIN_V7_LONG_TAKE_MAX_SEC` same-scene multi-angle coverage (wide room -> hands insert -> POV hands -> cutaway/brain).
- **One Move Per Clip**: Never chain conflicting moves (`orbit + whip-pan + dolly`) or embed `Camera Angle N` / `Shot N` labels. Anchor brain targets by anatomical name (`temporal lobe`, `ventral surface`), never screen quadrant (`upper-left`).

## R14-D & R55 — Legacy v4/v5 Role Camera Map (`clip.camera_move`)
| Role | Move (`classic_v5` / brain transitions) |
|---|---|
| `setup` | Wide establishing shot smoothly tracking forward toward subject |
| `symptom` | Close-up slow orbit around head |
| `failure` | Smooth lateral track between figures |
| `crisis` (`R55` dive) | Smooth dive through frosted-glass cranium -> glide over gyri/sulci -> zoom into target |
| `pivot` | Smooth orbit around structures, push in on `amber-gold` compensatory route |
| `mechanism` / `step1` / `step2` | Macro tracking following contained signal stream along `signal_path` |
| `step3` | Pull back to reveal full 3D anatomical circuit |
| `breakthrough` (`R55` exit) | Smooth pull-out from brain through cranium back into room |
| `conclusion` (`R19`) | Independent slow pull-back rising to elevated wide shot (never loops to Clip 1) |

- **R14-D v5 (`real_env` Reenactment)**: `visual_plan.shots[role].camera` selects 1 action-matched move: iconic blocking (`low-angle tracking`, `overhead wide`), prop physics (`close-up tracking hand on prop`, `insert shot of prop change`), or reaction (`medium push-in`). Note: `locked-off`/`tripod` are banned in legacy v4 (`R14-B`) ONLY; Schema v7 explicitly requires `locked_tripod` (`>= 35%`).
