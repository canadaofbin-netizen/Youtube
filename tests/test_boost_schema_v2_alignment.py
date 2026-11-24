"""
Unit & Integration Tests for Milestone 1 (`/boost` Gear 1–5 Pipeline, Validator & Skill Alignment):
  1. `Schema v2` Research Dossier templates & strict validation (`everyday_domain`, 3-Layer Behavioral Psych + `>= 2015` Neuro DOIs,
     `suitability_schema_version == 2` + `reenactment_section` + `08_reenactment_edl.json`, 3-Stage `debate_ignition`)
     + `Schema v1` backward compatibility + `initialize_longform_project` / `compile_longform_plan_from_dossier` gate.
  2. Porcelain cast head consistency (`PORCELAIN_V7_CAST_STYLE`, `PorcelainWorldRule.compose`, `validate_porcelain_v7_scene`
     — smooth featureless solid matte-white egg-shaped oval heads, zero frosted-glass craniums on cast scenes).
  3. Stage 2 Open-Verdict 2-sentence `?` close (`S_{N-1}` takeaway bridge `<= 13w` + `S_N` binary `... or ...?` `<= 13w`)
     + frozen `reenact_01_ainsworth_strange_situation` regression lock.
  4. `sanitize_longform_16x9_guide_frame` aspect-preserving `4:3 -> 16:9` framing (`1440x1080` + `240px` matte side extensions,
     zero horizontal stretch, zero black pillarbox bars) + `LFQ10` `RQ1–RQ5` enforcement on Long-Form `Track A`.
  5. `CommunityManager` `Schema v2` override over `_DIORAMA_NATURAL_PACKAGES` + `script_doc["offcenter_creator_bet"]`
     + `prepare_longform_publish_package` metadata-before-comment ordering.
  6. `diorama_batch_orchestrator._is_already_completed` strictness (`porcelain_cinematic_v7` + `emma_v7` + `dynamic_us_v7` + `Schema v2`).
"""

from __future__ import annotations

import copy
import json
from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline import config, research_dossier as rd
from pipeline.depiction_rules import CastDepictionRule, PorcelainWorldRule, validate_porcelain_v7_scene
from pipeline.batch_runner import _is_already_completed
from pipeline.flow_worker import _soften_veo_false_positive_words
from pipeline.prompt_builder import build_flow_prompts
from pipeline.prompt_gate import validate_anti_clone_uniqueness, validate_production_diorama_v6
from pipeline.ref_qa import _dhash_64
from pipeline.studio.community import CommunityManager, validate_debate_pinned_comment_line1


