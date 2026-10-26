# Rule: Master QA Loop & Video Validation Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)

Gates enforce rules owned elsewhere; this file owns only the gate definitions (R18, R18-B), delivery (R25) and the quality lock (R37).

---

## R18 — Master QA Gates G1–G12
Run by `ScriptingStage.validate_qa_gates` (`pipeline/scripting.py`) → `02_script/qa_report.json` and `05_assembly/master_qa_report.json`; all must pass (`all_gates_passed: true`) before assembly or upload.

**Prompt lock:** every prompt/narration check delegates to `flow_prompt_builder.validate_flow_prompts` and `flow_prompt_builder.validate_narrations` (`[]` = pass). No gate re-implements those checks.

| Gate | Checks | Owner rule |
|---|---|---|
| G1 word count & timing | `validate_narrations` budget (per clip, per script); final duration within `FINAL_SHORTS_DURATION_MIN_SEC..MAX_SEC`; audio not truncated | R2, R43-B |
| G2 hook | setup/symptom narration states a concrete, counter-intuitive behaviour | R42 |
| G3 crisis | failure/crisis narration states the failed attempt and the biological cause | R42 |
| G4 anatomy | narration traces the anatomical pathway (real region names, no mechanical metaphor) | R3, R38 |
| G5 conclusion opener | final clip opens with "Which proves" or "Which is why" | R26 |
| G6 tone | zero first-person pronouns, zero clickbait terms | R15 |
| G7 setting split | real_env / pull_out prompts name the real environment + porcelain mannequin; drill_down / brain_void prompts name the matte-white brain on bright studio; colour words follow the 4-point code; no `#hex` | R14-A, R21 |
| G8 banned tokens | zero `BANNED_PROMPT_TOKENS` / `BANNED_STYLE_TOKENS` | R14-B |
| G9 camera | exactly one camera move per clip; no angle labels, loop or tripod wording | R14-D |
| G10 voice line | every prompt ends with `Voice: Consistent deep male baritone documentary narrator. Spoken narration: "…"`; no `Audio:` | R13, R40-A |
| G11 pivot & memes | pivot clip contains "Instead of"; both signature memes present in their roles | R26, R24 |
| G12 zero dead air | vocal windows bounded by the R41 envelope; no mid-sentence clipping; inter-clip silence < `DEAD_AIR_FLOOR_SEC` | R41, R43-B |

## R18-V5 — Prompt System v5 Production Gate (before Gear 3)
`pipeline/prompt_quality_v5.validate_production_v5(plan, narrations, clips)` must return `[]` (`main.py prompt-gate --dir <project or draft>`). It wraps G1/G5/G8/G10/G11 (via the v4 validators) and adds:

| Tag | Checks | Owner rule |
|---|---|---|
| `[scene]` | must-have scenes present, exactly one iconic, iconic in clip 1..`ICONIC_SCENE_MAX_CLIP`, every must-have mapped to a clip | R46 |
| `[acting]` | every reenactment clip has a body verb, a prop physical change, no static-only acting | R47 |
| `[brain]` | brain clips ≤ mode cap; none in BEHAVIORAL_PSYCH; canonical regions only; narration names the on-screen region; region fields not blended | R45, R48 |
| `[plain]` | reading grade, jargon cap, anatomy cap + gloss, viewer link, no Step openers / paper voice | R15 v5 |
| `[tts]` | TTS-safe narration | R49-T |
| `[keyshot]` | iconic scene has `key_visual`; a clip with that `scene_id` contains every `must_show` token group, in clip 1..`ICONIC_SCENE_MAX_CLIP` | R46-K |
| `[fact]` | every number in the display narration exists in the linked dossier (`check_narration_facts`, run by `prompt-gate`) | R44-D |

**Reference gate (Gear 3, before the first clip)**: `main.py ref-qa --project <id>` → `pre_generation_ready: true` = every image passes Q1–Q10 + Q11 semantic review and was generated for the pack (provenance `flow_image_generation` / `gemini_image_generation`). `--audit` only inspects finished clips and can never pass this gate (R51). **Blueprint gate**: `main.py packets --project <id>` exits 0 only when `validate_scene_blueprints` returns `[]` (R52).

