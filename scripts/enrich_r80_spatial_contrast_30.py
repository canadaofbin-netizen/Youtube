#!/usr/bin/env python3
"""
Batch-enriches all 30 Golden Queue Schema v2 dossiers (+ Ep #9 `maguire_london_taxi_hippocampus`)
with bespoke study-grounded `Rule R80` `spatial_contrast_spec` metadata inside `03_visual_reference.json`
and mirrors the summary into `BCI_Shorts_Channel/topic_priority_queue.json`.
"""

from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.research_dossier import validate_dossier

DOSSIERS_DIR = ROOT / "BCI_Shorts_Channel" / "research_dossiers"
QUEUE_PATH = ROOT / "BCI_Shorts_Channel" / "topic_priority_queue.json"


def _atomic_write_json(path: Path, obj: Any) -> None:
    tmp = path.parent / f".{path.name}.tmp.{os.getpid()}"
    tmp.write_text(json.dumps(obj, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    os.replace(tmp, path)


R80_SPECS: dict[str, dict[str, Any]] = {
    "maguire_london_taxi_hippocampus": {
        "landmark_or_object_a": "London Eye observation wheel & tangled 25,000-street London black-cab maze",
        "landmark_or_object_b": "London red circular roundel bus stop & fixed straight double-decker bus boulevard",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "contrast_arrow_3d_mode": "fixed_linear_corridor",
        "target_act": 4,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past the London Eye wheel ascending steeply into the London skyline",
        "cut_b_topdown_3d_arrow": "90-degree top-down London street labyrinth with #FF2525 3D zigzag cab arrows vs single straight bus corridor",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "hauglund_2025_sleep_pill_norepinephrine_brain_wash": {
        "landmark_or_object_a": "Natural dark bedroom window & rhythmic pulsing perivascular fluid channels",
        "landmark_or_object_b": "Bedside Zolpidem pill blister & flattened stalled fluid corridor",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 4,
        "cut_a_landmark_drone": "Fast 3D aerial sweep from moonlit Copenhagen research institute facade into quiet bedroom nightstand",
        "cut_b_topdown_3d_arrow": "90-degree top-down comparison track with pulsing cyan 3D fluid arrows vs shortened muted #FF2525 sedated lane",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "janata_music_nostalgia_alzheimers_spared_hub": {
        "landmark_or_object_a": "Backyard barbecue patio where a new acquaintance's name fades in 5 seconds",
        "landmark_or_object_b": "1985 car stereo cassette deck unlocking a lifelong multi-turn memory highway",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep from UC Davis campus courtyard down to a sunlit parked vintage sedan",
        "cut_b_topdown_3d_arrow": "90-degree top-down life-timeline neighborhood where #FF2525 3D arrows weave across 1985 teen landmarks",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "v2_sleep_first_night_hemisphere_watch": {
        "landmark_or_object_a": "Unfamiliar hotel hallway & Night-1 half-awake sentinel bed side",
        "landmark_or_object_b": "Familiar Night-2 bedroom & symmetrical deep-sleep stillness",
        "arrow_3d_mode": "split_hemisphere_watch",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming an illuminated hotel exterior sign-free portico and ascending above the roof",
        "cut_b_topdown_3d_arrow": "90-degree top-down hotel suite floorplan where #FF2525 3D sound-alert arrows patrol the left corridor while the right side rests",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "radvansky_doorway_effect_memory_boundary": {
        "landmark_or_object_a": "Single continuous 10-foot living-room walk keeping memory intact",
        "landmark_or_object_b": "10-foot walk crossing an open kitchen doorway threshold where the memory track snaps",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Notre Dame Golden Dome ascending into an architectural house cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down two-room floorplan where a solid #FF2525 3D extruded arrow fractures cleanly at the doorway frame",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "hilditch_snooze_button_sleep_inertia": {
        "landmark_or_object_a": "Single crisp morning alarm & straight sunlit hallway walk",
        "landmark_or_object_b": "Repeated 9-minute snooze alarm loop & zig-zagging groggy kitchen stumble",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming sunlit suburban rooftops as morning light hits a bedroom window",
        "cut_b_topdown_3d_arrow": "90-degree top-down apartment layout comparing fast cyan brainstem wake lane vs lagging #FF2525 25-minute prefrontal track",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "yiweng_2025_walking_steps_tau_alzheimers_brake": {
        "landmark_or_object_a": "Sedentary indoor sofa loop (<2,000 daily steps)",
        "landmark_or_object_b": "Sunlit Boston tree-lined park loop crossing 5,000–7,500 daily steps",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Massachusetts General / Harvard stone colonnade rising over Charles River park paths",
        "cut_b_topdown_3d_arrow": "90-degree top-down neighborhood park grid with thick #FF2525 3D walking-route arrows connecting four green plaza pins",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "kaptchuk_open_label_placebo_pain_switch": {
        "landmark_or_object_a": "Empty waiting-room bench with untreated recurring pain",
        "landmark_or_object_b": "Harvard clinic pharmacy counter & open-label amber capsule ritual",
        "arrow_3d_mode": "fixed_linear_corridor",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming Harvard Longwood marble courtyard columns ascending steeply skyward",
        "cut_b_topdown_3d_arrow": "90-degree top-down clinic corridor with a straight #FF2525 3D conditioned-ritual arrow driving straight to the relief checkpoint",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "thanarajah_2023_2025_ultraprocessed_snack_reward_rewiring": {
        "landmark_or_object_a": "Daily sugary high-fat snack shelf detour over 8 weeks",
        "landmark_or_object_b": "Calorie-matched low-fat whole-food aisle corridor",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Max Planck / Yale stone laboratory courtyard rising into a miniature market grid",
        "cut_b_topdown_3d_arrow": "90-degree top-down grocery aisle maze where #FF2525 3D craving arrows veer repeatedly toward the sweet-snack island",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "tubbs_mind_after_midnight_3am_spiral": {
        "landmark_or_object_a": "Dark 3:00 AM bedroom spiral loop with offline frontal brake",
        "landmark_or_object_b": "Bright 8:00 AM sunlit sidewalk straight problem-solving path",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep over moonlit city rooftops ascending above a solitary lit 3 AM window",
        "cut_b_topdown_3d_arrow": "90-degree top-down bedroom-to-street cutaway contrasting tangled #FF2525 3 AM loop arrows vs straight daylight path",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "burke_tip_of_the_tongue_word_block": {
        "landmark_or_object_a": "Blocked speech bridge where forcing a forgotten name dead-ends at a gap",
        "landmark_or_object_b": "10-second phone lookup detour reconnecting meaning to pronunciation",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Claremont / sunlit garden patio tables ascending into overhead diorama view",
        "cut_b_topdown_3d_arrow": "90-degree top-down pathway where a thick #FF2525 3D arrow snaps across a mid-corridor gap when forcing a stuck word",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "brooks_power_nap_10min_vs_30min_grogginess": {
        "landmark_or_object_a": "Crisp 10-minute light-nap express lane launching straight into 155-minute focus",
        "landmark_or_object_b": "30-minute deep slow-wave pitfall trench causing heavy sleep inertia",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past sunlit university sleep-lab courtyard ascending into roof cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down dual timeline lanes comparing fast cyan 10-minute nap track overtaking stalled #FF2525 30-minute lane",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "oconnor_deja_vu_frontal_fact_check": {
        "landmark_or_object_a": "Brand-new stone courtyard matching the geometric layout of an older forgotten plaza",
        "landmark_or_object_b": "Frontal reality-check checkpoint catching the false-familiarity overlap",
        "arrow_3d_mode": "split_hemisphere_watch",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming St Andrews stone quad arches ascending into vertical bird's-eye view",
        "cut_b_topdown_3d_arrow": "90-degree top-down twin courtyard grid with parallel cyan and #FF2525 3D arrows revealing identical spatial geometry",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "burns_2024_2025_night_light_circadian_mental_risk": {
        "landmark_or_object_a": "Bedroom bathed in artificial street/TV glow leaking across closed eyelids at night",
        "landmark_or_object_b": "Pitch-dark bedroom paired with bright outdoor morning park walk",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep from illuminated city streetlamp canyon rising over residential rooftops",
        "cut_b_topdown_3d_arrow": "90-degree top-down house-and-park cutaway showing #FF2525 night-light intrusion beam vs clean outdoor daylight corridor",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "eisenberger_social_rejection_physical_pain": {
        "landmark_or_object_a": "Three-person triangle ball-toss inclusion loop",
        "landmark_or_object_b": "Two-person closed back-and-forth line shutting the third player out",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep over UCLA Royce Hall brick arcades ascending above an outdoor courtyard table",
        "cut_b_topdown_3d_arrow": "90-degree top-down courtyard triangle where the #FF2525 3D pass arrow severs away from the excluded third figure",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "brooks_sleep_paralysis_rem_motor_lock": {
        "landmark_or_object_a": "Wide-awake morning eyes while brainstem motor gate sever-locks the arms",
        "landmark_or_object_b": "Single gentle toe-wiggle side path clicking the safety lock open",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past sunlit Toronto stone facade rising over a bright morning bedroom skylight",
        "cut_b_topdown_3d_arrow": "90-degree top-down bedroom cutaway where a thick #FF2525 3D motor command arrow halts cleanly at the brainstem safety gate",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "v2_relationships_coan_handholding_pain_grid": {
        "landmark_or_object_a": "Isolated solo clinic chair where threat arrows surge unchecked",
        "landmark_or_object_b": "Partner hand-clasping bridge synchronizing twin wave tracks",
        "arrow_3d_mode": "split_hemisphere_watch",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past UVA Jeffersonian Rotunda lawn ascending above the neuroimaging suite",
        "cut_b_topdown_3d_arrow": "90-degree top-down twin-chair room showing chaotic solo #FF2525 alarm arrows calming into linked cyan partner lanes",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "wegner_white_bear_suppression": {
        "landmark_or_object_a": "Forced 'Do Not Think' suppression loop ricocheting back to the desk bell",
        "landmark_or_object_b": "Single focused replacement-thought straight exit lane",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Harvard Yard red-brick gables ascending into top-down study cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down room maze where #FF2525 3D rebound arrows bounce repeatedly back to the central silver bell",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "melzack_wall_pain_gate": {
        "landmark_or_object_a": "100 m/s fast myelinated touch lane rubbing a bumped shin",
        "landmark_or_object_b": "2 m/s slow unmyelinated ache lane blocked at the spinal dorsal-horn gate",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past MIT Great Dome limestone colonnade ascending steeply into skyward view",
        "cut_b_topdown_3d_arrow": "90-degree top-down parallel nerve highway where a blazing cyan 3D arrow outruns a #FF2525 slow pain arrow to shut the gate",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "holle_contagious_itch_mirror_insula": {
        "landmark_or_object_a": "Stranger scratching across an open table triggering instant visual-to-skin relay",
        "landmark_or_object_b": "Cool palm pressure breaking the contagious scratch loop",
        "arrow_3d_mode": "fixed_linear_corridor",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming Sussex / sunlit glass atrium walkway ascending into top-down view",
        "cut_b_topdown_3d_arrow": "90-degree top-down two-seat atrium table with a straight #FF2525 3D contagion arrow leaping directly from viewer to forearm",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "v2_anxiety_kross_third_person_amygdala": {
        "landmark_or_object_a": "First-person 'I' self-talk trapping attention inside the stage spotlight",
        "landmark_or_object_b": "Stepping back via own first name onto a calm observer vantage point",
        "arrow_3d_mode": "fixed_linear_corridor",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Michigan stone auditorium portico ascending steeply above the roof",
        "cut_b_topdown_3d_arrow": "90-degree top-down auditorium stage with a straight #FF2525 3D step-back arrow creating clean psychological distance in 1 second",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "baird_shower_thought_default_mode_incubation": {
        "landmark_or_object_a": "Rigid locked desk-stare corridor stalling on one dead-end wall",
        "landmark_or_object_b": "Unstructured sunlit walk / shower detour linking distant idea nodes",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past sunlit coastal campus courtyard walkways ascending into bird's-eye view",
        "cut_b_topdown_3d_arrow": "90-degree top-down campus path maze where #FF2525 3D associative arrows connect three distant idea beacons",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "stetson_eagleman_slow_motion_crisis_memory": {
        "landmark_or_object_a": "150-foot vertical free-fall tower drop at constant real-time camera speed",
        "landmark_or_object_b": "Expanded post-hoc memory tape stretched 36% longer by amygdala recording",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep climbing alongside the tall outdoor steel free-fall tower before banking into vertical top-down view",
        "cut_b_topdown_3d_arrow": "90-degree top-down dual track comparing short cyan live-eye ruler vs 36%-longer #FF2525 amygdala memory arrow",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "jakubowski_earworm_stuck_song_motor_loop": {
        "landmark_or_object_a": "Grocery-aisle pop chorus trapping speech-motor pathways in a repetitive zigzag loop",
        "landmark_or_object_b": "Plain chewing-gum jaw rhythm severing the silent vocal rehearsal loop",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Durham stone courtyard and high-street shops ascending skyward",
        "cut_b_topdown_3d_arrow": "90-degree top-down walkway where a looping #FF2525 3D song-track arrow breaks cleanly apart the moment jaw motion starts",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "zeigarnik_uncompleted_task_loop": {
        "landmark_or_object_a": "12 completed Berlin cafe orders vanishing cleanly off the mental board",
        "landmark_or_object_b": "1 interrupted unpaid puzzle/order keeping a live #FF2525 3D alert arrow active",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past classic Berlin stone boulevard cafe terrace ascending into overhead view",
        "cut_b_topdown_3d_arrow": "90-degree top-down tabletop grid where an interrupted #FF2525 3D task arrow stops just short of the goal pin and glows",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "mcgurk_multisensory_illusion": {
        "landmark_or_object_a": "Uncovered face in bright restaurant light where lip-vision leads ear-sound by 100 ms",
        "landmark_or_object_b": "Covered mouth screen severing visual override so ears hear true 'BA'",
        "arrow_3d_mode": "dual_speed_race_lanes",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming Surrey campus courtyard into an acoustic studio cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down studio floorplan where fast cyan visual arrow arrives 100 ms ahead of #FF2525 audio arrow at the listener",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "bodamer_prosopagnosia_face_blindness": {
        "landmark_or_object_a": "Silent face-recognition corridor severed cleanly before identity recall",
        "landmark_or_object_b": "Spoken voice detour routing around the face block straight to instant recognition",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past classical European stone clinic courtyard ascending into cutaway view",
        "cut_b_topdown_3d_arrow": "90-degree top-down hallway where the central #FF2525 visual-face arrow severs at a gap while a side voice lane connects",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "draganski_juggling_gray_matter": {
        "landmark_or_object_a": "90 days tracking 3 curved airborne juggling arcs expanding spatial-motion hubs",
        "landmark_or_object_b": "90 idle days with balls boxed away causing structural volume pullback",
        "arrow_3d_mode": "adaptive_landmark_zigzag",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past Regensburg stone courtyard where beginners practice three-ball arcs",
        "cut_b_topdown_3d_arrow": "90-degree top-down 3-scan timeline court with multi-turn #FF2525 3D trajectory arrows across Days 0, 90, and 180",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "rubber_hand_body_plasticity": {
        "landmark_or_object_a": "Synchronized twin paintbrush strokes merging visible rubber glove into body map",
        "landmark_or_object_b": "500-ms delayed out-of-sync strokes severing ownership across the divider board",
        "arrow_3d_mode": "split_hemisphere_watch",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past sunlit university psychology building facade into tabletop divider cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down partitioned table with twin synchronized cyan/#FF2525 3D stroke arrows converging into one body pin",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "godden_baddeley_diver_context_memory": {
        "landmark_or_object_a": "Dry Scottish harbor pier study zone vs 20-foot underwater dive platform mismatch",
        "landmark_or_object_b": "Matching underwater-to-underwater context corridor boosting word recall 46%",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep skimming a sunlit stone harbor pier and turquoise dive boat ascending into vertical top-down view",
        "cut_b_topdown_3d_arrow": "90-degree top-down split pier-and-water map where cross-boundary #FF2525 arrow severs at shoreline while matched lane stays whole",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
    "kruger_phantom_pocket_vibration_habit_false_alarm": {
        "landmark_or_object_a": "Empty trouser pocket firing false top-down vibration alert while phone rests 10 feet away",
        "landmark_or_object_b": "Relocating phone into a carry bag across the desk to reset the thigh touch map",
        "arrow_3d_mode": "doorway_boundary_sever",
        "target_act": 3,
        "cut_a_landmark_drone": "Fast 3D aerial sweep past sunlit hospital glass courtyard into doctor's workstation cutaway",
        "cut_b_topdown_3d_arrow": "90-degree top-down room showing a 10-foot gap between the silent desk phone and the #FF2525 false-alarm arrow at the pocket",
        "ricks_tempo_sec_range": [2.4, 3.2],
    },
}


def main() -> int:
    q_doc = json.loads(QUEUE_PATH.read_text(encoding="utf-8"))
    items = q_doc.get("items") or []
    assert len(items) == 30, f"Expected 30 queue items, got {len(items)}"

    enriched_count = 0
    for slug in ["maguire_london_taxi_hippocampus"] + [str(it["slug"]) for it in items]:
        spec = R80_SPECS.get(slug)
        if not spec:
            raise KeyError(f"Missing R80 spatial_contrast_spec for {slug}")
        vis_p = DOSSIERS_DIR / slug / "03_visual_reference.json"
        vis_doc = json.loads(vis_p.read_text(encoding="utf-8"))
        vis_doc["spatial_contrast_spec"] = spec
        _atomic_write_json(vis_p, vis_doc)

        rep = validate_dossier(slug, require_schema_v2=(slug != "maguire_london_taxi_hippocampus"))
        if slug != "maguire_london_taxi_hippocampus" and not rep["ready"]:
            raise RuntimeError(f"Dossier {slug} failed validate_dossier after R80 enrichment: {rep['issues']}")
        enriched_count += 1

    for it in items:
        it["spatial_contrast_spec"] = R80_SPECS[str(it["slug"])]
    q_doc["r80_spatial_enriched"] = True
    _atomic_write_json(QUEUE_PATH, q_doc)
    print(f"Successfully enriched and verified {enriched_count} dossiers (incl. 30/30 Golden Queue ready=True).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