def _populate_complete_schema_v2_dossier(
    root: Path,
    slug: str = "glymphatic_sleep_toxins",
    *,
    track: str = "track_a",
    neuro_year: int = 2019,
) -> Path:
    d = rd.init_dossier(
        slug,
        "Coupled Slow Waves and Glymphatic Sleep Clearance",
        pillar="brain_health",
        visual_mode="HYBRID",
        everyday_domain="sleep",
        schema_version=2,
        root=root,
    )
    sources = {
        "sources": [
            {
                "id": "van_dongen_2003",
                "type": "primary",
                "layer": "psychology",
                "authors": "Van Dongen HPA, Maislin G, Mullington JM, Dinges DF",
                "year": 2003,
                "title": "The cumulative cost of additional wakefulness",
                "journal": "Sleep",
                "doi": "10.1093/sleep/26.2.117",
                "verified": True,
            },
            {
                "id": "fultz_2019",
                "type": "follow_up",
                "layer": "neuroscience",
                "authors": "Fultz NE, Bonmassar G, Setsompop K, Stickgold RA, Rosen BR, Polimeni JR, Lewis LD",
                "year": neuro_year,
                "title": "Coupled electrophysiological, hemodynamic, and cerebrospinal fluid oscillations in human sleep",
                "journal": "Science",
                "doi": "10.1126/science.aax5440",
                "verified": True,
            },
            {
                "id": "eide_2021",
                "type": "follow_up",
                "layer": "neuroscience",
                "authors": "Eide PK, Vinje V, Pripp AH, Mardal KA, Ringstad G",
                "year": 2021,
                "title": "Sleep deprivation impairs molecular clearance from the human brain",
                "journal": "Brain",
                "doi": "10.1093/brain/awab298",
                "verified": True,
            },
            {
                "id": "xie_2013",
                "type": "follow_up",
                "layer": "neuroscience",
                "authors": "Xie L, Kang H, Xu Q, Nedergaard M",
                "year": 2013,
                "title": "Sleep drives metabolite clearance from the adult brain",
                "journal": "Science",
                "doi": "10.1126/science.1241224",
                "verified": True,
            },
            {
                "id": "hauglund_2025",
                "type": "follow_up",
                "layer": "neuroscience",
                "authors": "Hauglund NL, Andersen M, Tokarska K, Nedergaard M",
                "year": neuro_year if neuro_year < 2015 else 2025,
                "title": "Norepinephrine-mediated slow vasomotion drives glymphatic clearance during sleep",
                "journal": "Cell",
                "doi": "10.1016/j.cell.2024.11.027",
                "verified": True,
            },
            {
                "id": "miao_2024",
                "type": "critique",
                "authors": "Miao A, Luo T, Hsieh B, Franks NP, Wisden W",
                "year": neuro_year if neuro_year < 2015 else 2024,
                "title": "Brain clearance is reduced during sleep and anesthesia",
                "journal": "Nature Neuroscience",
                "doi": "10.1038/s41593-024-01638-y",
                "verified": True,
            },
        ],
        "followups_replications_critiques": [],
    }
    (d / "01_sources.json").write_text(json.dumps(sources, indent=2) + "\n", encoding="utf-8")

    dossier_doc = json.loads((d / "dossier.json").read_text(encoding="utf-8"))
    dossier_doc.update(
        {
            "schema_version": 2,
            "everyday_domain": "sleep",
            "visual_mode_reason": "Pairs human sleep restriction behavioral psychology with 2019 human EEG-fMRI CSF oscillation imaging.",
            "three_layer_formula": {
                "everyday_problem": "Feeling rested after six hours or sedated pills while cognitive lapses silently accumulate.",
                "psychology_experiment": {
                    "source_id": "van_dongen_2003",
                    "doi": "10.1093/sleep/26.2.117",
                    "summary": "Van Dongen et al. (2003, Sleep) proved adults restricted to six hours for fourteen nights hit two-night total-deprivation lapse rates while rating themselves barely sleepy.",
                },
                "neuroscience_mechanism": {
                    "source_id": "fultz_2019",
                    "doi": "10.1126/science.aax5440",
                    "year": neuro_year,
                    "summary": "Fultz et al. (2019, Science) imaged coupled twenty-second slow-wave EEG drops in cerebral blood volume pulling pulsing cerebrospinal fluid waves into the human fourth ventricle.",
                },
                "psychology_studies": [{"source_id": "van_dongen_2003", "doi": "10.1093/sleep/26.2.117", "year": 2003}],
                "neuroscience_studies": [
                    {"source_id": "fultz_2019", "doi": "10.1126/science.aax5440", "year": neuro_year},
                    {"source_id": "hauglund_2025", "doi": "10.1016/j.cell.2024.11.027", "year": neuro_year if neuro_year < 2015 else 2025},
                ],
            },
            "debate_ignition": {
                "prebunk_myth": "Many sleepers assume eight unconscious hours on a sleeping pill washes the brain identically to natural deep sleep",
                "open_verdict_question": "Would you take five natural hours or eight sedated ones?",
                "offcenter_creator_bet": "My bet: 5 natural hours beat sleeping pills — sedatives blunt the 20-second norepinephrine pump that flushes brain waste. Honest pick: 5 natural hours or 8 sedated ones?",
            },
            "primary_case": {
                "title": "Human Coupled Slow-Wave CSF Wash & Sleep Restriction Blindness",
                "year": "2003–2025",
                "place": "University of Pennsylvania & Boston University Sleep Labs",
                "people": [
                    {"name": "Hans Van Dongen", "role": "behavioral sleep psychologist", "source": "van_dongen_2003"},
                    {"name": "Laura Lewis", "role": "human EEG-fMRI neuroscientist", "source": "fultz_2019"},
                ],
                "summary": "Behavioral restriction blinds self-awareness while slow-wave vascular oscillations physically pump CSF.",
            },
            "core_facts": [
                {"fact": f"Fact {i}: Six hours nightly for 14 days matches 48 hours without sleep in psychomotor vigilance tests.", "source_id": "van_dongen_2003"}
                for i in range(1, 7)
            ]
            + [
                {"fact": "Human CSF waves pulse every 20 seconds coupled to slow-wave EEG.", "source_id": "fultz_2019"},
                {"fact": "Zolpidem suppresses norepinephrine oscillations and glymphatic influx by over 30 percent.", "source_id": "hauglund_2025"},
            ],
            "wow_facts": [
                {"rank": 1, "fact": "Six-hour sleepers perform as poorly as two-day all-nighters yet feel nearly normal.", "source_id": "van_dongen_2003"},
                {"rank": 2, "fact": "Cerebral blood volume drops first so clear CSF surges up into the fourth ventricle.", "source_id": "fultz_2019"},
                {"rank": 3, "fact": "One sleep-deprived night leaves intrathecal MRI tracer un-cleared even after recovery sleep.", "source_id": "eide_2021"},
            ],
            "misconceptions": [
                {
                    "myth": "Unconscious sedation equals restorative slow-wave sleep",
                    "truth": "Zolpidem quiets the norepinephrine vascular waves needed to pump cerebrospinal fluid",
                    "source_id": "hauglund_2025",
                }
            ],
            "everyday_hooks": [
                "Waking foggy after eight hours on a sleep aid while five deep natural hours feel sharper."
            ],
        }
    )
    (d / "dossier.json").write_text(json.dumps(dossier_doc, indent=2) + "\n", encoding="utf-8")

    (d / "02_master_story.md").write_text(("Detailed human sleep laboratory narrative. " * 180) + "\n", encoding="utf-8")

    vis_ref = {
        "scenes": [
            {
                "id": "sleep_scanner_bay",
                "title": "EEG-Cap Sleeper Inside High-Key MRI Bore",
                "iconic": True,
                "shorts_priority": 1,
                "era": "2019 university neuroimaging sleep suite",
                "setting": "lab",
                "layout": {
                    "room": "Bright glass-walled neuroimaging control room overlooking a matte-white MRI gantry",
                    "positions": [
                        {"who": "sleeper", "where": "supine on cushioned scanner table", "facing": "upward into gantry"},
                        {"who": "researcher", "where": "seated at glass observation console", "facing": "scanner window"},
                    ],
                    "camera_axis": "side 3/4 view across observation glass",
                },
                "props": [
                    {
                        "name": "64-channel non-magnetic EEG cap",
                        "period_detail": "soft white elastic mesh cap with braided silver-white leads",
                        "physical_behavior": "rests snugly over smooth matte-white oval head inside head coil",
                    },
                    {
                        "name": "psychomotor vigilance button box",
                        "period_detail": "brushed aluminum handheld response box with single tactile button",
                        "physical_behavior": "slips slightly under sleeper's relaxed porcelain thumb",
                    },
                ],
                "key_visual": {
                    "description": "Porcelain sleeper in a white mesh EEG cap sliding into a sunlit MRI gantry while researchers watch slow waves",
                    "must_show": "64-channel non-magnetic EEG cap",
                    "source": "fultz_2019",
                },
                "wardrobe": "soft slate cotton sleep shirt on sleeper; crisp white lab coat over navy knit on researcher",
                "lighting": "soft high-key daylight diffused through frosted acoustic panels",
                "actions": ["researcher secures white EEG mesh ribbon", "table glides smoothly into white scanner ring"],
                "reactions": ["sleeper's porcelain shoulders settle into deep stillness"],
                "recognition_hook": "EEG cap inside an MRI bore capturing real human sleep waves",
                "sources": ["fultz_2019"],
            }
        ],
        "cast": [
            {"id": "sleeper", "role": "sleep study volunteer", "wardrobe": "soft slate cotton sleep shirt"},
            {"id": "researcher", "role": "neuroimaging sleep researcher", "wardrobe": "white lab coat over navy sweater"},
        ],
    }
    (d / "03_visual_reference.json").write_text(json.dumps(vis_ref, indent=2) + "\n", encoding="utf-8")

    media_refs = {
        "suitability_schema_version": 2,
        "reenactment_track": track,
        "track_selection_reason": "Archival sleep-lab EEG-fMRI experiment footage audited for Track A." if track == "track_a" else "Scene bible Track B.",
        "primary_reenactment_media_id": "bu_sleep_lab" if track == "track_a" else "",
        "media": [
            {
                "id": "bu_sleep_lab",
                "kind": "video",
                "title": "Human Sleep EEG-fMRI CSF Waves Laboratory Demonstration",
                "url": "https://www.youtube.com/watch?v=dQw4w9WgXcQ",
                "reenactment_suitability": "suitable_track_a" if track == "track_a" else "reject_track_b_only",
                "reenactment_section": "00:12-01:05" if track == "track_a" else "",
                "analysis": {"local_dir": "media/bu_sleep_lab", "keyframe_count": 9},
                "timecodes": [
                    {"t": "00:15", "what": "Researcher fits 64-channel white mesh EEG cap onto seated participant in bright prep bay, 8s"},
                    {"t": "00:42", "what": "Participant lies supine on white MRI table sliding into scanner bore while console monitors trace slow waves, 11s"},
                ],
            },
            {
                "id": "upenn_pvt_lab",
                "kind": "video",
                "title": "Psychomotor Vigilance Task Sleep Restriction Lab Footage",
                "url": "https://www.youtube.com/watch?v=9bZkp7q19f0",
                "reenactment_suitability": "reject_track_b_only",
                "timecodes": [
                    {"t": "00:10", "what": "Fatigued participant holds handheld button box at desk missing reaction cue, 7s"},
                    {"t": "00:28", "what": "Technician reviews overnight polysomnography strip beside observation window, 9s"},
                ],
            },
        ],
    }
    (d / "04_media_refs.json").write_text(json.dumps(media_refs, indent=2) + "\n", encoding="utf-8")

    # Populate analyzed keyframes on disk
    kf_dir = d / "media" / "bu_sleep_lab" / "keyframes"
    kf_dir.mkdir(parents=True, exist_ok=True)
    dummy_kf = np.full((180, 320, 3), 210, dtype=np.uint8)
    for idx in range(9):
        cv2.imwrite(str(kf_dir / f"kf_{idx:02d}.jpg"), dummy_kf)
    (d / "media" / "bu_sleep_lab" / "analysis.json").write_text(
        json.dumps({"keyframe_count": 9, "section": "00:12-01:05"}, indent=2) + "\n",
        encoding="utf-8",
    )

    if track == "track_a":
        edl_doc = {
            "slug": slug,
            "shot_count": 4,
            "sanitization_verified": True,
            "section": "00:12-01:05",
            "shots": [
                {"shot_index": i, "start_sec": float(i * 4), "end_sec": float(i * 4 + 4), "dhash": f"{i:016x}"}
                for i in range(1, 5)
            ],
        }
        (d / "08_reenactment_edl.json").write_text(json.dumps(edl_doc, indent=2) + "\n", encoding="utf-8")

    plain = {
        "one_sentence_story": "Restricting sleep blinds your sense of fatigue while sedatives mute the vascular pump that washes your brain.",
        "so_what_for_you": "Protecting natural slow-wave sleep keeps the twenty-second cerebrospinal fluid wash running.",
        "jargon_map": [
            {
                "jargon": "glymphatic system",
                "plain": "brain fluid wash channels",
                "analogy": "a city street-sweeper flushing narrow alleys after midnight traffic stops",
            }
        ],
    }
    (d / "05_plain_language.json").write_text(json.dumps(plain, indent=2) + "\n", encoding="utf-8")

    brain_link = {
        "visual_mode": "HYBRID",
        "links": [
            {
                "region": "brainstem",
                "plain": "locus coeruleus vascular pacemaker",
                "function": "regulates arousal and slow norepinephrine vascular waves during non-REM sleep",
                "story_role": "drives 20-second vessel contractions that pump CSF",
                "linked_scene_id": "sleep_scanner_bay",
                "narration_bridge": "Deep in the brainstem, slow chemical pulses squeeze blood vessels like a rhythmic bellows.",
                "source_id": "hauglund_2025",
            }
        ],
    }
    (d / "06_brain_link.json").write_text(json.dumps(brain_link, indent=2) + "\n", encoding="utf-8")

    outline = {
        "target_minutes": 9,
        "chapters": [
            {"chapter": i, "title": f"Chapter {i}", "beats": ["Setup", "Experiment", "Brain mechanism"], "new_shots_needed": ["Close-up EEG cap"]}
            for i in range(1, 6)
        ],
        "shorts_extract": {
            "hook": "Six hours of sleep feels fine while reaction lapses match two sleepless nights.",
            "core_experiment": "Coupled human EEG-fMRI reveals 20-second CSF waves during natural slow-wave sleep.",
            "twist": "Sleeping pills induce unconsciousness while blunting the norepinephrine pump.",
        },
    }
    (d / "07_longform_outline.json").write_text(json.dumps(outline, indent=2) + "\n", encoding="utf-8")
    return d


