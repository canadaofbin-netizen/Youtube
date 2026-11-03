---
name: bci-episode-production
description: Fully automatic, no-confirmation production of ONE new ALL ABOUT BRAIN Schema v7 neuro_diorama episode, from a topic (or an existing dossier slug) to a QA-passed final 1080x1920 MP4 - duplicate check, research dossier, 6-Act script with the R57-H2 3-sentence cold-open and re-hooks, visual_plan, prompt-gate, Google Flow clip generation, dynamic_rush_v7 assembly, and the full QA chain (verify, autopsy, episode-qa, posthoc-qa, prosody-qa). Use when the user asks to "make a video / 영상 만들어줘 / 다음 에피소드 제작". Upload is NOT included (use youtube-studio-manager).
---

# BCI Episode Production (one topic → final MP4, fully automatic)

Master: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Rules: [neuro_diorama_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/neuro_diorama_rules.md) (R56–R66, R57-H2, R63-P)

**Golden cold-open + prosody + audio reference (approved 2026-10-31):** `BCI_Shorts_Channel/projects/diorama_01_hm_lab_B_dynamic` — read its `02_script/script.json` and `03_visuals/visual_plan.json` before authoring. Every new episode must match its structure, pacing and audio while using the default `porcelain_cinematic_v7` visual skin (R66; pass `--style-profile lowpoly_pastel_v7` only when explicitly requested).

## Operating mode
- **No confirmation checkpoints.** Run all steps end to end; only stop and report if a step is blocked (missing credentials/browser, network failure, or a gate that still fails after the fixes below).
- **Never loosen a QA threshold** to pass. Fix the script / plan / clips instead.
- **Never touch published projects** (`06_publish/upload_receipt.json` present) — `diorama-episode` refuses them.
- Python: `/home/canadaofbin/hermes-venv/bin/python3 -X utf8 main.py …` (has cv2, faster_whisper, edge-tts). Run long steps as background tasks.
- Send a short Korean progress note to the user at each step boundary (1–2 lines), and a final report.

## Step 0 — Pick the topic & IDs
1. If the user gave a topic, use it; otherwise pick the next unproduced spec from `DIORAMA_BATCH_20_SPECS` in `pipeline/diorama_batch_orchestrator.py`, balancing pillars (P1, R20).
2. Duplicate check (R1, R34): the topic/DOI must not already exist in a published project (`grep -l <doi> BCI_Shorts_Channel/projects/*/06_publish/metadata.json`) and no existing project uses the same case.
3. Choose `slug` (snake_case case name), `project_id` = `diorama_<NN>_<short_slug>` (next free NN), `pillar` (P1 id).

## Step 1 — Research dossier (Gear 1, R44 / R44-D)
- If `BCI_Shorts_Channel/research_dossiers/<slug>/dossier.json` is missing or `dossier validate` fails, follow [bci-deep-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-deep-research/SKILL.md).
- Must end with: `main.py dossier validate --slug <slug>` → ready, verified primary DOI in `01_sources.json`, every narration number traceable to a `[fact]`.

