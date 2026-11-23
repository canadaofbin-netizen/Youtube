---
trigger: model_decision
description: "Load when authoring episode titles, Schema v8 2-paragraph viewer descriptions, hashtags, or metadata.json packaging (R8-R10, R60, R68-D)."
---

# Metadata Contract & `R68-D` Descriptions (`R8–R10`, `R68-D`)

Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | Constants: [production_constants.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/production_constants.md) | Code: [`pipeline/publish.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/publish.py)

## R8–R10 & R68-D — Title, Plain Viewer Description & Hashtags
- **R8 Title**: `en-US` (`TITLE_DESCRIPTION_LANGUAGE_CODE`). `neuro_diorama` uses a 5-Archetype US Paradox Title (`R60`: `<= R68_TITLE_MAX_CHARS` `55` chars / `4–8` words on `v8`; `<= TITLE_MAX_CHARS_DIORAMA` on `v7`), zero all-caps spam, zero claims beyond verified DOI.
- **R9 & R68-D Description**:
  - `v7`/legacy uses `DESCRIPTION_EDITORIAL_TEMPLATES` (`publish.py`): 1-line hook, plain mechanism, `https://doi.org/<doi>`, `AI_DISCLOSURE_SENTENCE` (`R4`), `#Shorts`.
  - Non-frozen `Schema v8` (`R68-D`) uses `format_v8_viewer_story_description`: `55–135w` (`R68D_DESCRIPTION_WORD_RANGE`) across **2 plain declarative paragraphs** + closing line `Research: <Author> et al., <Institution> (<Year>).` (`0` hashtags, `0` raw DOIs, `0` `—`/`;`/bullets/subheaders/`R68D_BANNED_AI_CLICHES`; Studio `ai_content_declaration = True` kept).
  - **R88-A & R89 Archival Credits**: When `direct_insert_cc_by` inserts appear, append `Image credit: <Author>, <License Label> (<URI>).` (`R88-A`, `03_visuals/archival_inserts_manifest.json`) and/or `Video credit: Adapted from <Lead Author> et al., <Journal> (<Year>), <Supp. Movie ID>, CC BY 4.0 (<URI>) — cropped & muted (<Article URL>).` (`R89`, `03_visuals/archival_videos_manifest.json`) right after `Research: ...` (`0` credits for `PD/CC0`).
  - Author `debate_question` / `pinned_comment` as 1 casual everyday `?` viewer question (`0` DOI, `0` `"My bet:"`, `0` `—`).
- **R10 Hashtags**: Starts with `#Shorts` and `#Neuroscience` + pillar/topic tags in `metadata.json` (`0` hashtags inside `v8` `viewer_description` body).
