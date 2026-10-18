# Rule: Camera Choreography Protocol

Parent Master Index: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Scene/setting rules: [visual_prompt_spec.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md)

Scope: the camera sentence inside each Flow prompt scene. Trimming, holds and speed belong to [audio_assembly_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/audio_assembly_rules.md).

---

## R14-D — Per-Role Camera Vocabulary
One clean camera move per clip, written as one sentence in plain film language. Roles come from `clip_roles(n)`; the builder stores the chosen move in `clip.camera_move`.

| Role | Canonical move | Allowed vocabulary | Golden phrasing (Capgras) |
|---|---|---|---|
| setup | wide establishing shot, camera smoothly tracks forward toward the subject | wide shot, establishing, tracks forward, glides toward | "Wide establishing shot, camera smoothly tracks forward toward his face." |
| symptom | close-up, slow orbit around the head revealing the colour points through the cranium | close-up, slowly orbits, circles, revealing | "The camera slowly orbits his head, revealing the brain through the translucent frosted-glass cranium" |
| failure | smooth lateral tracking between figures | tracks sideways, lateral track, slides between | "The camera tracks smoothly sideways between them, capturing the distance." |
| crisis | dive through the frosted-glass cranium → glide over gyri/sulci → zoom into the target | dives through, glides over, zooms into | "The camera dives smoothly through … It glides over the cortex and zooms into the temporal lobe" |
| pivot | smooth orbit around the structures, push in on the compensatory route | orbits, pushes in | "the camera smoothly orbits two separate structures … slowly pushes in on the glowing amber-gold route" |
| mechanism / step1 / step2 | macro tracking along the signal path | macro view, follows, tracks the flowing signal, orbits the gap | "The camera tracks the flowing signal from back to front." |
| step3 | pull back to reveal the full circuit | pulls back to reveal, the full brain turns | "The camera pulls back to reveal the whole circuit" |
| breakthrough | pull out of the brain through the cranium into the real environment | pulls out, back through the cranium, into the room | "The camera pulls smoothly out of the brain, back through the translucent frosted-glass cranium, into the hospital room." |
| conclusion | slow pull-back rising to an elevated wide shot | pulls back, rises, elevated angle | "The camera slowly pulls back and rises to an elevated angle." |

## Composition Rules
| Rule | Requirement |
|---|---|
| One move | Never chain conflicting moves (orbit + whip-pan + dolly) or list multiple angles in one clip. |
| No labels | No `Camera Angle N`, `Shot N`, `Angle Group` labels in prompts. |
| Continuity | Adjacent clips hand off spatially: real_env → drill_down enters the cranium; brain_void clips stay inside; pull_out exits to the same environment as setup. |
| Anatomical anchoring | Name brain regions by anatomy (temporal lobe, ventral surface, behind the forehead), never by screen position (upper-left, upper-right). |
| Ending | Conclusion is an independent elevated wide scene (R19); it does not return to the clip 1 framing. |
| Banned camera words | locked-off, tripod, dolly-percentage push-ins, decoupled kinetic, seamless loop, loop back (see R14-B). |