Research gate (before Gear 2): `validate_dossier(slug)["ready"]` incl. `depth_standard` (R44, R44-D). Voice gate (Gear 3/4): `evaluate_f0_series` semitone limits, then R49 fallback. Back-catalogue audit: `main.py audit-prompts` → `BCI_Shorts_Channel/reports/prompt_v5_score_sheet.md`.

## R18-B — Visual Browser Gates V1–V5
Saved under `03_visuals/flow_screenshots/` with `visual_qa_report.json`.

| Gate | Screenshot | Pass |
|---|---|---|
| V1 | `flow_gate_v1_prompt_approved.png` | 9:16 selected, credit dialog approved, builder prompt injected into `.ProseMirror` |
| V2 | `flow_gate_v2_first_clip_rendered.png` | first clip rendering (`<video>` active) |
| V3 | `flow_gate_v3_all_clips_timeline.png` | all N clips rendered |
| V4 | `flow_gate_v4_export_ready.png` | real `.mp4` streams extracted (static-image blocker active) |
| V5 | `flow_gate_v5_ingested_clips.png` | `clip_1..clip_N.mp4` ingested, each ≥ `MIN_CLIP_SIZE_BYTES`, unique SHA-256 + dHash, ASR-ordered (R39) |

## R25 — Single MP4 Delivery
One deliverable per project: `05_assembly/final_shorts_1080x1920.mp4` with `probe_report.json`, `video_autopsy_report.json`, `master_qa_report.json`. No partial or duplicate renders.

## R37 — 6-Guard Quality Lock
| Guard | Mechanism | Code |
|---|---|---|
| 1 Provenance | `03_visuals/flow_provenance_receipt.json` (`flow_project_url`, `tab_target_id`, clip SHA-256) | `FlowProjectSubagentWorker.validate_provenance_receipt` (`pipeline/flow_browser.py`) |
| 2 Uniqueness | 64-bit dHash; clips with distance ≤ `MAX_PERCEPTUAL_DHASH_HAMMING_DISTANCE` across projects are rejected | `VideoAutopsyEngine` |
| 3 Zero shortcut | static scan for synthetic/slideshow/clone code paths; `ALLOW_EXTERNAL_PAID_APIS` / `ALLOW_STATIC_IMAGE_VIDEO_FALLBACK` False | `run_preflight_qa` |
| 4 Quarantine | unverified projects isolated in `BCI_Shorts_Channel/projects_quarantine_pending_flow/` | storage / QA |
| 5 Visual audit | V1–V5 pass (R18-B) | `run_browser_generation_qa` |
| 6 Isolation & cap | 1 topic = 1 subagent = 1 Naver Whale tab; ≤ `FLOW_MAX_PARALLEL_BATCH_SIZE` per batch | `allocate_dedicated_flow_project_tab`, `flow-parallel` |

Flow defense layers (inside Guards 1/5): `.ProseMirror` injection → `<video>` poll every `FLOW_RENDER_POLL_INTERVAL_SEC` up to `FLOW_RENDER_TIMEOUT_SEC` → static-image blocker → `MediaIntegrityValidator` → ASR ordering (R39).

## Executable QA Suite (`python -X utf8 main.py qa`)
| Stage | Function (`pipeline/qa_gates.py`) | Checks |
|---|---|---|
| 1 Pre-flight | `run_preflight_qa` | paid-API lock, Guard 3, Guard 6 cap, contract constants (`production_constants.md`), FFmpeg / OpenCV / Whale binaries |
| 2 Browser generation | `run_browser_generation_qa` | provenance uniqueness, V1–V5 |
| 3 Media integrity | `run_media_integrity_qa` | `MediaIntegrityValidator` + `VideoAutopsyEngine`: duration bounds, `MIN_FRAME_DIFF_THRESHOLD`, `MIN_OPTICAL_FLOW_THRESHOLD`, no clipping / truncation, zero cloned frozen end-frames, word-level subtitle sync drift `<= 0.15s`, zero overlapping subtitle events (`overlapping_events_count == 0`), zero unconverted multi-word numbers in subtitles (`unconverted_number_words_count == 0`), voice F0 continuity / `am_fenrir` R41 broadcast chain, bidirectional spoken-vs-script content word match |
| 4 Intent & content | `run_intent_content_qa` | G1–G12, three distinct thumbnails (R31), R16 subtitle layout, R36 localization |

Entry point: `run_full_executable_qa`.
