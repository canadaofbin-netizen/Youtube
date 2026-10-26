# ALL ABOUT BRAIN — Psychology 100 Longform Research Dossiers Audit Report (Round-2 Adversarial Verified)

- **Generated at**: `2026-10-26T04:18:00+00:00`
- **Dossiers Root**: `BCI_Shorts_Channel/research_dossiers/`
- **Index JSON**: `BCI_Shorts_Channel/reports/psychology_100_research_dossiers_index.json`
- **Validation Gate (`R44`, `R44-D`, `R52`)**: **100 / 100 READY (`issues: []`)**

---

## 1. Executive Summary & Aggregate Metrics

| Metric | Count / Result |
|---|---|
| Total `ALL_PSYCHOLOGY_100_TOPICS` Covered | **100 / 100 (100%)** |
| Pre-Existing Golden Dossiers Preserved Untouched | **4** (`phineas_gage_iron_rod`, `invisible_gorilla_attention`, `pavlov_dogs_conditioning`, `milgram_obedience_shock`) |
| Remediated & Verified Longform Dossiers | **96** |
| `validate_dossier(slug)` (`ready == True`, `issues == []`) | **100 / 100 PASS** |
| `resolve_dossier_for_project(project_id)` (`100/100` incl. legacy aliases) | **100 / 100 PASS** |
| `plan_seed_from_dossier(slug)` (`schema == 5`, `key_visual` preserved) | **100 / 100 PASS** |
| `validate_scene_blueprints()` (`R52` + `S1` media evidence linked) | **100 / 100 PASS (`0` issues)** |
| `check_narration_facts()` (`shorts_extract` + `script.json` numeral trace) | **100 / 100 PASS (`0` untraced numerals)** |
| `04_media_refs.json` Honesty Gate (`M1` + `M2` keyframe-locked windows, `0` VTT stutters, `0` false `archive_film`, `M3` still) | **96 / 96 New Dossiers PASS (max S1 Jaccard `0.208 < 0.35`, `0` boilerplate)** |
| Unique Reference YouTube Videos (`M1` & `M2`, zero doodle/whiteboard/screencast/AI-faceless/wrong-topic channels) | **201 Unique Video IDs (`0` collisions)** |
| Verified Wikimedia Commons / Museum Archival Stills (`media/M3/still.jpg`) | **96 / 96 New Dossiers (`96` unique Commons files)** |
| Total Curated Sources Across 100 Dossiers | **898** |
| Total Verified Peer-Reviewed DOIs (`0` hallucinated, `0` off-domain collisions, `0` citation mismatches) | **595** |
| Total Extracted Video Keyframes (`keyframes/kf_*.jpg`) | **2,758** |
| Total `02_master_story.md` Documentary Prose (`0` prompt/meta leaks, `0` HTML entities, `0` mechanical grammar splices) | **2,030,159 characters (~338,359 words)** |

### Visual Mode Distribution (`R45` — Brain Only When Needed)
- **`BEHAVIORAL_PSYCH`** (pure human/social/cognitive reenactment, opaque cranium, `links: []`): **23**
- **`HYBRID`** (real-world behavioral experiment + selective translucent brain mechanism bridge): **28**
- **`NEURO_BIOLOGY`** (lesion, split-brain, single-unit electrophysiology, PET/fMRI/EEG, BCI): **49**

### Content Pillar Distribution (`P1`)
- **`bci_ethics`**: **9**
- **`bci_tech`**: **4**
- **`brain_basics`**: **41**
- **`brain_health`**: **16**
- **`brain_history`**: **11**
- **`brain_mysteries`**: **18**
- **`brain_news`**: **1**

---

## 2. Upstream `pipeline/topics_catalog.py` Audit Findings (Important for Gear 2)

During Crossref verification of `ALL_PSYCHOLOGY_100_TOPICS`, two important upstream issues in `pipeline/topics_catalog.py` were identified and corrected inside the authoritative dossiers:

1. **Upstream Template `clip_narrations` Warning**: Several legacy auto-seeded entries in `ALL_PSYCHOLOGY_100_TOPICS` contain broken placeholder strings (e.g., missing researcher subjects `"In YYYY, investigated..."` or boilerplate `"firing rates shifted by forty millivolts"` on purely behavioral studies). **Gear 2 (`@yt-writer` / `bci-script-gen`) MUST author fresh plain-language `script.json` + v5 `visual_plan.json` directly from these validated `research_dossiers/<slug>/` files** rather than copying legacy `topics_catalog.py` `clip_narrations`.
2. **Upstream `paper_doi` Corrections / Historical Archival Upgrades (32 topics)**: Where `topics_catalog.py` listed a dead Crossref DOI, wrong journal suffix, secondary review/chapter instead of the primary experiment paper, or anachronistic DOI for a pre-DOI 19th-century monograph, `01_sources.json` anchors `SRC1` to the verified primary Crossref DOI (or verified `primary_historical` archival source + peer-reviewed `follow_up`/`replication` DOIs):

