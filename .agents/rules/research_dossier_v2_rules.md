---
trigger: model_decision
description: "Load when creating, validating, or auditing Schema v2 research dossiers (dossier validate --require-v2), verifying behavioral/neuro DOIs, or running 4-Gate archival media audits (R44, R44-D, R44-M)."
---

# Schema v2 Research Dossier & 4-Gate Media Audit (`R44`, `R44-D`, `R44-M`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Skill: [youtube-research](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/skills/youtube-research/SKILL.md) | Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py)

## R44 — Schema v2 Topic Dossier (`BCI_Shorts_Channel/research_dossiers/<slug>/`)
Gate before Gear 2: `main.py dossier validate --slug <slug> --require-v2` (`validate_dossier(..., require_schema_v2=True)["ready"] == True`).
- `dossier.json`: `schema_version: 2`, `everyday_domain` (`EVERYDAY_LONGFORM_DOMAINS`), `three_layer_formula` (`everyday_problem`, `psychology_experiment`, `neuroscience_mechanism`, `psychology_studies`, `neuroscience_studies` with `year >= DOSSIER_NEURO_MODERN_MIN_YEAR`), `debate_ignition` (`prebunk_myth`, binary `open_verdict_question`, `offcenter_creator_bet` passing `validate_debate_pinned_comment_line1`), `visual_mode` + `visual_mode_reason`, `primary_case`, `core_facts`, `wow_facts` (`>= 3`), `misconceptions`, `everyday_hooks`, `linked_projects`, `spatial_arrow_eligible` (`R87-A`).
- `01_sources.json`: Verified Behavioral Psych DOI + distinct verified `>= DOSSIER_NEURO_MODERN_MIN_YEAR` Neuro/Imaging/BCI DOI (`verify_doi`), replications, critiques (`>= DOSSIER_MIN_SOURCES`, `>= DOSSIER_MIN_FOLLOWUP_SOURCES`).
- `02_master_story.md`: Narrative (`>= DOSSIER_MIN_STORY_CHARS`): cold open -> world before -> people -> method -> exact results -> critique -> aftermath -> takeaway.
- `03_visual_reference.json`: Scenes (`era`, `layout` `>= DOSSIER_MIN_ICONIC_POSITIONS`, `props` `>= DOSSIER_MIN_ICONIC_PROPS`, `actions`, `reactions`, `recognition_hook`, `key_visual`), 1 `iconic: true`.
- `04_media_refs.json`: `suitability_schema_version: 2`, `reenactment_track` (`track_a` | `track_b`), `primary_reenactment_media_id`, `>= DOSSIER_MIN_MEDIA` items with `>= DOSSIER_MIN_MEDIA_TIMECODES` `{t, what}`, plus `reenactment_section` (`MM:SS-MM:SS`) for Track A.
- `05_plain_language.json`, `06_brain_link.json` (`{}` when `BEHAVIORAL_PSYCH`), `07_longform_outline.json` (`>= 5` chapters + `shorts_extract`), `08_reenactment_edl.json` (Track A: `shot_count >= 3`, `sanitization_verified: true`, dHash + 5-gram hashes, `0` raw pixels).

## R44-D & R44-M — Depth & 4-Gate Media Suitability (`dossier audit-media`)
- **R44-D**: `>= DOSSIER_MIN_CORE_FACTS` `{fact, source_id}` mapped to `01_sources.json`; every subtitle number verified by `check_narration_facts` (`[fact]`); `>= DOSSIER_MIN_ANALYZED_MEDIA`.
- **R44-M (`evaluate_media_reenactment_suitability` -> `MEDIA_SUITABILITY_CLASSES`)**: (1) Blocklist `MEDIA_REJECT_CHANNEL_PATTERNS` & era `< MEDIA_MIN_CINEMA_YEAR`; (2) Dark Void `> MEDIA_MAX_DARK_VOID_RATIO`; (3) Flat 2D slide/static vs 16mm B&W exemption (`MEDIA_BW_ARCHIVAL_SAT_MAX`, `MEDIA_BW_FRAME_P90_SAT_MAX`); (4) YuNet talking-head reject + `> MEDIA_MAX_UNWINDOWED_DURATION_SEC` -> `needs_section_window`.
