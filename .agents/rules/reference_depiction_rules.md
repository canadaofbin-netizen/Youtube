# Rule: Dual-Track Reference Conditioning & Source-to-Prompt Protocol (`R51` / `R52` / `R66` / `R67`)

Parent Master Index: [AGENTS.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/AGENTS.md) · Composer Spec: [visual_prompt_spec.md](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/.agents/rules/visual_prompt_spec.md) · Code: [`pipeline/reference_image_qa.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/reference_image_qa.py), [`pipeline/porcelain_anchor_pack.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/porcelain_anchor_pack.py), [`pipeline/source_reenactment.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/source_reenactment.py), [`pipeline/scene_blueprint.py`](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/pipeline/scene_blueprint.py)

Single source of truth for reference still frames (`R51`), generation packets (`R52`), and the **Dual-Track `porcelain_cinematic_v7` Reference Conditioning Architecture (`R66-Anchor` + `R67`)**.

## 1. Schema v7 `porcelain_cinematic_v7` — Mandatory Dual-Track Reference Pack (`R66` / `R67`)
Every `porcelain_cinematic_v7` episode (`diorama-episode`, `diorama-batch`, `diorama-pipeline`, `reenact-produce`) compiles `6–9` `9:16` reference PNGs (`reference_image_specs.json`) via `populate_porcelain_reference_contract` and verifies `ensure_porcelain_reference_pack` (`0-credit` Google Flow `Image` `Nano Banana 2.1`, `x4` batch per prompt, `1 -> 2 -> 3` conditioning order) **before** sharded Flow video generation:
1. **Track A — `R67` Source-Conditioned Archival Reenactment (`reenactment_track = "track_a"`)**:
   - Used when `dossier audit-media` finds genuine archival experiment film (`suitable_track_a`, or `needs_section_window` clipped via `reenact-extract --section MM:SS-MM:SS`).
   - Extracts quarantined shot EDL + dHash/5-gram hashes in `/tmp/aab_reenact/<slug>/`, sanitizes human faces (OpenCV Zoo `YuNet` + CLAHE B&W/color + HSV skin) and colorful wall posters into `9:16` structural guides, translates them into porcelain `9:16` keyframes (`reenact-refs` / `porcelain-refs`), purges `/tmp/aab_reenact`, and enforces `RQ1–RQ5` (`reenact-qa`).
2. **Track B — `R66-Anchor` Scene-Bible Porcelain Pack (`reenactment_track = "track_b"`)**:
   - Used for pre-film historical cases (e.g. `1848` Phineas Gage, `1861` Broca, `1880` Cotard) or topics whose online videos are rejected by the 4-Gate suitability filter (TED dark stages, 2D slide explainers, talking-head monologues).
   - Synthesizes `ref_env_master.png` (`order 1`), `ref_cast_<role>.png` for all recurring roles (`order 2`, conditioned on `ref_env_master`), `ref_brain_master.png` (`order 1`, when `HYBRID` / `NEURO_BIOLOGY`), and `3–5` curated room-state `ref_anchor_01..05.png` (`order 3`, conditioned on `ref_env_master` + `ref_cast_<role>`, `scene_id = "LOC_<location_id>"`).
3. **Selective `~55–68%` Anchor-Binding Sweet Spot (Zero Wide-Frame Lock)**:
   - `porcelain_fullbleed_world` clips bind to the room anchor matching `(location_id, present_cast_start)` (`strict_room_continuity: True`).
   - `porcelain_living_brain` clips (except macro `bounded_micro_channel`) bind to `ref_brain_master.png`.
   - `porcelain_hands_closeup`, `porcelain_pov_hands`, `porcelain_cutaway_section`, `porcelain_literal_analogy`, and `outro` clips remain **unanchored (`reference_image = None`)** so macro inserts and literal analogies never inherit wide-room framing stiffness.
4. **Automated Batch Gate vs Explicit Human Semantic Review (`ref-qa`)**:
   - `inspect_reference_image_pack` / `main.py ref-qa` exposes `cv_all_passed` and `cv_pre_generation_ready` (`Q1–Q10` + provenance lock).
   - Unattended `neuro_diorama` runs default `require_review=False` (gated by deterministic `Q1–Q10` + provenance); pass `--require-review` (default `True` on classic Schema v5) or `--auto-populate-review` when SHA-256 `reference_semantic_review.json` sign-off is required.

## 2. Legacy Schema v4 / v5 Short Mode (`R51` / `R52`)
1. **Default Legacy Mode — Text-Only Schema v4 (`31_O2CmlKOk` 10-Clip Standard)**:
   - Legacy `10`-clip Schema v4 projects can run text-only prompts or attach optional reference stills via `main.py ref-qa --require-review` and `main.py packets`.