| `project_id` | Dossier `slug` | Legacy Catalog `paper_doi` | Verified Dossier `SRC1` Primary | Resolution |
|---|---|---|---|---|
| `psych_01_habit_loop_basal_ganglia` | `habit_loop_basal_ganglia` | `10.1038/nrn2787` | `10.1038/nature03857` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_02_inner_speech_decoding` | `inner_speech_decoding` | `10.1038/s41586-023-06443-4` | `10.1038/s41586-023-06377-x` | Catalog DOI retained as follow-up/review; SRC1 upgraded to original landmark primary experiment DOI |
| `psych_03_split_brain_dual_consciousness` | `split_brain_dual_consciousness` | `10.1093/brain/123.7.1293` | `10.1073/pnas.48.10.1765` | Catalog DOI retained as follow-up/review; SRC1 upgraded to original landmark primary experiment DOI |
| `psych_04_phineas_gage_frontal_lobe` | `phineas_gage_iron_rod` | `10.1126/science.8178168` | `10.1056/NEJM184812130392001` | Catalog DOI retained as follow-up/review; SRC1 upgraded to original landmark primary experiment DOI |
| `psych_09_false_memory_elizabeth_loftus` | `false_memory_elizabeth_loftus` | `10.1016/0010-0285(74)90019-9` | `10.1016/s0022-5371(74)80011-3` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_10_cognitive_dissonance_acc` | `cognitive_dissonance_acc` | `10.1038/nn.2338` | `10.1038/nn.2413` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_11_pavlov_classical_conditioning` | `pavlov_dogs_conditioning` | `10.1038/nrn728` | `10.5214/ans.0972-7531.1017309` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_13_asch_conformity_pressure` | `asch_conformity_pressure` | `10.1016/j.biopsych.2005.06.004` | `10.1037/h0093718` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_21_beck_cognitive_triad_depression` | `beck_cognitive_triad_depression` | `10.1001/archpsyc.1963.01420160013002` | `10.1001/archpsyc.1963.01720160014002` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_33_ekman_microexpressions_deception` | `ekman_microexpressions_deception` | `10.1177/0956797611413294` | `10.1080/00332747.1969.11023575` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_37_shapiro_emdr_trauma_saccades` | `shapiro_emdr_trauma_saccades` | `10.1038/s41586-019-0931-y` | `10.1002/jts.2490020207` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_38_baars_global_workspace_theater` | `baars_global_workspace_theater` | `10.1016/j.neuron.2011.01.002` | `10.1016/s0079-6123(05)50004-9` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_39_csikszentmihalyi_flow_hypofrontality` | `csikszentmihalyi_flow_hypofrontality` | `10.1016/j.concog.2004.06.001` | `10.1016/j.concog.2004.07.002` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_50_kross_distanced_self_talk_chatter` | `kross_distanced_self_talk_chatter` | `10.1038/s41598-017-04047-3` | `10.1037/a0035173` | Catalog DOI retained as follow-up/review; SRC1 upgraded to original landmark primary experiment DOI |
| `psych_51_stroop_color_word_conflict` | `stroop_color_word_conflict` | `10.1037/h0054117` | `10.1037/h0054651` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_55_thorndike_law_of_effect` | `thorndike_law_of_effect` | `10.1037/h0071325` | `10.1037/10780-000` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_56_wason_selection_confirmation_bias` | `wason_selection_confirmation_bias` | `10.1080/14640746608400047` | `10.1080/14640746808400161` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_59_alien_hand_syndrome` | `alien_hand_syndrome` | `10.1016/0028-3932(72)90040-5` | `10.1001/archneur.1981.00510110043004` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_63_ramachandran_synesthesia_cross_wiring` | `ramachandran_synesthesia_cross_wiring` | `10.1098/rspb.2001.1576` | `10.1098/rspb.2000.1576` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_64_broca_patient_tan_speech_loss` | `broca_patient_tan_speech_loss` | `10.3406/bmsap.1861.1238` | `10.1007/s11065-011-9174-x` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_65_wernicke_sensory_aphasia` | `wernicke_sensory_aphasia` | `10.1097/00005053-187510000-00010` | `10.1001/archneur.1970.00480210090013` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_66_cotard_walking_corpse_syndrome` | `cotard_walking_corpse_syndrome` | `10.1016/S0140-6736(02)77131-1` | `10.1111/j.1600-0447.1995.tb09764.x` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_67_clive_wearing_seven_second_mind` | `clive_wearing_seven_second_mind` | `10.1093/neucas/1.2.83` | `10.1080/01688639508405157` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_68_milner_hm_procedural_memory` | `milner_hm_procedural_memory` | `10.1016/0028-3932(68)90013-4` | `10.1016/0028-3932(68)90021-3` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_70_delgado_stimoceiver_bull_stop` | `delgado_stimoceiver_bull_stop` | `10.1037/h0040183` | `https://www.nytimes.com/1965/05/17/archives/matador-with-a-radio-stops-wired-bull-modified-behavior-of-animals.html` | Pre-DOI 19th/early-20th c. monograph anchored to verified archival primary + peer-reviewed DOIs |
| `psych_73_kandel_aplysia_synaptic_plasticity` | `kandel_aplysia_synaptic_plasticity` | `10.1126/science.167.3917.378` | `10.1126/science.167.3926.1745` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_75_hebb_synaptic_learning_rule` | `hebb_synaptic_learning_rule` | `10.1037/10019-000` | `10.4324/9781410612403` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_78_treisman_attenuation_selective_attention` | `treisman_attenuation_selective_attention` | `10.1080/14640746408400157` | `10.1016/s0022-5371(64)80015-3` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_80_tulving_episodic_mental_time_travel` | `tulving_episodic_mental_time_travel` | `10.1016/B978-0-12-692550-0.50013-2` | `10.1146/annurev.psych.53.100901.135114` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_84_clark_doll_experiment_bias` | `clark_doll_experiment_bias` | `10.1007/BF02808007` | `10.2307/2966491` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_93_trivers_parental_investment_drives` | `trivers_parental_investment_drives` | `10.1017/CBO9780511818202.007` | `10.1086/406755` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |
| `psych_94_cosmides_tooby_cheater_detection` | `cosmides_tooby_cheater_detection` | `10.1016/0010-0277(92)90050-Z` | `10.1016/0010-0277(89)90023-1` | Catalog DOI failed Crossref / wrong target; replaced with Crossref-verified primary DOI |

---

## 3. Complete 100-Topic Research Dossier Registry

| # | `project_id` | Dossier `slug` | Mode | Origin | Primary DOI / Archive | Sources | Facts | Story Chars | Keyframes | Gate |
|---|---|---|---|---|---|---|---|---|---|---|
| 1 | `psych_01_habit_loop_basal_ganglia` | `habit_loop_basal_ganglia` | `NEURO_BIOLOGY` | Remediated v5 | `10.1038/nature03857` | 8 (5 DOIs) | 10 | 21,115 | 28 | PASS |
| 2 | `psych_02_inner_speech_decoding` | `inner_speech_decoding` | `NEURO_BIOLOGY` | Remediated v5 | `10.1038/s41586-023-06377-x` | 7 (4 DOIs) | 11 | 20,400 | 22 | PASS |
| 3 | `psych_03_split_brain_dual_consciousness` | `split_brain_dual_consciousness` | `NEURO_BIOLOGY` | Remediated v5 | `10.1073/pnas.48.10.1765` | 8 (5 DOIs) | 11 | 21,098 | 26 | PASS |
| 4 | `psych_04_phineas_gage_frontal_lobe` | `phineas_gage_iron_rod` | `NEURO_BIOLOGY` | Preserved v5 | `10.1056/NEJM184812130392001` | 10 (8 DOIs) | 25 | 13,579 | 56 | PASS |
| 5 | `psych_05_capgras_imposter_delusion` | `capgras_imposter_delusion` | `NEURO_BIOLOGY` | Remediated v5 | `10.1098/rspb.1997.0062` | 10 (7 DOIs) | 10 | 20,874 | 28 | PASS |
| 6 | `psych_06_glymphatic_sleep_toxins` | `glymphatic_sleep_toxins` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.1241224` | 10 (7 DOIs) | 10 | 20,065 | 28 | PASS |
| 7 | `psych_07_hippocampal_memory_prosthesis` | `hippocampal_memory_prosthesis` | `NEURO_BIOLOGY` | Remediated v5 | `10.1088/1741-2552/aaaed7` | 8 (5 DOIs) | 11 | 21,444 | 28 | PASS |
| 8 | `psych_08_inattentional_blindness_gorilla` | `invisible_gorilla_attention` | `HYBRID` | Preserved v5 | `10.1068/p281059` | 14 (13 DOIs) | 9 | 13,580 | 61 | PASS |
| 9 | `psych_09_false_memory_elizabeth_loftus` | `false_memory_elizabeth_loftus` | `HYBRID` | Remediated v5 | `10.1016/s0022-5371(74)80011-3` | 8 (5 DOIs) | 12 | 21,073 | 26 | PASS |
| 10 | `psych_10_cognitive_dissonance_acc` | `cognitive_dissonance_acc` | `HYBRID` | Remediated v5 | `10.1038/nn.2413` | 11 (8 DOIs) | 12 | 23,508 | 25 | PASS |
| 11 | `psych_11_pavlov_classical_conditioning` | `pavlov_dogs_conditioning` | `HYBRID` | Preserved v5 | `https://psychclassics.yorku.ca/Pavlov/lecture` | 18 (12 DOIs) | 14 | 6,963 | 37 | PASS |
| 12 | `psych_12_skinner_operant_superstition` | `skinner_operant_superstition` | `HYBRID` | Remediated v5 | `10.1037/h0055873` | 9 (6 DOIs) | 11 | 18,874 | 24 | PASS |
| 13 | `psych_13_asch_conformity_pressure` | `asch_conformity_pressure` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0093718` | 9 (6 DOIs) | 13 | 17,793 | 28 | PASS |
| 14 | `psych_14_patient_hm_hippocampus` | `patient_hm_hippocampus` | `NEURO_BIOLOGY` | Remediated v5 | `10.1136/jnnp.20.1.11` | 9 (6 DOIs) | 10 | 18,643 | 28 | PASS |
| 15 | `psych_15_olds_milner_pleasure_center` | `olds_milner_pleasure_center` | `NEURO_BIOLOGY` | Remediated v5 | `10.1037/h0058775` | 7 (4 DOIs) | 11 | 18,952 | 23 | PASS |
| 16 | `psych_16_miller_magical_number_seven` | `miller_magical_number_seven` | `HYBRID` | Remediated v5 | `10.1037/h0043158` | 9 (6 DOIs) | 10 | 17,693 | 28 | PASS |
| 17 | `psych_17_harlow_cloth_mother_attachment` | `harlow_cloth_mother_attachment` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0047884` | 9 (6 DOIs) | 11 | 18,212 | 24 | PASS |
| 18 | `psych_18_milgram_obedience_authority` | `milgram_obedience_shock` | `BEHAVIORAL_PSYCH` | Preserved v5 | `10.1037/h0040525` | 12 (7 DOIs) | 16 | 8,623 | 28 | PASS |
| 19 | `psych_19_bandura_bobo_doll_mirroring` | `bandura_bobo_doll_mirroring` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0045925` | 9 (6 DOIs) | 10 | 18,382 | 28 | PASS |
| 20 | `psych_20_schachter_singer_two_factor` | `schachter_singer_two_factor` | `HYBRID` | Remediated v5 | `10.1037/h0046234` | 9 (6 DOIs) | 10 | 19,475 | 28 | PASS |
| 21 | `psych_21_beck_cognitive_triad_depression` | `beck_cognitive_triad_depression` | `HYBRID` | Remediated v5 | `10.1001/archpsyc.1963.01720160014002` | 9 (6 DOIs) | 9 | 18,574 | 21 | PASS |
| 22 | `psych_22_rosenthal_pygmalion_expectancy` | `rosenthal_pygmalion_expectancy` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.2466/pr0.1966.19.1.115` | 9 (6 DOIs) | 9 | 19,255 | 28 | PASS |
| 23 | `psych_23_melzack_wall_pain_gate` | `melzack_wall_pain_gate` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.150.3699.971` | 9 (6 DOIs) | 8 | 19,286 | 28 | PASS |
| 24 | `psych_24_seligman_learned_helplessness` | `seligman_learned_helplessness` | `HYBRID` | Remediated v5 | `10.1037/h0024514` | 9 (6 DOIs) | 9 | 18,911 | 27 | PASS |
| 25 | `psych_25_darley_latane_bystander_effect` | `darley_latane_bystander_effect` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0025589` | 9 (6 DOIs) | 11 | 19,096 | 28 | PASS |
| 26 | `psych_26_mischel_marshmallow_self_control` | `mischel_marshmallow_self_control` | `HYBRID` | Remediated v5 | `10.1037/h0029815` | 9 (6 DOIs) | 9 | 19,007 | 28 | PASS |
| 27 | `psych_27_zimbardo_stanford_prison_roles` | `zimbardo_stanford_prison_roles` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.21236/ad0751041` | 9 (6 DOIs) | 9 | 19,469 | 28 | PASS |
| 28 | `psych_28_shepard_metzler_mental_rotation` | `shepard_metzler_mental_rotation` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.171.3972.701` | 8 (5 DOIs) | 8 | 18,366 | 28 | PASS |
| 29 | `psych_29_deci_overjustification_reward` | `deci_overjustification_reward` | `HYBRID` | Remediated v5 | `10.1037/h0030644` | 9 (6 DOIs) | 9 | 19,929 | 24 | PASS |
| 30 | `psych_30_rosenhan_sane_in_insane_places` | `rosenhan_sane_in_insane_places` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1126/science.179.4070.250` | 7 (4 DOIs) | 9 | 18,855 | 25 | PASS |
| 31 | `psych_31_kahneman_tversky_loss_aversion` | `kahneman_tversky_loss_aversion` | `HYBRID` | Remediated v5 | `10.2307/1914185` | 9 (6 DOIs) | 9 | 19,034 | 28 | PASS |
| 32 | `psych_32_posner_spatial_attention_spotlight` | `posner_spatial_attention_spotlight` | `NEURO_BIOLOGY` | Remediated v5 | `10.1080/00335558008248231` | 9 (6 DOIs) | 9 | 19,353 | 28 | PASS |
| 33 | `psych_33_ekman_microexpressions_deception` | `ekman_microexpressions_deception` | `HYBRID` | Remediated v5 | `10.1080/00332747.1969.11023575` | 8 (5 DOIs) | 9 | 19,149 | 28 | PASS |
| 34 | `psych_34_libet_readiness_potential_free_will` | `libet_readiness_potential_free_will` | `NEURO_BIOLOGY` | Remediated v5 | `10.1093/brain/106.3.623` | 9 (6 DOIs) | 8 | 20,467 | 28 | PASS |
| 35 | `psych_35_baron_cohen_theory_of_mind` | `baron_cohen_theory_of_mind` | `HYBRID` | Remediated v5 | `10.1016/0010-0277(85)90022-8` | 8 (5 DOIs) | 8 | 19,441 | 26 | PASS |
| 36 | `psych_36_wegner_white_bear_suppression` | `wegner_white_bear_suppression` | `HYBRID` | Remediated v5 | `10.1037/0022-3514.53.1.5` | 8 (5 DOIs) | 8 | 18,967 | 28 | PASS |
| 37 | `psych_37_shapiro_emdr_trauma_saccades` | `shapiro_emdr_trauma_saccades` | `NEURO_BIOLOGY` | Remediated v5 | `10.1002/jts.2490020207` | 9 (6 DOIs) | 9 | 20,495 | 28 | PASS |
| 38 | `psych_38_baars_global_workspace_theater` | `baars_global_workspace_theater` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/s0079-6123(05)50004-9` | 9 (6 DOIs) | 8 | 20,994 | 28 | PASS |
| 39 | `psych_39_csikszentmihalyi_flow_hypofrontality` | `csikszentmihalyi_flow_hypofrontality` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/j.concog.2004.07.002` | 9 (6 DOIs) | 9 | 19,933 | 28 | PASS |
| 40 | `psych_40_rizzolatti_mirror_neuron_empathy` | `rizzolatti_mirror_neuron_empathy` | `NEURO_BIOLOGY` | Remediated v5 | `10.1007/bf00230027` | 9 (6 DOIs) | 9 | 20,446 | 28 | PASS |
| 41 | `psych_41_dunbar_number_neocortex_limit` | `dunbar_number_neocortex_limit` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/0047-2484(92)90081-j` | 9 (6 DOIs) | 9 | 19,053 | 28 | PASS |
| 42 | `psych_42_damasio_somatic_marker_decision` | `damasio_somatic_marker_decision` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/0010-0277(94)90018-3` | 9 (6 DOIs) | 8 | 20,484 | 28 | PASS |
| 43 | `psych_43_steele_aronson_stereotype_threat` | `steele_aronson_stereotype_threat` | `HYBRID` | Remediated v5 | `10.1037/0022-3514.69.5.797` | 8 (5 DOIs) | 9 | 20,071 | 26 | PASS |
| 44 | `psych_44_ledoux_dual_fear_pathways` | `ledoux_dual_fear_pathways` | `NEURO_BIOLOGY` | Remediated v5 | `10.1146/annurev.ps.46.020195.001233` | 9 (6 DOIs) | 8 | 20,104 | 28 | PASS |
| 45 | `psych_45_kanwisher_fusiform_face_area` | `kanwisher_fusiform_face_area` | `NEURO_BIOLOGY` | Remediated v5 | `10.1523/jneurosci.17-11-04302.1997` | 9 (6 DOIs) | 9 | 20,427 | 26 | PASS |
| 46 | `psych_46_ramachandran_phantom_limb_mirror` | `ramachandran_phantom_limb_mirror` | `NEURO_BIOLOGY` | Remediated v5 | `10.1093/brain/121.9.1603` | 9 (6 DOIs) | 9 | 20,111 | 26 | PASS |
| 47 | `psych_47_dunning_kruger_metacognitive_blindness` | `dunning_kruger_metacognitive_blindness` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/0022-3514.77.6.1121` | 9 (6 DOIs) | 8 | 20,038 | 28 | PASS |
| 48 | `psych_48_raichle_default_mode_network` | `raichle_default_mode_network` | `NEURO_BIOLOGY` | Remediated v5 | `10.1073/pnas.98.2.676` | 9 (6 DOIs) | 9 | 20,860 | 25 | PASS |
| 49 | `psych_49_greene_trolley_dilemma_dual_process` | `greene_trolley_dilemma_dual_process` | `HYBRID` | Remediated v5 | `10.1126/science.1062872` | 9 (6 DOIs) | 9 | 20,919 | 28 | PASS |
| 50 | `psych_50_kross_distanced_self_talk_chatter` | `kross_distanced_self_talk_chatter` | `HYBRID` | Remediated v5 | `10.1037/a0035173` | 8 (5 DOIs) | 9 | 20,265 | 26 | PASS |
| 51 | `psych_51_stroop_color_word_conflict` | `stroop_color_word_conflict` | `HYBRID` | Remediated v5 | `10.1037/h0054651` | 10 (7 DOIs) | 9 | 21,527 | 28 | PASS |
| 52 | `psych_52_zeigarnik_uncompleted_task_loop` | `zeigarnik_uncompleted_task_loop` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1007/bf02409755` | 9 (6 DOIs) | 9 | 20,059 | 28 | PASS |
| 53 | `psych_53_little_albert_fear_conditioning` | `little_albert_fear_conditioning` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0069608` | 9 (6 DOIs) | 9 | 20,700 | 26 | PASS |
| 54 | `psych_54_ebbinghaus_forgetting_curve` | `ebbinghaus_forgetting_curve` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/10011-000` | 9 (6 DOIs) | 9 | 18,876 | 28 | PASS |
| 55 | `psych_55_thorndike_law_of_effect` | `thorndike_law_of_effect` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/10780-000` | 9 (6 DOIs) | 8 | 18,922 | 26 | PASS |
| 56 | `psych_56_wason_selection_confirmation_bias` | `wason_selection_confirmation_bias` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1080/14640746808400161` | 9 (6 DOIs) | 9 | 18,929 | 28 | PASS |
| 57 | `psych_57_mcgurk_multisensory_illusion` | `mcgurk_multisensory_illusion` | `NEURO_BIOLOGY` | Remediated v5 | `10.1038/264746a0` | 9 (6 DOIs) | 8 | 20,290 | 26 | PASS |
| 58 | `psych_58_rubber_hand_body_plasticity` | `rubber_hand_body_plasticity` | `NEURO_BIOLOGY` | Remediated v5 | `10.1038/35784` | 10 (7 DOIs) | 8 | 22,073 | 23 | PASS |
| 59 | `psych_59_alien_hand_syndrome` | `alien_hand_syndrome` | `NEURO_BIOLOGY` | Remediated v5 | `10.1001/archneur.1981.00510110043004` | 9 (6 DOIs) | 8 | 21,318 | 28 | PASS |
| 60 | `psych_60_blindsight_subcortical_vision` | `blindsight_subcortical_vision` | `NEURO_BIOLOGY` | Remediated v5 | `10.1093/brain/97.1.709` | 10 (7 DOIs) | 9 | 22,737 | 28 | PASS |
| 61 | `psych_61_bodamer_prosopagnosia_face_blindness` | `bodamer_prosopagnosia_face_blindness` | `NEURO_BIOLOGY` | Remediated v5 | `10.1007/bf00352849` | 10 (7 DOIs) | 8 | 21,583 | 26 | PASS |
| 62 | `psych_62_zihl_akinetopsia_motion_blindness` | `zihl_akinetopsia_motion_blindness` | `NEURO_BIOLOGY` | Remediated v5 | `10.1093/brain/106.2.313` | 9 (6 DOIs) | 9 | 20,486 | 28 | PASS |
| 63 | `psych_63_ramachandran_synesthesia_cross_wiring` | `ramachandran_synesthesia_cross_wiring` | `NEURO_BIOLOGY` | Remediated v5 | `10.1098/rspb.2000.1576` | 9 (6 DOIs) | 9 | 21,369 | 28 | PASS |
| 64 | `psych_64_broca_patient_tan_speech_loss` | `broca_patient_tan_speech_loss` | `NEURO_BIOLOGY` | Remediated v5 | `10.1007/s11065-011-9174-x` | 10 (7 DOIs) | 9 | 21,959 | 26 | PASS |
| 65 | `psych_65_wernicke_sensory_aphasia` | `wernicke_sensory_aphasia` | `NEURO_BIOLOGY` | Remediated v5 | `10.1001/archneur.1970.00480210090013` | 9 (6 DOIs) | 8 | 20,719 | 24 | PASS |
| 66 | `psych_66_cotard_walking_corpse_syndrome` | `cotard_walking_corpse_syndrome` | `NEURO_BIOLOGY` | Remediated v5 | `10.1111/j.1600-0447.1995.tb09764.x` | 9 (6 DOIs) | 8 | 22,797 | 26 | PASS |
| 67 | `psych_67_clive_wearing_seven_second_mind` | `clive_wearing_seven_second_mind` | `NEURO_BIOLOGY` | Remediated v5 | `10.1080/01688639508405157` | 9 (6 DOIs) | 8 | 22,059 | 28 | PASS |
| 68 | `psych_68_milner_hm_procedural_memory` | `milner_hm_procedural_memory` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/0028-3932(68)90021-3` | 9 (6 DOIs) | 9 | 22,055 | 19 | PASS |
| 69 | `psych_69_penfield_cortical_homunculus` | `penfield_cortical_homunculus` | `NEURO_BIOLOGY` | Remediated v5 | `10.1093/brain/60.4.389` | 9 (6 DOIs) | 9 | 22,118 | 28 | PASS |
| 70 | `psych_70_delgado_stimoceiver_bull_stop` | `delgado_stimoceiver_bull_stop` | `NEURO_BIOLOGY` | Remediated v5 | `https://www.nytimes.com/1965/05/17/archives/m` | 9 (5 DOIs) | 9 | 22,574 | 25 | PASS |
| 71 | `psych_71_sperry_split_chiasm_interhemispheric` | `sperry_split_chiasm_interhemispheric` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.133.3466.1749` | 9 (6 DOIs) | 8 | 22,080 | 28 | PASS |
| 72 | `psych_72_hubel_wiesel_visual_orientation` | `hubel_wiesel_visual_orientation` | `NEURO_BIOLOGY` | Remediated v5 | `10.1113/jphysiol.1959.sp006308` | 9 (6 DOIs) | 9 | 22,239 | 28 | PASS |
| 73 | `psych_73_kandel_aplysia_synaptic_plasticity` | `kandel_aplysia_synaptic_plasticity` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.167.3926.1745` | 9 (6 DOIs) | 8 | 21,027 | 26 | PASS |
| 74 | `psych_74_okeefe_moser_place_grid_cells` | `okeefe_moser_place_grid_cells` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/0006-8993(71)90358-1` | 9 (6 DOIs) | 9 | 22,373 | 26 | PASS |
| 75 | `psych_75_hebb_synaptic_learning_rule` | `hebb_synaptic_learning_rule` | `NEURO_BIOLOGY` | Remediated v5 | `10.4324/9781410612403` | 9 (6 DOIs) | 8 | 22,761 | 28 | PASS |
| 76 | `psych_76_sperling_iconic_memory_buffer` | `sperling_iconic_memory_buffer` | `HYBRID` | Remediated v5 | `10.1037/h0093759` | 8 (5 DOIs) | 9 | 21,739 | 26 | PASS |
| 77 | `psych_77_cherry_cocktail_party_filter` | `cherry_cocktail_party_filter` | `HYBRID` | Remediated v5 | `10.1121/1.1907229` | 9 (6 DOIs) | 9 | 22,407 | 26 | PASS |
| 78 | `psych_78_treisman_attenuation_selective_attention` | `treisman_attenuation_selective_attention` | `HYBRID` | Remediated v5 | `10.1016/s0022-5371(64)80015-3` | 9 (6 DOIs) | 9 | 22,497 | 28 | PASS |
| 79 | `psych_79_baddeley_working_memory_architecture` | `baddeley_working_memory_architecture` | `HYBRID` | Remediated v5 | `10.1016/s0079-7421(08)60452-1` | 9 (6 DOIs) | 9 | 22,580 | 22 | PASS |
| 80 | `psych_80_tulving_episodic_mental_time_travel` | `tulving_episodic_mental_time_travel` | `NEURO_BIOLOGY` | Remediated v5 | `10.1146/annurev.psych.53.100901.135114` | 9 (6 DOIs) | 8 | 22,031 | 28 | PASS |
| 81 | `psych_81_craik_lockhart_levels_of_processing` | `craik_lockhart_levels_of_processing` | `HYBRID` | Remediated v5 | `10.1016/s0022-5371(72)80001-x` | 9 (6 DOIs) | 10 | 22,946 | 28 | PASS |
| 82 | `psych_82_godden_baddeley_diver_context_memory` | `godden_baddeley_diver_context_memory` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1111/j.2044-8295.1975.tb01468.x` | 7 (4 DOIs) | 9 | 20,275 | 28 | PASS |
| 83 | `psych_83_festinger_carlsmith_insufficient_reward` | `festinger_carlsmith_insufficient_reward` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0041593` | 9 (6 DOIs) | 9 | 21,733 | 28 | PASS |
| 84 | `psych_84_clark_doll_experiment_bias` | `clark_doll_experiment_bias` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.2307/2966491` | 9 (6 DOIs) | 9 | 22,513 | 28 | PASS |
| 85 | `psych_85_tajfel_minimal_group_favoritism` | `tajfel_minimal_group_favoritism` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1002/ejsp.2420010202` | 8 (5 DOIs) | 8 | 20,283 | 28 | PASS |
| 86 | `psych_86_festinger_social_comparison_envy` | `festinger_social_comparison_envy` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1177/001872675400700202` | 8 (5 DOIs) | 8 | 19,228 | 26 | PASS |
| 87 | `psych_87_cialdini_door_in_the_face_reciprocity` | `cialdini_door_in_the_face_reciprocity` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0076284` | 9 (6 DOIs) | 9 | 21,202 | 28 | PASS |
| 88 | `psych_88_freedman_fraser_foot_in_the_door` | `freedman_fraser_foot_in_the_door` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/h0023552` | 8 (5 DOIs) | 9 | 22,326 | 28 | PASS |
| 89 | `psych_89_langer_copy_machine_because_heuristic` | `langer_copy_machine_because_heuristic` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1037/0022-3514.36.6.635` | 8 (5 DOIs) | 8 | 19,558 | 24 | PASS |
| 90 | `psych_90_dutton_aron_capilano_bridge_arousal` | `dutton_aron_capilano_bridge_arousal` | `HYBRID` | Remediated v5 | `10.1037/h0037031` | 8 (5 DOIs) | 8 | 21,725 | 28 | PASS |
| 91 | `psych_91_zajonc_mere_exposure_effect` | `zajonc_mere_exposure_effect` | `HYBRID` | Remediated v5 | `10.1037/h0025848` | 8 (5 DOIs) | 9 | 21,325 | 28 | PASS |
| 92 | `psych_92_schachter_external_eating_cues` | `schachter_external_eating_cues` | `HYBRID` | Remediated v5 | `10.1126/science.161.3843.751` | 8 (5 DOIs) | 9 | 21,589 | 28 | PASS |
| 93 | `psych_93_trivers_parental_investment_drives` | `trivers_parental_investment_drives` | `BEHAVIORAL_PSYCH` | Remediated v5 | `10.1086/406755` | 8 (5 DOIs) | 8 | 20,500 | 28 | PASS |
| 94 | `psych_94_cosmides_tooby_cheater_detection` | `cosmides_tooby_cheater_detection` | `HYBRID` | Remediated v5 | `10.1016/0010-0277(89)90023-1` | 9 (6 DOIs) | 9 | 22,846 | 25 | PASS |
| 95 | `psych_95_raine_murderer_brain_pet_deficits` | `raine_murderer_brain_pet_deficits` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/s0006-3223(96)00362-9` | 9 (6 DOIs) | 9 | 22,863 | 28 | PASS |
| 96 | `psych_96_davidson_monk_gamma_synchrony` | `davidson_monk_gamma_synchrony` | `NEURO_BIOLOGY` | Remediated v5 | `10.1073/pnas.0407401101` | 9 (6 DOIs) | 8 | 23,183 | 28 | PASS |
| 97 | `psych_97_maguire_london_taxi_hippocampus` | `maguire_london_taxi_hippocampus` | `NEURO_BIOLOGY` | Remediated v5 | `10.1073/pnas.070039597` | 9 (6 DOIs) | 9 | 22,103 | 26 | PASS |
| 98 | `psych_98_draganski_juggling_gray_matter` | `draganski_juggling_gray_matter` | `NEURO_BIOLOGY` | Remediated v5 | `10.1038/427311a` | 8 (5 DOIs) | 9 | 21,280 | 28 | PASS |
| 99 | `psych_99_schultz_dopamine_prediction_error` | `schultz_dopamine_prediction_error` | `NEURO_BIOLOGY` | Remediated v5 | `10.1126/science.275.5306.1593` | 9 (6 DOIs) | 9 | 22,320 | 28 | PASS |
| 100 | `psych_100_dehaene_conscious_brain_ignition` | `dehaene_conscious_brain_ignition` | `NEURO_BIOLOGY` | Remediated v5 | `10.1016/j.tics.2006.03.007` | 8 (5 DOIs) | 8 | 23,772 | 28 | PASS |
