---
name: youtube-research
description: Gear 1 case discovery (Crossref/ClinicalTrials DOIs) and Schema v2 research dossier builder (3-Layer Formula + Dual-Track archival media audit + R67 quarantine EDL).
---

# youtube-research (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [research_dossier_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_rules.md) | Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py), [`pipeline/researcher.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/researcher.py)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Discovery & Duplicate Lock (R1, P1, R34)
- Scan breaking papers: `main.py news-radar --days 14 --max-candidates 5` or `main.py research --query "<topic>" --pillar <id>`.
- Verify zero overlap in case, Behavioral Psych DOI, or `>=2015` Neuro DOI against `BCI_Shorts_Channel/projects/*/06_publish/metadata.json`.

## 2. Schema v2 Dossier Build (`BCI_Shorts_Channel/research_dossiers/<slug>/`)
1. **Init**: `main.py dossier init --slug <slug> --topic "<title>" --pillar <id> --everyday-domain <sleep|habits|memory|anxiety|relationships> --mode HYBRID`
2. **3-Layer Formula (`01_sources.json` + `dossier.json.three_layer_formula`)**:
   - Layer 1: Everyday viewer domain (`sleep` / `habits` / `memory` / `anxiety` / `relationships`).
   - Layer 2: Verified Behavioral Psychology Experiment DOI (`verify_doi` via Crossref or `primary_historical`).
   - Layer 3: Verified `>= 2015` Neural Circuit / fMRI / EEG / Two-Photon / BCI DOI (`verify_doi`).
   - Breadth: `>= 6` verified sources (incl. replications + `>= 1` critique/myth check) and `>= 8` `core_facts` with `source_id`s. Every script number must trace to a `[fact]`.
3. **Dual-Track Archival Audit (`04_media_refs.json`, R44-M)**:
   - `main.py dossier yt-search --query "<experiment> archival footage"`
   - `main.py dossier yt-analyze --slug <slug> --url <url> --media-id <id> [--section "*mm:ss-mm:ss"]`
   - `main.py dossier audit-media --slug <slug> --write` (4-Gate CV/YuNet/transcript classifier -> `track_a` vs `track_b`).
   - If `track_a` (R67): set `reenactment_section` (`MM:SS-MM:SS`) and run `main.py reenact-extract --source <url> --slug <slug> --section <MM:SS-MM:SS>` -> generates `08_reenactment_edl.json` (`shot_count >= 3`, `sanitization_verified: true`, zero source pixels reused; purge `/tmp/aab_reenact` after refs).
4. **Scene Bible (`03_visual_reference.json`)**: Era, layout/facing, props (`name`, `period_detail`, `physical_behavior`), action verb chain, reactions, `recognition_hook`, `key_visual`, one `iconic` scene.
5. **Story, Plain Language & Brain Links**:
   - `02_master_story.md` (`>= 6,000` chars, 8 sections) + `dossier.json.debate_ignition` (`prebunk_myth`, binary `open_verdict_question` `... or ...?`, 1st-person `offcenter_creator_bet` `<= 45` chars).
   - `05_plain_language.json` (jargon -> plain gloss -> everyday analogy).
   - `06_brain_link.json` (canonical `pipeline/anatomy_map.py` regions only; omit on `BEHAVIORAL_PSYCH`).
   - `07_longform_outline.json` (`shorts_extract {hook, core_experiment, twist}`).
6. **Gate & Seed**:
   - `main.py dossier validate --slug <slug> --require-v2` -> `ready: true`.
   - `main.py dossier seed --slug <slug> --profile neuro_diorama` -> hand off to `youtube-script`.