def test_schema_v2_dossier_validation_and_longform_init_gate(tmp_path: Path):
    d_root = tmp_path / "dossiers"
    d_dir = _populate_complete_schema_v2_dossier(d_root, "glymphatic_sleep_toxins", track="track_a", neuro_year=2019)

    val_ok = rd.validate_dossier("glymphatic_sleep_toxins", root=d_root, require_schema_v2=True)
    assert val_ok["ready"] is True, f"Unexpected Schema v2 issues: {val_ok['issues']}"
    assert val_ok["schema_version"] == 2

    # 1. Neuro paper older than 2015 must fail Schema v2
    _populate_complete_schema_v2_dossier(d_root, "old_neuro_only", track="track_b", neuro_year=2012)
    val_old = rd.validate_dossier("old_neuro_only", root=d_root, require_schema_v2=True)
    assert val_old["ready"] is False
    assert any("2015" in x for x in val_old["issues"])

    # 2. Track A missing 08_reenactment_edl.json or reenactment_section must fail
    (d_dir / "08_reenactment_edl.json").unlink()
    val_no_edl = rd.validate_dossier("glymphatic_sleep_toxins", root=d_root, require_schema_v2=True)
    assert val_no_edl["ready"] is False
    assert any("08_reenactment_edl.json" in x for x in val_no_edl["issues"])

    # 3. Schema v1 backward compatibility when require_schema_v2=False, rejected when require_schema_v2=True
    d_v1_doc = json.loads((d_dir / "dossier.json").read_text(encoding="utf-8"))
    d_v1_doc["schema_version"] = 1
    d_v1_doc.pop("everyday_domain", None)
    d_v1_doc.pop("three_layer_formula", None)
    d_v1_doc.pop("debate_ignition", None)
    (d_dir / "dossier.json").write_text(json.dumps(d_v1_doc, indent=2), encoding="utf-8")
    assert rd.validate_dossier("glymphatic_sleep_toxins", root=d_root, require_schema_v2=False)["ready"] is True
    assert rd.validate_dossier("glymphatic_sleep_toxins", root=d_root, require_schema_v2=True)["ready"] is False


