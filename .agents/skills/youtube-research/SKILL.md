---
name: youtube-research
description: Gear 1 case discovery (Crossref/ClinicalTrials DOIs) and Schema v2 research dossier builder (3-Layer Formula + Dual-Track archival media audit + R67/R89 provenance).
---

# youtube-research (AI-Only Spec)

SSOT: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) | [research_dossier_v2_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/research_dossier_v2_rules.md) | [knowledge_hub_asset_manifest_rules.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/knowledge_hub_asset_manifest_rules.md) | Code: [`pipeline/research_dossier.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/research_dossier.py)
Interpreter: `/home/canadaofbin/hermes-venv/bin/python -X utf8`

## 1. Discovery & Duplicate Lock (`R1`, `P1`, `R34`)
- Scan recent papers: `main.py news-radar --days 14 --max-candidates 5` or `scripts/run_topic_radar.py`.
- Verify zero overlap in case, Behavioral Psych DOI, or `>=2015` Neuro DOI against `BCI_Shorts_Channel/projects/*/06_publish/metadata.json` and `BCI_Shorts_Channel/database/published_legacy_topics.json`.

## 2. Schema v2 Dossier Build (`BCI_Shorts_Channel/research_dossiers/<slug>/`)
1. **Init**: `main.py dossier init --slug <slug> --topic "<title>" --pillar <id> --everyday-domain <sleep|habits|memory|anxiety|relationships> --mode HYBRID`
2. **3-Layer Formula (`01_sources.json` + `dossier.json.three_layer_formula`)**:
   - Layer 1: Everyday viewer domain (`sleep` / `habits` / `memory` / `anxiety` / `relationships`).
   - Layer 2: Verified Behavioral Psychology Experiment DOI (`main.py dossier doi --doi <doi>` or `primary_historical`).
   - Layer 3: Verified `>= 2015` Neural Circuit / fMRI / EEG / Two-Photon / BCI DOI.
   - Breadth: `>= 6` verified sources (incl. replications + `>= 1` critique/myth check) and `>= 8` `core_facts` with `source_id`s. Every script number must trace to a `[fact]`.
3. **Dual-Track Archival Audit (`04_media_refs.json`, `R44-M`, `R88-A`, `R89`)**:
   - `main.py dossier yt-search --query "<experiment> archival footage"`
   - `main.py dossier yt-analyze --slug <slug> --url <url> --media-id <id> [--section "*mm:ss-mm:ss"]`
   - `main.py dossier audit-media --slug <slug> --write` (4-Gate CV/YuNet/transcript classifier -> `track_a` vs `track_b`).
   - If `R89` real experiment / supplementary movie fits (`CC BY 4.0` from `PLOS`/`eLife`/`PMC OA`/`Nature Comm` or `17 U.S.C. § 105` intramural federal work), audit strictly via `audit_archival_video_eligibility` (`0` Fair Use, `0` `CC BY-NC/ND/SA`, `0` third-party caption carve-outs, `5fps` `YuNet < 0.42`, `min_frame_diff >= 0.30`; stage `03_visuals/archival_videos_manifest.json`).
   - Restricted human/classic archival footage routes to `track_a` (`R67` `08_reenactment_edl.json` / `main.py reenact-refs` sanitized reenactment, `0` source pixels reused).
4. **Scene Bible & `R87-A` Spatial Contrast Spec (`03_visual_reference.json`)**: Era, layout/facing, props (`name`, `period_detail`, `physical_behavior`), action verb chain, `recognition_hook`, `key_visual`, one `iconic` scene, plus explicit `spatial_arrow_eligible: bool` (`True` only for physical navigation/doorway/maze with `spatial_contrast_spec`; `False` routes to `Category K` prop/brain contrast).
5. **Story, Plain Language & Brain Links**:
   - `02_master_story.md` (`>= 6,000` chars, 8 sections) + `dossier.json.debate_ignition` (`prebunk_myth`, binary `open_verdict_question`, `offcenter_creator_bet` `<= 45` chars).
   - `05_plain_language.json`, `06_brain_link.json` (canonical `pipeline/anatomy_map.py` regions), `07_longform_outline.json` (`shorts_extract`).
6. **Gate & Seed**:
   - `main.py dossier validate --slug <slug> --require-v2` -> `ready: true`.
   - `main.py dossier seed --slug <slug> --profile neuro_diorama --style-profile expressive_25d_v8` -> hand off to `youtube-script`.
