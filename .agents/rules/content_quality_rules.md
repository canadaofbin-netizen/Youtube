# Rule: Content Quality & Narrative Architecture Protocol

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Validator: `flow_prompt_builder.validate_narrations`

Scope: what the narration says. Visuals → [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md); title → [channel_operations_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) (R8); pinned comment and AI disclosure → [youtube_studio_operations.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R35, R4).

---

## R1 — Fact Accuracy, DOI & Single-Case Consistency
| Rule | Requirement |
|---|---|
| Source | At least one verified peer-reviewed source (Nature, Science, Cell, NEJM, Lancet, Neuron, Brain, JAMA, Proc. R. Soc. B, PubMed-indexed) with explicit `doi` in `01_ideation/research_card.json` and `06_publish/metadata.json`. v5: all sources live in the topic's research dossier (`01_sources.json`, R44), DOIs verified with `verify_doi`. |
| One case | One video = one case, one cast, one DOI. Never blend cases (e.g. the historical Capgras patient with Ramachandran's patient DS). |
| Cast match | Names, era, relations and genders in narration and `visual_plan.cast` match the cited paper (DS's **mother and father**, not a husband). |
| Claims | Every quantitative claim (rates, response measures) is stated as the paper reports it; no invented numbers. |

## R2 — Word Budget & Clip Count
| Item | Constant |
|---|---|
| Clip count | `CLIP_COUNT_MIN..CLIP_COUNT_MAX` (default `DEFAULT_CLIP_COUNT`) |
| Words per clip | `CLIP_WORDS_MIN..CLIP_WORDS_MAX` (decision D1) |
| Words per script | `script_word_range(n)`; global bounds `SCRIPT_WORD_MIN..SCRIPT_WORD_MAX` |
| Words per sentence | ≤ `MAX_WORDS_PER_SENTENCE` |
| Speaking rate | `NATIVE_FLOW_WPS` requested from Flow; `EFFECTIVE_WPS` after `AV_SPEEDUP_FACTOR`; per-clip duration (`"8s"` vs `"10s"`) dynamically routed by `compute_clip_target_duration` (`<= FLOW_CLIP_SAFE_MAX_SYLLABLES` syllables to prevent tail cutoff) |
| Final length | ≤ `FINAL_SHORTS_DURATION_MAX_SEC` |

## R42 — Deep-Mechanism Role Spine
Role order per clip count = `CLIP_ROLE_SEQUENCES` (listed in [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)). Narration starts at frame 0 of every clip; no silent hook.

| Role | Narrative job |
|---|---|
| setup | Who / when / where: era, institution, subject, inciting event. v5: cold open on the iconic scene (R46, clip 1–2). |
| symptom | The bizarre, concrete behaviour (or the shocking result of the experiment). |
| failure | What earlier attempts (family, doctors, willpower) tried and why it failed — or what everyone expected. |
| crisis | The exact cause (anatomical in NEURO / HYBRID, situational in BEHAVIORAL) ("Here is what went wrong" is allowed). |
| pivot | The paradigm flip — **must contain "Instead of"**. |
| mechanism / step1–3 | Physical step-by-step chain along the signal path. |
| breakthrough | The concrete experimental proof. |
| conclusion | Universal takeaway, independent of clip 1. |

## R26 — Role Openers (decision D2)
| Role | Opener |
|---|---|
| pivot | Contains "Instead of". |
| mechanism / step1–3 | Opens with natural documentary transitions ("First,", "Next," / "Then," / "From there,", "Finally,") or "Here is how it works"; avoid robotic "Step one/two/three" numbering. |
| conclusion | Opens with "Which proves" or "Which is why". |

## R24 — Dual Signature Memes
| Meme | Text | Placement |
|---|---|---|
| #1 crisis | "For your brain, this is a total nightmare." (pronoun/tense may adapt: "For his brain, this was a total nightmare.") | symptom or crisis clip |
| #2 awe | "The researchers were left completely stunned." | breakthrough clip; if the sequence has no breakthrough role, the mechanism or conclusion clip |

## R3 — Sensory-to-Brain Pathway in Words
- Narration follows the same chain as `visual_plan.signal_path` (organ → nerve → region → target), so voice and picture describe the same route.
- Every anatomical term is explained in plain words on first use ("the amygdala, his emotional alarm").
- No mechanical metaphors (gears, tape recorders, scales); the real anatomy is the story (R38).

## R15 — Tone & Readability
- US English, Grade 6–7 readability, documentary storyteller tone with punchy contrast.
- Zero first-person pronouns (I / we / my / our); second person ("your brain") allowed.
- Concrete action verbs; no clickbait phrases, no unexplained jargon.

### R15 v5 — Quantified plain-language guardrails (`pipeline/plain_language.py`, gate `validate_production_v5`)
The audience is the general public. The goal is "the world has things like this?!" and watching to the end — never reading a paper aloud.

| Guardrail | Limit |
|---|---|
| Reading level | Flesch-Kincaid ≤ `READABILITY_SCRIPT_FK_MAX` (script) and ≤ `READABILITY_CLIP_FK_MAX` (any clip) |
| Technical terms | ≤ `JARGON_TERMS_MAX` non-anatomy terms per script (lexicon, codes like CA3, acronyms like MIMO); explain it in the same clip with an everyday analogy |
| Brain-region names | ≤ `MAX_ANATOMY_TERMS_BY_MODE[mode]`, each glossed with its anatomy_map plain name ("the hippocampus, your memory maker") |
| Story share | Event + "what this means for you" carry the script; mechanism lines stay inside the mode's brain-clip budget (R45) |
| Viewer link | ≥ `SECOND_PERSON_CLIPS_MIN` clip speaks to "you / your" about everyday life |
| Banned | "Step one / two / three", paper voice ("participants demonstrated…"), researcher name-dropping beyond the case's key people, more than one statistic per clip |
| Source | Plain words and analogies come from the dossier's `05_plain_language.json` |

### R49-T — TTS-safe narration
`clip_narrations` are the **spoken** text: no digits (spell numbers and years out), no `! ? — – ; ( ) % & /`, no abbreviations with periods (Dr., U.S.). Use commas and periods for breath. `to_tts_text` normalizes; subtitles get compact numerals back through `to_display_text` (Display script vs TTS script). Reason: these characters make Flow / TTS narrators jump in pitch or read symbols aloud.

## R2-B — Narrative Archetypes (`--style`)
`ALLOWED_NARRATIVE_STYLES` (`auto` resolves via `PILLAR_DEFAULT_STYLE_MAP`): `case_file`, `delusion_museum`, `forbidden_lab`, `icon_autopsy`, `caveman_brain`, `chronicle_cutaway`. The archetype changes framing and vocabulary only; the role spine (R42) is fixed.
