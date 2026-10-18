# Rule: Content Quality & Narrative Architecture Protocol

Parent Master Index: [AGENTS.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Numbers: [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) · Validator: `flow_prompt_builder.validate_narrations`

Scope: what the narration says. Visuals → [visual_prompt_spec.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md); title → [channel_operations_rules.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/channel_operations_rules.md) (R8); pinned comment and AI disclosure → [youtube_studio_operations.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/youtube_studio_operations.md) (R35, R4).

---

## R1 — Fact Accuracy, DOI & Single-Case Consistency
| Rule | Requirement |
|---|---|
| Source | At least one verified peer-reviewed source (Nature, Science, Cell, NEJM, Lancet, Neuron, Brain, JAMA, Proc. R. Soc. B, PubMed-indexed) with explicit `doi` in `01_ideation/research_card.json` and `06_publish/metadata.json`. |
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
| Speaking rate | `NATIVE_FLOW_WPS` requested from Flow; `EFFECTIVE_WPS` after `AV_SPEEDUP_FACTOR` |
| Final length | ≤ `FINAL_SHORTS_DURATION_MAX_SEC` |

## R42 — Deep-Mechanism Role Spine
Role order per clip count = `CLIP_ROLE_SEQUENCES` (listed in [production_constants.md](file:///g:/My%20Drive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md)). Narration starts at frame 0 of every clip; no silent hook.

| Role | Narrative job |
|---|---|
| setup | Who / when / where: era, institution, subject, inciting event. |
| symptom | The bizarre, concrete behaviour. |
| failure | What earlier attempts (family, doctors, willpower) tried and why it failed. |
| crisis | The exact anatomical cause ("Here is what went wrong" is allowed). |
| pivot | The paradigm flip — **must contain "Instead of"**. |
| mechanism / step1–3 | Physical step-by-step chain along the signal path. |
| breakthrough | The concrete experimental proof. |
| conclusion | Universal takeaway, independent of clip 1. |

## R26 — Role Openers (decision D2)
| Role | Opener |
|---|---|
| pivot | Contains "Instead of". |
| mechanism / step1–3 | May open with "Step one/two/three" or "Here is how it works"; both allowed. |
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

## R2-B — Narrative Archetypes (`--style`)
`ALLOWED_NARRATIVE_STYLES` (`auto` resolves via `PILLAR_DEFAULT_STYLE_MAP`): `case_file`, `delusion_museum`, `forbidden_lab`, `icon_autopsy`, `caveman_brain`, `chronicle_cutaway`. The archetype changes framing and vocabulary only; the role spine (R42) is fixed.