def test_porcelain_cast_head_consistency_zero_frosted_cranium():
    assert "frosted-glass cranium" not in config.PORCELAIN_V7_CAST_STYLE.lower()
    assert "smooth featureless solid matte-white egg-shaped oval heads" in config.PORCELAIN_V7_CAST_STYLE.lower()

    rule = PorcelainWorldRule()
    # Legacy scene containing 'with translucent frosted-glass craniums' is normalized cleanly without double-head strings
    composed = rule.compose(
        environment="bright oak laboratory room",
        action="Two porcelain figures with translucent frosted-glass craniums sit across an oak table sorting cards",
    )
    assert "frosted-glass cranium" not in composed.lower()
    assert composed.lower().count("egg-shaped oval head") == 1

    # Scene that already specifies smooth featureless head does NOT get a duplicate head clause appended
    composed_pre = rule.compose(
        environment="bright oak laboratory room",
        action="A porcelain researcher with a smooth featureless solid matte-white egg-shaped oval head adjusts a dial",
    )
    assert composed_pre.lower().count("egg-shaped oval head") == 1

    # Un-normalized frosted-glass cranium in a raw non-brain scene is flagged by validate_porcelain_v7_scene
    errs = validate_porcelain_v7_scene(
        "High-key bright studio scene where a porcelain researcher with a translucent frosted-glass cranium writes notes at a desk",
        grammar="porcelain_fullbleed_world",
    )
    assert any("frosted-glass cranium" in e.lower() for e in errs)

    # Sharded worker sanitizer replaces 'skull' with solid oval head, not frosted-glass cranium
    softened = _soften_veo_false_positive_words("Camera tracks past the figure's skull in daylight")
    assert "frosted-glass cranium" not in softened.lower()
    assert "egg-shaped oval head" in softened.lower()

    # Classic Schema v4 CastDepictionRule remains intact for legacy classic_v5 tests
    assert "frosted-glass cranium" in CastDepictionRule.cranium_clause("NEURO_BIOLOGY", "brain_void").lower()