## Step 2 — Script + visual plan (Gear 2)
1. `main.py dossier seed --slug <slug> --profile neuro_diorama` → JSON seed (`style_profile: "porcelain_cinematic_v7"` default; save draft under `research_dossiers/<slug>/diorama_v7_porcelain/` or `diorama_v7/`).
2. Hand-author `script.json` + `visual_plan.json` in that draft dir per [bci-script-gen](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/bci-script-gen/SKILL.md) and R66 (`PorcelainV7PromptComposer` in `pipeline/depiction_rules.py`). Checklist:
   - [ ] 6 Acts, total words within `DIORAMA_WORD_COUNT_MIN..MAX` (`DIORAMA_WORD_COUNT_MIN..DIORAMA_US_WORD_COUNT_MAX` on `dynamic_us_v7`), every sentence `<= DIORAMA_V7_SENTENCE_WORDS_MAX` (`<= DIORAMA_US_SENTENCE_WORDS_MAX` on `dynamic_us_v7`, Flesch-Kincaid `<= DIORAMA_V7_MAX_FK_GRADE`), 100% US English, TTS-safe.
   - [ ] **R57-H2 cold-open:** S1 myth-flip/paradox ending `!` (`<= DIORAMA_V7_COLD_OPEN_S1_MAX_WORDS` words) → S2 `Yet/But …` contrast (`<= DIORAMA_V7_COLD_OPEN_S2_MAX_WORDS` words) → S3 rotating case stamp from `DIORAMA_COLD_OPEN_S3_BANK` + matching chapter headline.
   - [ ] Signature hooks from rotating Anti-Clone banks (`DIORAMA_CRISIS_BEAT_BANK`, `DIORAMA_MECHANISM_PIVOT_BANK`, `DIORAMA_EUREKA_REVEAL_BANK`, `DIORAMA_TAKEAWAY_BRIDGE_BANK`, `DIORAMA_MIDPOINT_REHOOK_BANK` — zero opener reuse across `DIORAMA_ADJACENT_OPENER_WINDOW` adjacent episodes).
   - [ ] **R57-R re-hooks:** a `?`, stamp line, or midpoint re-hook at least every ~6 sentences (P10 gap `<= PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC`); midpoint `?` across Act 3→4.
   - [ ] Every number paired with an everyday analogy; real names; glossed anatomy; no `Imagine…`.
   - [ ] Voice & prosody: `voice_preset` from `DIORAMA_VOICE_PRESETS` (`DEFAULT_DIORAMA_VOICE_PRESET` = `andrew_v7`; `DEFAULT_REENACTMENT_VOICE_PRESET` = `emma_v7`) and `prosody_mode` (`DIORAMA_V7_PROSODY_MODE` = `dynamic_rush_v7` or US `45+` `DIORAMA_V7_US_PROSODY_MODE` = `dynamic_us_v7`); optional `emphasis_words`.
   - [ ] `visual_plan` (`style_profile: "porcelain_cinematic_v7"`): 1:1 zero-reuse clips covering every sentence (`>= DIORAMA_TARGET_CUT_MIN`), `PORCELAIN_V7_VISUAL_GRAMMARS` (`porcelain_hands_closeup`, `porcelain_pov_hands`, `porcelain_fullbleed_world`, `porcelain_cutaway_section`, `porcelain_literal_analogy`, `porcelain_living_brain`) & v7 camera ratios, clothed articulated matte-white porcelain figures/hands in photorealistic high-key environments, **Contained Living 4-Color 3D Brain** (`PORCELAIN_V7_BRAIN_RENDER_MODES`: `cortical_vascular_whole`, `sagittal_coronal_cutaway`, `frosted_glass_subcortical_xray`, `bounded_micro_channel`; strictly enclosed `clear cyan-blue` / `deep crimson-red` / `warm amber-gold` / `luminous pearl-aqua` fluid or `champagne-white` impulse; zero `"bioluminescent green"`, `"particles"`, `"mist"`, `"slime"`), positive phrasing only, no plaque-trigger nouns (plaque, sign, newspaper, textbook…).
   - [ ] **R65 thumbnail & cover frame:** author `visual_plan.thumbnail` (`hook_text` `<= THUMB_HOOK_MAX_WORDS` words / `<= THUMB_HOOK_MAX_CHARS` chars uppercase complementing the title, `cover_sentence_index: 3`, `cover_brief`) and set the `chapter_headlines` entry at `sentence_index: 3` to the exact `hook_text`.
   - [ ] `metadata.json` title = R60 5-archetype US title (`<= TITLE_MAX_CHARS_DIORAMA`).
3. `main.py prompt-gate --dir BCI_Shorts_Channel/research_dossiers/<slug>/diorama_v7_porcelain` → `passed: true, issues: []`. Fix and repeat until clean.

