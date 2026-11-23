# Folder Cleanup Inventory (`folder_cleanup_inventory.md`)

Updated after explicit user approval (`"진행하고 테스트 영상 하나 만들어줘"`, `2026-11-09T12:06Z`):
- **All `65` unreferenced `PARTIAL_MEDIA` folders** moved safely to recoverable 30-day Google Drive Trash via `rclone purge --fast-list` (`41` active/referenced projects strictly preserved).
- **Duplicate `BCI_Shorts_Channel/scripts/`** archived to `BCI_Shorts_Channel/research/_archive_scripts/` and empty duplicate `BCI_Shorts_Channel/news/` removed; guarded in [workspace_hygiene.py](file:///home/canadaofbin/gdrive/Kyubin_Yun_Workspace/07_Youtube/scripts/workspace_hygiene.py).

## 1. Summary of Executed Safe Cleanup (Phase 4-2, Recoverable 30-Day Google Drive Trash)

| Scope | Target | Action Taken | Notes |
|---|---|---|---|
| `pipeline/` | 13 resurrected Oct legacy files (`assembly.py`, `audio.py`, `visuals.py`, `batch_psychology_production.py`, `colab_runner.py`, `smoke_psychology_topic1.py`, `smoke_topic1.py`, `smoketest.py`, `test_audit_fixes.py`, `test_edge_cases.py`, `test_flow_all_in_one.py`, `test_flow_chaining.py`, `test_tension_speed.py`) | **Moved to Google Drive Trash** (`rclone deletefile` without `--drive-use-trash=false`) | Verified 0 active imports across `main.py`, `pipeline/`, `scripts/`, `tests/` |
| Root | `produce_psychology_batch.py` | **KEPT (Active Imports Detected)** | Imported by `pipeline/cli.py:147`, `pipeline/orchestrator.py:53`, `pipeline/video_autopsy.py:984,2187`, `tests/test_flow_qa_anti_placeholder.py:18,280` |
| Root | `final_shorts_v8_pilot_01_*.mp4` (47.34 MB, matches `05_assembly`: `True`), `final_shorts_v8_pilot_02_*.mp4` (95.41 MB, matches `05_assembly`: `True`) | **KEPT (Protected `v8_pilot_01*` / `v8_pilot_02*` constraint)** | Preserved pending Phase 6 user review |
| Root | `__pycache__/`, `.pytest_cache/` | **Removed** | Guarded via `PYTHONPYCACHEPREFIX=/tmp/aab_pycache` & `.gitignore` |
| `research_dossiers/` | 4 `.tmp_*_flow_all_in_one_prompts.json` files under `phineas_gage_iron_rod/diorama_v7_lowpoly/` | **Moved to Google Drive Trash** | Fixed `storage.py` & `flow_prompt_builder.py` to unlink `.tmp_*` on write failure |
| `reports/daily/` | `2026-10-*.png` chart images | **Archived to `BCI_Shorts_Channel/reports/archive/2026-10/`** | Kept `.json`/`.md` metrics intact for historical trend continuity |

## 2. Duplicate Directories Audit

| Pair | Findings | Recommended Action (Pending User Approval) |
|---|---|---|
| `scripts/` vs `BCI_Shorts_Channel/scripts/` | Root `scripts/` holds active Python CLI/maintenance tools (`chatroom_mention.py`, `sync_artifacts_archive.py`, `workspace_hygiene.py`, etc.). `BCI_Shorts_Channel/scripts/` holds legacy Oct planning markdown (`week01_first_5_videos.md`, `batch_ops/`). | Move `BCI_Shorts_Channel/scripts/` into `BCI_Shorts_Channel/research/_archive_scripts/` so `scripts/` is unambiguous. |
| `BCI_Shorts_Channel/news/` vs `BCI_Shorts_Channel/research/news/` | Both directories currently exist on disk with `0` files (`empty`). `pipeline/news_hunter.py` & `pipeline/config.py` resolve news paths dynamically. | Remove empty duplicate after confirming canonical `NEWS_DIR` target. |

## 3. All 106 `BCI_Shorts_Channel/projects/*` Directories (8737.96 MB Total)

- **KEEP_PROTECTED** (`17`): Published `diorama_01..07`, `v8_pilot_01/02`, or active `staging_queue.json`.
- **KEEP_REFERENCED** (`24`): Referenced by name in code, tests, or rule docs.
- **REUSABLE_ASSEMBLED** (`0`): Unreferenced with completed `05_assembly/final_shorts_1080x1920.mp4`.
- **PARTIAL_MEDIA** (`65`): Unreferenced partial clips/audio without final MP4.
- **STUB_OR_LEGACY_DRAFT** (`0`): Draft/stub JSON only.
- **EMPTY_SHELL** (`0`): Empty directory.

| # | Project ID | Category | Size (MB) | Files | Last Modified | Git | Code Ref | In Queue | Upload Receipt | Clips | Assembled | Proposed Disposition |
|---:|---|---|---:|---:|---|---|---|---|---|---:|---|---|
| 1 | `boost_01_sleep_first_night_watch` | `KEEP_REFERENCED` | 278.36 | 160 | 2026-11-09 | No | Yes | No | `No` | 48 | Yes | Preserve (Referenced in code/tests/docs) |
| 2 | `boost_02_habits_marshmallow_trust` | `KEEP_REFERENCED` | 18.66 | 24 | 2026-11-05 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 3 | `boost_03_memory_loftus_false_engram` | `KEEP_REFERENCED` | 315.96 | 145 | 2026-11-09 | No | Yes | No | `No` | 48 | Yes | Preserve (Referenced in code/tests/docs) |
| 4 | `boost_04_anxiety_third_person_chatter` | `KEEP_REFERENCED` | 27.70 | 29 | 2026-11-04 | No | Yes | No | `No` | 1 | No | Preserve (Referenced in code/tests/docs) |
| 5 | `boost_05_relationships_handholding_pain` | `KEEP_REFERENCED` | 5.96 | 18 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 6 | `diorama_01_hm_lab_B_dynamic` | `KEEP_REFERENCED` | 254.95 | 110 | 2026-11-09 | No | Yes | No | `No` | 63 | Yes | Preserve (Referenced in code/tests/docs) |
| 7 | `diorama_01_patient_hm_hippocampus` | `KEEP_PROTECTED` | 366.43 | 178 | 2026-11-04 | No | Yes | No | `q1lUimnZ-V0` | 63 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 8 | `diorama_02_ramachandran_phantom_mirror` | `KEEP_PROTECTED` | 215.08 | 131 | 2026-11-04 | No | Yes | No | `u5mQNZWNjiw` | 61 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 9 | `diorama_03_alien_hand_syndrome` | `KEEP_PROTECTED` | 214.77 | 107 | 2026-11-04 | No | Yes | No | `PK1opKmokwY` | 61 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 10 | `diorama_04_milgram_obedience_switch` | `KEEP_PROTECTED` | 213.16 | 106 | 2026-11-04 | No | Yes | No | `wUAD5xIpaww` | 60 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 11 | `diorama_05_hippocampal_memory_prosthesis` | `KEEP_PROTECTED` | 201.14 | 102 | 2026-11-04 | No | Yes | No | `JJkBqo-hTS8` | 56 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 12 | `diorama_06_clive_wearing_seven_second_mind` | `KEEP_PROTECTED` | 207.09 | 104 | 2026-11-04 | No | Yes | No | `ZbjKX8CBt8A` | 58 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 13 | `diorama_07_invisible_gorilla_attention` | `KEEP_PROTECTED` | 221.65 | 106 | 2026-11-04 | No | Yes | No | `t8Z_Q8oB9MY` | 56 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 14 | `diorama_08_maguire_london_taxi_hippocampus` | `KEEP_REFERENCED` | 222.98 | 105 | 2026-11-08 | No | Yes | No | `No` | 56 | Yes | Preserve (Referenced in code/tests/docs) |
| 15 | `diorama_09_broca_patient_tan_speech_loss` | `KEEP_REFERENCED` | 226.31 | 105 | 2026-11-08 | No | Yes | No | `No` | 56 | Yes | Preserve (Referenced in code/tests/docs) |
| 16 | `diorama_10_olds_milner_pleasure_center` | `KEEP_REFERENCED` | 228.09 | 110 | 2026-11-08 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 17 | `diorama_11_blindsight_subcortical_vision` | `KEEP_REFERENCED` | 225.95 | 107 | 2026-11-08 | No | Yes | No | `No` | 56 | Yes | Preserve (Referenced in code/tests/docs) |
| 18 | `diorama_14_libet_readiness_potential` | `KEEP_REFERENCED` | 267.06 | 173 | 2026-11-08 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 19 | `diorama_16_rizzolatti_mirror_neuron_empathy` | `KEEP_REFERENCED` | 283.60 | 182 | 2026-11-08 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 20 | `diorama_18_greene_trolley_dilemma_dual_process` | `KEEP_REFERENCED` | 298.18 | 182 | 2026-11-09 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 21 | `diorama_20_dutton_aron_capilano_bridge` | `KEEP_REFERENCED` | 348.17 | 191 | 2026-11-04 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 22 | `diorama_21_delgado_stimoceiver_bull` | `KEEP_REFERENCED` | 311.48 | 190 | 2026-11-04 | No | Yes | No | `No` | 57 | Yes | Preserve (Referenced in code/tests/docs) |
| 23 | `diorama_26_clark_doll_experiment_bias` | `KEEP_REFERENCED` | 351.81 | 213 | 2026-11-09 | No | Yes | No | `No` | 58 | Yes | Preserve (Referenced in code/tests/docs) |
| 24 | `diorama_27_baddeley_working_memory_architecture` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 25 | `diorama_28_csikszentmihalyi_flow_hypofrontality` | `PARTIAL_MEDIA` | 27.93 | 12 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 26 | `diorama_29_cotard_walking_corpse_syndrome` | `PARTIAL_MEDIA` | 24.31 | 24 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 27 | `diorama_30_little_albert_fear_conditioning` | `PARTIAL_MEDIA` | 27.52 | 12 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 28 | `diorama_31_darley_latane_bystander_effect` | `PARTIAL_MEDIA` | 29.00 | 12 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 29 | `diorama_32_bandura_bobo_doll_mirroring` | `PARTIAL_MEDIA` | 0.39 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 30 | `diorama_33_festinger_social_comparison_envy` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 31 | `diorama_34_deci_overjustification_reward` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 32 | `diorama_35_pavlov_dogs_conditioning` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 33 | `diorama_36_rosenhan_sane_in_insane_places` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 34 | `diorama_37_baron_cohen_theory_of_mind` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 35 | `diorama_38_harlow_cloth_mother_attachment` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 36 | `diorama_39_dehaene_conscious_brain_ignition` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 37 | `diorama_40_raine_murderer_brain_pet_deficits` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 38 | `diorama_41_steele_aronson_stereotype_threat` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 39 | `diorama_42_cherry_cocktail_party_filter` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 40 | `diorama_43_kross_distanced_self_talk_chatter` | `PARTIAL_MEDIA` | 0.37 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 41 | `diorama_44_dunning_kruger_metacognitive_blindness` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 42 | `diorama_45_thorndike_law_of_effect` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 43 | `diorama_46_zimbardo_stanford_prison_roles` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 44 | `diorama_47_cialdini_door_in_the_face_reciprocity` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 45 | `diorama_48_raichle_default_mode_network` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 46 | `diorama_49_ekman_microexpressions_deception` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 47 | `diorama_50_wernicke_sensory_aphasia` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 48 | `diorama_51_cosmides_tooby_cheater_detection` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 49 | `diorama_52_schachter_external_eating_cues` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 50 | `diorama_53_kanwisher_fusiform_face_area` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 51 | `diorama_54_craik_lockhart_levels_of_processing` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 52 | `diorama_55_seligman_learned_helplessness` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 53 | `diorama_56_skinner_operant_superstition` | `PARTIAL_MEDIA` | 0.39 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 54 | `diorama_57_dunbar_number_neocortex_limit` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 55 | `diorama_58_shapiro_emdr_trauma_saccades` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 56 | `diorama_59_wegner_white_bear_suppression` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 57 | `diorama_60_ebbinghaus_forgetting_curve` | `PARTIAL_MEDIA` | 0.38 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 58 | `diorama_61_zeigarnik_uncompleted_task_loop` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 59 | `diorama_62_zihl_akinetopsia_motion_blindness` | `PARTIAL_MEDIA` | 0.39 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 60 | `diorama_63_festinger_carlsmith_insufficient_reward` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 61 | `diorama_64_freedman_fraser_foot_in_the_door` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 62 | `diorama_65_godden_baddeley_diver_context_memory` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 63 | `diorama_66_hebb_synaptic_learning_rule` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 64 | `diorama_67_hubel_wiesel_visual_orientation` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 65 | `diorama_68_kahneman_tversky_loss_aversion` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 66 | `diorama_69_kandel_aplysia_synaptic_plasticity` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 67 | `diorama_70_langer_copy_machine_because_heuristic` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 68 | `diorama_71_ledoux_dual_fear_pathways` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 69 | `diorama_72_mcgurk_multisensory_illusion` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 70 | `diorama_73_melzack_wall_pain_gate` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 71 | `diorama_74_miller_magical_number_seven` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 72 | `diorama_75_mischel_marshmallow_self_control` | `PARTIAL_MEDIA` | 0.39 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 73 | `diorama_76_okeefe_moser_place_grid_cells` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 74 | `diorama_77_posner_spatial_attention_spotlight` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 75 | `diorama_78_ramachandran_synesthesia_cross_wiring` | `KEEP_REFERENCED` | 0.37 | 10 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 76 | `diorama_79_rosenthal_pygmalion_expectancy` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 77 | `diorama_80_rubber_hand_body_plasticity` | `PARTIAL_MEDIA` | 0.39 | 11 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 78 | `diorama_81_schultz_dopamine_prediction_error` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 79 | `diorama_82_shepard_metzler_mental_rotation` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 80 | `diorama_83_sperling_iconic_memory_buffer` | `PARTIAL_MEDIA` | 0.36 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 81 | `diorama_84_stroop_color_word_conflict` | `PARTIAL_MEDIA` | 0.37 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 82 | `diorama_85_tajfel_minimal_group_favoritism` | `PARTIAL_MEDIA` | 0.35 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 83 | `diorama_86_treisman_attenuation_selective_attention` | `PARTIAL_MEDIA` | 0.35 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 84 | `diorama_87_trivers_parental_investment_drives` | `PARTIAL_MEDIA` | 0.35 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 85 | `diorama_88_tulving_episodic_mental_time_travel` | `PARTIAL_MEDIA` | 0.35 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 86 | `diorama_89_wason_selection_confirmation_bias` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 87 | `diorama_90_zajonc_mere_exposure_effect` | `PARTIAL_MEDIA` | 0.38 | 10 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 88 | `diorama_91_hochberg_braingate_robotic_coffee` | `PARTIAL_MEDIA` | 29.10 | 12 | 2026-11-04 | No | No | No | `No` | 0 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 89 | `diorama_gage_v65_roger` | `PARTIAL_MEDIA` | 4.04 | 2 | 2026-10-27 | No | No | No | `No` | 2 | No | Candidate: projects/_archive/partial (Hold pending user approval) |
| 90 | `gage_diorama_v6` | `KEEP_REFERENCED` | 317.39 | 257 | 2026-10-27 | No | Yes | No | `No` | 61 | Yes | Preserve (Referenced in code/tests/docs) |
| 91 | `gage_diorama_v6_dynamic` | `KEEP_PROTECTED` | 334.79 | 216 | 2026-11-04 | No | Yes | No | `Wydl4JpZmAw` | 61 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 92 | `gage_diorama_v7_lowpoly` | `KEEP_REFERENCED` | 377.15 | 174 | 2026-11-09 | No | Yes | No | `No` | 61 | Yes | Preserve (Referenced in code/tests/docs) |
| 93 | `psych_01` | `KEEP_REFERENCED` | 0.00 | 2 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 94 | `psych_01_habit_loop_basal_ganglia` | `KEEP_PROTECTED` | 94.10 | 16 | 2026-11-04 | No | Yes | No | `p4ou90cHt50` | 0 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 95 | `psych_02` | `KEEP_REFERENCED` | 0.00 | 2 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 96 | `psych_02_inner_speech_decoding` | `KEEP_PROTECTED` | 100.96 | 12 | 2026-11-04 | No | Yes | No | `p0etX4iMJ7Q` | 0 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 97 | `psych_03` | `KEEP_REFERENCED` | 0.00 | 2 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 98 | `psych_03_split_brain_dual_consciousness` | `KEEP_PROTECTED` | 89.19 | 12 | 2026-11-04 | No | Yes | No | `nGNIl26te0w` | 0 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 99 | `psych_04_phineas_gage_frontal_lobe` | `KEEP_PROTECTED` | 535.96 | 199 | 2026-11-08 | No | Yes | No | `deleted_from_studio` | 10 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 100 | `psych_05` | `KEEP_REFERENCED` | 0.00 | 2 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 101 | `psych_05_capgras_imposter_delusion` | `KEEP_PROTECTED` | 87.23 | 12 | 2026-11-04 | No | Yes | No | `lZv3_UAWScI` | 0 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 102 | `psych_06` | `KEEP_REFERENCED` | 0.00 | 2 | 2026-11-04 | No | Yes | No | `No` | 0 | No | Preserve (Referenced in code/tests/docs) |
| 103 | `psych_06_glymphatic_sleep_toxins` | `KEEP_PROTECTED` | 98.68 | 16 | 2026-11-04 | No | Yes | No | `31_O2CmlKOk` | 0 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 104 | `reenact_01_ainsworth_strange_situation` | `KEEP_PROTECTED` | 676.12 | 338 | 2026-11-04 | No | Yes | No | `jySZ6EL3aYM` | 64 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 105 | `v8_pilot_01_sleep_first_night_watch` | `KEEP_PROTECTED` | 176.71 | 96 | 2026-11-08 | No | Yes | No | `No` | 18 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
| 106 | `v8_pilot_02_sleep_night_watch_cam3d` | `KEEP_PROTECTED` | 380.95 | 163 | 2026-11-08 | No | No | No | `No` | 14 | Yes | Strictly Preserve (Published / v8 Pilot / Active Queue) |