def test_stage2_open_verdict_two_sentence_close_and_frozen_reenact_01():
    reenact_01_dir = Path(config.PROJECTS_DIR) / "reenact_01_ainsworth_strange_situation"
    if not (reenact_01_dir / "02_script" / "script.json").exists():
        pytest.skip("Optional fixture reenact_01_ainsworth_strange_situation not present on disk")
    s_doc = json.loads((reenact_01_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    vp_doc = json.loads((reenact_01_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    pr_doc = json.loads((reenact_01_dir / "03_visuals" / "flow_all_in_one_prompts.json").read_text(encoding="utf-8"))
    narrs = [str(s) for s in s_doc["sentences"]]

    # Frozen Day-1 golden benchmark reenact_01 must pass with 0 issues
    frozen_issues = validate_production_diorama_v6(vp_doc, narrs, pr_doc["clips"], script_doc=s_doc)
    assert frozen_issues == [], f"Frozen reenact_01 broke: {frozen_issues}"

    # Non-frozen Schema v2 clone ending on a declarative period MUST fail [open_verdict_v2]
    new_s = copy.deepcopy(s_doc)
    new_s["project_id"] = "diorama_31_fresh_test"
    new_s["dossier_schema_version"] = 2
    new_vp = copy.deepcopy(vp_doc)
    new_vp["project_id"] = "diorama_31_fresh_test"
    new_vp["dossier"] = "fresh_schema_v2_topic"
    new_vp["dossier_schema_version"] = 2
    decl_issues = validate_production_diorama_v6(new_vp, narrs, pr_doc["clips"], script_doc=new_s)
    assert any("[open_verdict_v2]" in x for x in decl_issues)

    # Replacing final 2 sentences with S_{N-1} takeaway bridge (<= 13w) + S_N binary '... or ...?' (<= 13w) passes!
    narrs_v2 = list(narrs)
    narrs_v2[-2] = "What this means for you is reading calm silence twice."
    narrs_v2[-1] = "Is quiet calm true safety, or hidden alarm underneath?"
    new_s["sentences"] = narrs_v2
    if isinstance(new_s.get("acts"), list) and new_s["acts"]:
        new_s["acts"][-1]["sentences"][-2] = narrs_v2[-2]
        new_s["acts"][-1]["sentences"][-1] = narrs_v2[-1]
    rebuilt_prompts = build_flow_prompts(new_vp, narrs_v2)
    v2_issues = validate_production_diorama_v6(new_vp, narrs_v2, rebuilt_prompts, script_doc=new_s)
    assert v2_issues == [], f"2-sentence open-verdict close failed: {v2_issues}"
    near_clone_corpus = [narrs_v2[:-2] + ["So next time you see silence, pause.", "Calm faces can hide storms."]]
    assert validate_anti_clone_uniqueness(narrs_v2, near_clone_corpus) != []
    assert validate_anti_clone_uniqueness(narrs_v2, []) == []






def test_batch_orchestrator_is_already_completed_rejects_legacy_profiles(tmp_path: Path):
    proj = tmp_path / "diorama_09_legacy"
    for st in ("02_script", "03_visuals", "05_assembly"):
        (proj / st).mkdir(parents=True, exist_ok=True)
    mp4 = proj / "05_assembly" / "final_shorts_1080x1920.mp4"
    mp4.write_bytes(b"0" * (2_500_000))
    (proj / "05_assembly" / "video_autopsy_report.json").write_text(json.dumps({"passed": True}), encoding="utf-8")
    (proj / "05_assembly" / "episode_qa_report.json").write_text(json.dumps({"overall_passed": True}), encoding="utf-8")
    (proj / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
        json.dumps({"episode_passed": True, "mean_clarity_score": 92.0, "weak_cut_count": 0}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "reference_image_qa_report.json").write_text(
        json.dumps({"pre_generation_ready": True}),
        encoding="utf-8",
    )
    # Legacy andrew_v7 + dynamic_rush_v7 must NOT count as completed!
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"voice_preset": "andrew_v7", "prosody_mode": "dynamic_rush_v7"}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "porcelain_cinematic_v7"}),
        encoding="utf-8",
    )
    assert _is_already_completed(proj) is False
