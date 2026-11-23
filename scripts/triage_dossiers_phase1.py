#!/usr/bin/env python3
"""
Phase 0 & Phase 1 — Baseline Lock + 6-Axis 100-Point Triage Audit of Existing Dossiers.
Outputs `BCI_Shorts_Channel/reports/research/dossier_90_triage_audit.json`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.anatomy_map import ANATOMY_FUNCTION_MAP, resolve_region
from pipeline.config import (
    DATA_STAMP_MAX_PER_EPISODE,
    DOSSIER_MIN_ANALYZED_MEDIA,
    DOSSIER_MIN_CORE_FACTS,
    DOSSIER_MIN_FOLLOWUP_SOURCES,
    DOSSIER_MIN_ICONIC_POSITIONS,
    DOSSIER_MIN_ICONIC_PROPS,
    DOSSIER_MIN_KEYFRAMES,
    DOSSIER_MIN_MEDIA,
    DOSSIER_MIN_MEDIA_TIMECODES,
    DOSSIER_MIN_SOURCES,
    DOSSIER_MIN_STORY_CHARS,
    DOSSIER_NEURO_MODERN_MIN_YEAR,
)
from pipeline.research_dossier import validate_dossier
from pipeline.studio.config import BANNED_OFF_TOPIC_TECH_TAGS

CHANNEL_DIR = ROOT / "BCI_Shorts_Channel"

ALREADY_PUBLISHED_OR_SCHEDULED_DOSSIERS = {
    "ainsworth_strange_situation",
    "alien_hand_syndrome",
    "blakemore_cerebellar_tickle_prediction",
    "capgras_imposter_delusion",
    "clive_wearing_seven_second_mind",
    "false_memory_elizabeth_loftus",
    "feinstein_patient_sm_fearless_amygdala",
    "gilbert_reversible_choice_paradox",
    "glymphatic_sleep_toxins",
    "habit_loop_basal_ganglia",
    "hippocampal_memory_prosthesis",
    "inner_speech_decoding",
    "invisible_gorilla_attention",
    "maguire_london_taxi_hippocampus",
    "milgram_obedience_shock",
    "milner_hm_procedural_memory",
    "mischel_marshmallow_self_control",
    "patient_hm_hippocampus",
    "phineas_gage_iron_rod",
    "ramachandran_phantom_limb_mirror",
    "scullin_bedtime_todo_list_sleep",
    "sperry_split_chiasm_interhemispheric",
    "split_brain_dual_consciousness",
    "v2_habits_marshmallow_prefrontal_trust",
    "v2_memory_loftus_false_alibi_engram",
}

GATE0_SAFETY_AND_POLICY_QUARANTINE = {
    "raine_murderer_brain_pet_deficits": "homicide/violence prompt & Shorts ad-safety risk",
    "cotard_walking_corpse_syndrome": "corpse/rotting delusion Flow safety filter risk",
    "little_albert_fear_conditioning": "crying infant distress in lab policy risk",
    "harlow_cloth_mother_attachment": "infant monkey isolation cruelty visual risk",
    "zimbardo_stanford_prison_roles": "prison abuse + severe replication/coaching controversy",
    "delgado_stimoceiver_bull_stop": "animal implant + off-brand legacy BCI focus",
    "hochberg_braingate_robotic_coffee": "pure BCI hardware focus (R75 non-everyday)",
    "scangos_closed_loop_depression_dbs": "surgical psychiatric implant focus",
    "seligman_learned_helplessness": "inescapable dog shock cruelty visual risk",
    "rosenhan_sane_in_insane_places": "Cahalan 2019 fraud/fabrication controversy",
    "shapiro_emdr_trauma_saccades": "clinical PTSD trauma sensitivity + mechanism debate",
    "beck_cognitive_triad_depression": "clinical depression therapy lecture rather than visual paradox",
    "clark_doll_experiment_bias": "sensitive racial trauma involving young children",
}

# Curated 6-axis expert scoring for Track 2 selection (Everyday 25 + Age35+ 15 + R79_Action 20 + R78_Circuit 15 + R70_Quant_Rep 15 + Save_Debate 10 = 100)
EXPERT_TIER_S_SCORES: dict[str, tuple[int, int, int, int, int, int, str]] = {
    "v2_sleep_first_night_hemisphere_watch": (25, 15, 18, 15, 14, 9, "Universal hotel/travel sleep mystery; L-vs-R hemisphere asymmetry is iconic in #27D8FF 3D brain; direct sequel to surging sleep anchors."),
    "wegner_white_bear_suppression": (24, 14, 18, 14, 14, 9, "Every adult knows the 3 AM unwanted thought rebound; dual monitor-vs-operator prefrontal/ACC loop + crisp bell-ringing counteraction."),
    "v2_relationships_coan_handholding_pain_grid": (23, 15, 19, 14, 14, 9, "Visceral partner hand-holding silencing hypothalamus/insula threat grid; replicated with PNAS 2018 brain-to-brain coupling."),
    "v2_anxiety_kross_third_person_amygdala": (24, 14, 17, 14, 14, 9, "Actionable 5-second name-switching hack for adult stress; fMRI/ERP proof of rapid amygdala cooldown without effortful control."),
    "melzack_wall_pain_gate": (24, 15, 19, 13, 13, 8, "Instantly relatable rubbing-a-stubbed-shin reflex; crisp sensory touch cable outrunning pain fibers to shut spinal/thalamic gate."),
    "zeigarnik_uncompleted_task_loop": (24, 14, 17, 13, 13, 9, "Explains why one unfinished email haunts adults at night and how a 60-second plan shuts off the dorsolateral prefrontal alarm."),
    "rubber_hand_body_plasticity": (22, 13, 20, 14, 14, 8, "Unbeatable 2-second visual prop action (paintbrush + rubber hand + sudden hammer flinch); direct kin to 1,250-view Phantom Mirror Box."),
    "mcgurk_multisensory_illusion": (23, 14, 18, 14, 13, 9, "Viewer experiences visual-auditory hijacking directly; visual cortex overrides auditory cortex in real time."),
    "godden_baddeley_diver_context_memory": (21, 13, 19, 13, 15, 8, "40%+ recall swing underwater vs dry land; striking outdoor diving visuals (R72) + hippocampal context-tag mechanism."),
    "bodamer_prosopagnosia_face_blindness": (21, 14, 18, 15, 13, 8, "Seeing eyes and nose clearly yet failing to recognize family or oneself in a mirror; razor-sharp fusiform face area lesion contrast."),
    "kanwisher_fusiform_face_area": (21, 13, 17, 15, 13, 8, "Upside-down Thatcher face illusion + discovery of the brain's dedicated face patch."),
    "dutton_aron_capilano_bridge_arousal": (21, 13, 19, 13, 12, 8, "Swaying 230-foot suspension bridge outdoor spectacle (R72); amygdala/insula heartbeat misattributed as attraction."),
    "draganski_juggling_gray_matter": (21, 15, 19, 14, 14, 8, "Adult brains growing measurable visual-motion gray matter in 3 months of learning 3-ball juggling (replicated in older adults!)."),
}

TEXTBOOK_LOW_VISUAL_KEYWORDS = (
    "law_of_effect",
    "levels_of_processing",
    "global_workspace",
    "iconic_memory_buffer",
    "attenuation_selective",
    "wason_selection",
    "magical_number_seven",
    "forgetting_curve",
    "mental_rotation",
    "operant_superstition",
    "classical_conditioning",
    "dogs_conditioning",
    "synaptic_learning_rule",
    "aplysia",
    "visual_orientation",
    "place_grid_cells",
    "cheater_detection",
    "parental_investment",
    "minimal_group",
    "pygmalion",
    "stereotype_threat",
    "overjustification",
    "insufficient_reward",
    "foot_in_the_door",
    "door_in_the_face",
)


def atomic_write_json(path: Path, data: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp.write_text(json.dumps(data, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


def main() -> None:
    print(
        "CONSTS:",
        {
            "DOSSIER_NEURO_MODERN_MIN_YEAR": DOSSIER_NEURO_MODERN_MIN_YEAR,
            "DOSSIER_MIN_SOURCES": DOSSIER_MIN_SOURCES,
            "DOSSIER_MIN_FOLLOWUP_SOURCES": DOSSIER_MIN_FOLLOWUP_SOURCES,
            "DOSSIER_MIN_CORE_FACTS": DOSSIER_MIN_CORE_FACTS,
            "DOSSIER_MIN_STORY_CHARS": DOSSIER_MIN_STORY_CHARS,
            "DOSSIER_MIN_MEDIA": DOSSIER_MIN_MEDIA,
            "DOSSIER_MIN_MEDIA_TIMECODES": DOSSIER_MIN_MEDIA_TIMECODES,
            "DOSSIER_MIN_ANALYZED_MEDIA": DOSSIER_MIN_ANALYZED_MEDIA,
            "DOSSIER_MIN_KEYFRAMES": DOSSIER_MIN_KEYFRAMES,
            "DOSSIER_MIN_ICONIC_POSITIONS": DOSSIER_MIN_ICONIC_POSITIONS,
            "DOSSIER_MIN_ICONIC_PROPS": DOSSIER_MIN_ICONIC_PROPS,
            "DATA_STAMP_MAX_PER_EPISODE": DATA_STAMP_MAX_PER_EPISODE,
            "ANATOMY_REGIONS": len(ANATOMY_FUNCTION_MAP),
            "BANNED_TECH_TAGS": len(BANNED_OFF_TOPIC_TECH_TAGS),
        }
    )

    pub_dois: set[str] = set()
    for rec_p in sorted((CHANNEL_DIR / "projects").glob("*/06_publish/upload_receipt.json")):
        r = json.loads(rec_p.read_text(encoding="utf-8"))
        if not r.get("video_id"):
            continue
        meta_p = rec_p.parent / "metadata.json"
        if meta_p.exists():
            m = json.loads(meta_p.read_text(encoding="utf-8"))
            for k in ("doi", "secondary_doi", "mechanism_doi"):
                if m.get(k):
                    pub_dois.add(str(m[k]).lower().strip())

    records = []
    for dp in sorted((CHANNEL_DIR / "research_dossiers").iterdir()):
        if not dp.is_dir() or not (dp / "dossier.json").exists():
            continue
        slug = dp.name
        d = json.loads((dp / "dossier.json").read_text(encoding="utf-8"))
        srcs_doc = json.loads((dp / "01_sources.json").read_text(encoding="utf-8"))
        srcs = srcs_doc.get("sources") or []
        dois = [str(s.get("doi") or "").lower().strip() for s in srcs if isinstance(s, dict) and s.get("doi")]
        brain_doc = json.loads((dp / "06_brain_link.json").read_text(encoding="utf-8")) if (dp / "06_brain_link.json").exists() else {}
        regions = [str(l.get("region") or "") for l in (brain_doc.get("links") or []) if isinstance(l, dict)]
        atlas_ok = all(resolve_region(rg) is not None for rg in regions) if regions else False
        vr = validate_dossier(slug, require_schema_v2=True)

        if slug in ALREADY_PUBLISHED_OR_SCHEDULED_DOSSIERS:
            bucket = "already_published_or_scheduled"
            total_score = 0
            rationale = "Already published or scheduled on @AllAboutBrainOfficial (or direct duplicate dossier)."
            breakdown = {}
        elif slug in GATE0_SAFETY_AND_POLICY_QUARANTINE:
            bucket = "quarantined_gate0"
            total_score = 0
            rationale = GATE0_SAFETY_AND_POLICY_QUARANTINE[slug]
            breakdown = {}
        elif slug in EXPERT_TIER_S_SCORES:
            s1, s2, s3, s4, s5, s6, rationale = EXPERT_TIER_S_SCORES[slug]
            total_score = s1 + s2 + s3 + s4 + s5 + s6
            bucket = "tier_s_selected_track2" if total_score >= 88 else "tier_a_reserve"
            breakdown = {
                "everyday_self_relevance_25": s1,
                "adult_35plus_fit_15": s2,
                "r79_prop_action_20": s3,
                "r78_circuit_contrast_15": s4,
                "r70_quant_replication_15": s5,
                "debate_saveability_10": s6,
            }
        elif any(k in slug for k in TEXTBOOK_LOW_VISUAL_KEYWORDS):
            bucket = "quarantined_textbook_low_visual"
            total_score = 58
            rationale = "Classic textbook theory or static desk/screen task; low 2-second visual hook for Shorts feed."
            breakdown = {}
        else:
            bucket = "tier_b_backlog"
            total_score = 74
            rationale = "Valid Schema v2 dossier, held in reserve below 85-point Golden Slate threshold."
            breakdown = {}

        records.append(
            {
                "slug": slug,
                "topic": d.get("topic", ""),
                "pillar": d.get("pillar", ""),
                "everyday_domain": d.get("everyday_domain", ""),
                "bucket": bucket,
                "total_score": total_score,
                "score_breakdown": breakdown,
                "rationale": rationale,
                "schema_v2_ready": bool(vr.get("ready")),
                "atlas_31_compatible": atlas_ok,
                "regions": regions,
                "primary_dois": dois[:3],
                "overlaps_published_doi": [x for x in dois[:1] if x in pub_dois],
            }
        )

    records.sort(key=lambda x: (-x["total_score"], x["slug"]))
    tier_s = [r for r in records if r["total_score"] >= 85 and r["bucket"].startswith("tier_")]
    selected_track2_11 = tier_s[:11]
    for r in selected_track2_11:
        r["bucket"] = "tier_s_selected_track2"
    for r in tier_s[11:]:
        r["bucket"] = "tier_a_reserve"

    out_doc = {
        "schema_version": 1,
        "total_dossiers_scanned": len(records),
        "published_doi_blacklist": sorted(pub_dois),
        "counts": {
            "already_published_or_scheduled": sum(1 for r in records if r["bucket"] == "already_published_or_scheduled"),
            "quarantined_gate0": sum(1 for r in records if r["bucket"] == "quarantined_gate0"),
            "quarantined_textbook_low_visual": sum(1 for r in records if r["bucket"] == "quarantined_textbook_low_visual"),
            "tier_s_selected_track2": len(selected_track2_11),
            "tier_a_reserve": sum(1 for r in records if r["bucket"] == "tier_a_reserve"),
            "tier_b_backlog": sum(1 for r in records if r["bucket"] == "tier_b_backlog"),
        },
        "selected_track2_top11": [
            {
                "rank": idx + 1,
                "slug": r["slug"],
                "score": r["total_score"],
                "pillar": r["pillar"],
                "everyday_domain": r["everyday_domain"],
                "regions": r["regions"],
                "rationale": r["rationale"],
            }
            for idx, r in enumerate(selected_track2_11)
        ],
        "records": records,
    }
    out_path = CHANNEL_DIR / "reports" / "research" / "dossier_90_triage_audit.json"
    atomic_write_json(out_path, out_doc)
    print("WROTE:", out_path)
    print("COUNTS:", out_doc["counts"])
    for item in out_doc["selected_track2_top11"]:
        print(f"  TRACK2 #{item['rank']:02d} [{item['score']} pts] {item['slug']} ({item['everyday_domain']} / {item['pillar']})")


if __name__ == "__main__":
    main()