## Step 3 — Precheck (no Flow credits)
```bash
main.py diorama-episode --slug <slug> --project <project_id> --pillar <pillar> [--voice-preset <id>] --precheck-only
```
Syncs the draft into `projects/<project_id>/`, re-runs prompt-gate + fact trace + paradox title + plaque lock, and synthesizes the TTS master clock (must land in `DIORAMA_V7_DURATION_MIN_SEC..SHORTS_HARD_CEILING_SEC`). For **R67 Source-Conditioned 1:1 Porcelain Reenactment** episodes, run `main.py reenact-extract --source <url_or_mp4> --slug <slug> --project <project_id>` → `main.py reenact-refs --project <project_id> --slug <slug>` → `main.py ref-qa --project <project_id>` before Flow generation.

## Step 4 — Generate + assemble + full QA (Gears 3–4)
Preconditions: Naver Whale running with CDP on port 9222 and logged in to Google Flow (R5). If not reachable, stop and ask the user to open it.
```bash
main.py diorama-episode --slug <slug> --project <project_id> --pillar <pillar> [--voice-preset <id>] [--engine auto] [--tabs 5]
# Or for R67 Source-Conditioned Porcelain Reenactment (auto-purges /tmp/aab_reenact + runs RQ1-RQ5):
main.py reenact-produce --slug <slug> --project <project_id> --pillar <pillar> --voice-preset emma_v7 --prosody-mode dynamic_us_v7
```
This runs: 5-tab sharded Flow generation → `finalize_and_verify_diorama_project` (assembly with `dynamic_rush_v7` native per-gear TTS, true-peak-guarded mux, DQ1–DQ12, R64 post-hoc, autopsy, **prosody-qa P1–P10**, asset manifest, KB sync, `verify`) with up to 2 auto-heal rounds (EDL-only rebuild or targeted clip regeneration). Expect ~1–3 h (Flow) + ~20 min (TTS + assembly; edge-tts ≈ 8 min cold).

## Step 5 — If a gate still fails
| Failure | Fix (no threshold changes) |
|---|---|
| P2 hook timing | shorten S1/S2 (cold-open), re-run Step 3–4 assembly only: `main.py diorama-assemble --project <id> --force --posthoc-qa` |
| P10 re-hook gap | rewrite an existing sentence in the gap into a re-hook (keep sentence count so clip indices stay aligned) |
| P6 ASR by gear | inspect low sentences; respell hard words in TTS-safe form |
| P7 / autopsy audio | check `video_autopsy_report.json`; never bypass the true-peak guard |
| R64 / DQ weak cuts | `main.py diorama-flow --project <id> --clips <n,…>` then `main.py diorama-recut` or re-assemble |
| Flow credits exhausted | `--engine zero-credit` |

## Step 6 — Deliver & report
- Final MP4: `BCI_Shorts_Channel/projects/<project_id>/05_assembly/final_shorts_1080x1920.mp4` (archive copy in `Completed_Psychology_100_Shorts/final_shorts_<project_id>.mp4`). Copy it to the artifact directory and embed it in the report.
- Report in Korean: title, duration, cut count, gate table (prompt-gate, verify, autopsy, episode-qa, posthoc mean clarity, prosody-qa x/10, LUFS / dBTP), and anything that needed manual fixing.
- Clean temporary files (`/tmp/aab_*`, previews). Hand off to [youtube-studio-manager](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-studio-manager/SKILL.md) only if the user asks to upload.

## Pitfalls
- gdrive FUSE is slow: avoid `du`, bulk `rm -rf`, or many small writes; use `rclone purge` for big deletions.
- Validate narration text in Python files, not inline `python -c` (apostrophes break shell quoting).
- If the visual plan's clip indices are tied to sentence indices, don't insert or delete sentences after clips are generated — rewrite in place.
