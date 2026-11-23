#!/usr/bin/env python3
"""
Builds the clean Rule R82 remake project `v8_ep09_maguire_london_taxi_hippocampus_r82`
without touching the frozen live `Public` baseline `v8_ep09_maguire_london_taxi_hippocampus` (`tWjrK5enOoM`).

Upgrades vs v1 (`v8_ep09`):
  1. Restores the missing University College London Wilkins Portico & Dome aerial drone shot (`Clip 03` -> `Clip 04` 3T MRI breach).
  2. Eliminates all 5.2–5.9s static human filler scenes via crisp 2.0–2.6s 2-beat experimental relays (`Clip 01..08`, `Clip 13..16`).
  3. Expands poised 3D Brain scenes from 39.7% -> ~51%+ duration (`8` steady `<=12°` parallax cuts @ ~5.0–5.6s, zero frantic 90° spin) + XL `R81` callouts.
  4. Adds dedicated Side-by-Side 3D Brain Hippocampus Comparison (`Taxi Hippocampus` giant vs `Bus Hippocampus` flat, `Clip 17`)
     plus 2 verified R70-M study Data Stamps (`39/79 Trainees` Woollett & Maguire 2011 + `21.3 vs 17.3` Rey Shape Recall Maguire et al. 2006).
  5. Ready for 100% `Omni 1.2 Flash` (`--engine omni`) generation (`v1` used `0-credit` `Veo 3.1 - Lite`).
"""

from __future__ import annotations

from datetime import datetime, timezone
import json
import os
import shutil
import sys
from pathlib import Path
from typing import Any

sys.dont_write_bytecode = True
os.environ.setdefault("PYTHONDONTWRITEBYTECODE", "1")

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from pipeline.dynamic_episode_qa import compile_episode_qa_contract
from pipeline.flow_prompt_builder import build_flow_prompts, write_flow_prompts_json
from pipeline.reference_image_qa import build_reference_image_specs, register_reference_image


PROJECT_ID = "v8_ep09_maguire_london_taxi_hippocampus_r82"
OLD_PROJECT_ID = "v8_ep09_maguire_london_taxi_hippocampus"


def _atomic_write_json(path: Path, payload: Any) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    rendered = json.dumps(payload, indent=2, ensure_ascii=False) + "\n"
    if path.is_file() and path.read_text(encoding="utf-8") == rendered:
        return
    tmp = path.with_name(f".{path.name}.tmp")
    tmp.write_text(rendered, encoding="utf-8")
    tmp.replace(path)


def main() -> int:
    proj_dir = ROOT / "BCI_Shorts_Channel" / "projects" / PROJECT_ID
    old_dir = ROOT / "BCI_Shorts_Channel" / "projects" / OLD_PROJECT_ID
    for stage in ("01_ideation", "02_script", "03_visuals/reference_images", "04_audio", "05_assembly", "06_publish", "logs"):
        (proj_dir / stage).mkdir(parents=True, exist_ok=True)

    sentences = [
        "Ditching phone maps doesn't just test your memory, it reshapes your adult brain!",
        "To prove it, University College London doctors scanned cabbies who learned twenty-five thousand streets.",
        "Without phone maps, trainees ride mopeds in the rain to learn twenty thousand landmarks.",
        "For years, textbooks claimed adult brains stay fixed in size once you grow up.",
        "Yet street views hit the eyes and race to the vision spot in back.",
        "From there, the brain's memory hub, the hippocampus, weaves each turn into one live map.",
        "On brain scans, cabbies grew way more gray matter in the back of their hippocampus.",
        "Across sixteen cabbies and fifty controls, the more years they drove, the larger it grew.",
        "Wait, what if loud city traffic, not map skill, made their brains grow?",
        "So doctors scanned eighteen cabbies and seventeen London bus drivers on fixed routes.",
        "Side by side, cabbies grew a giant rear map while bus drivers stayed flat.",
        "That's because live detour choices force your sense of place and hippocampus to link up.",
        "When seventy-nine trainees started equal, just the thirty-nine who passed four years later grew.",
        "Wait, did cabbies get that giant street map for free?",
        "Not quite: as their rear map grew, the front of their hippocampus shrank.",
        "That front spot helps grab brand-new shapes on the first try.",
        "On new shapes, bus drivers scored twenty-one point three to cabbies' seventeen point three, trading space.",
    ]
    display_sentences = [
        "Ditching phone maps doesn't just test your memory, it reshapes your adult brain!",
        "To prove it, University College London doctors scanned cabbies who learned 25,000 streets.",
        "Without phone maps, trainees ride mopeds in the rain to learn 20,000 landmarks.",
        "For years, textbooks claimed adult brains stay fixed in size once you grow up.",
        "Yet street views hit the eyes and race to the vision spot in back.",
        "From there, the brain's memory hub, the hippocampus, weaves each turn into one live map.",
        "On brain scans, cabbies grew way more gray matter in the back of their hippocampus.",
        "Across 16 cabbies and 50 controls, the more years they drove, the larger it grew.",
        "Wait, what if loud city traffic, not map skill, made their brains grow?",
        "So doctors scanned 18 cabbies and 17 London bus drivers on fixed routes.",
        "Side by side, cabbies grew a giant rear map while bus drivers stayed flat.",
        "That's because live detour choices force your sense of place and hippocampus to link up.",
        "When 79 trainees started equal, just the 39 who passed 4 years later grew.",
        "Wait, did cabbies get that giant street map for free?",
        "Not quite: as their rear map grew, the front of their hippocampus shrank.",
        "That front spot helps grab brand-new shapes on the first try.",
        "On new shapes, bus drivers scored 21.3 to cabbies' 17.3, trading space.",
    ]
    assert len(sentences) == 17 and len(display_sentences) == 17

    data_stamps = [
        {
            "sentence_index": 13,
            "mode": "study",
            "preset": "dot_array",
            "chart": "dot_array",
            "style": "ink_pen",
            "format": "dot_array",
            "title": "Trainees Who Grew Map",
            "highlighted_k": 39,
            "total_n": 79,
            "unit": "trainees",
            "duration_sec": 3.85,
            "doi": "10.1016/j.cub.2011.11.018",
            "source_citation": "Woollett & Maguire (2011)",
        },
        {
            "sentence_index": 17,
            "mode": "study",
            "preset": "bar_compare",
            "chart": "bar_compare",
            "style": "ink_pen",
            "format": "group_means",
            "title": "New Shape Recall Score",
            "unit": "pts",
            "bars": [
                {"label": "Bus Drivers", "value": 21.3, "unit": "pts"},
                {"label": "Taxi Cabbies", "value": 17.3, "unit": "pts"},
            ],
            "duration_sec": 4.05,
            "doi": "10.1002/hipo.20233",
            "source_citation": "Maguire, Woollett & Spiers (2006)",
        },
    ]

    viewer_description = (
        "To earn a licensed London black-cab badge, trainees spend three to four years riding mopeds without phone maps "
        "while memorizing twenty-five thousand streets and twenty thousand city landmarks around Charing Cross. "
        "Structural brain scans at University College London showed that licensed cabbies grew noticeably more gray matter "
        "in the back of the hippocampus, scaling upward with total years behind the wheel.\n\n"
        "Matched London bus drivers on fixed routes showed zero rear expansion, and scanning seventy-nine trainees over four years "
        "confirmed that only the thirty-nine who passed grew new rear map tissue while trading off front space and new shape recall.\n\n"
        "Research: Maguire et al., University College London (2000, 2006) and Woollett and Maguire (2011)."
    )

    script_doc = {
        "schema": 8,
        "schema_version": 8,
        "dossier_schema_version": 2,
        "project_id": PROJECT_ID,
        "title": "Why London Taxi Drivers Grew Bigger Brains",
        "pillar": "brain_health",
        "everyday_domain": "memory",
        "dossier": "maguire_london_taxi_hippocampus",
        "dossier_slug": "maguire_london_taxi_hippocampus",
        "language": "en-US",
        "doi": "10.1073/pnas.070039597",
        "secondary_doi": "10.1002/hipo.20233",
        "mechanism_doi": "10.1016/j.cub.2011.11.018",
        "profile": "neuro_diorama",
        "production_profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "shorts_format_profile": "shorts_expressive_v8",
        "topic_focus": "neuroscience",
        "prosody_mode": "expressive_us_v8",
        "voice_preset": "el_siren_v4",
        "foil_voice_preset": "",
        "foil_sentence_indices": [],
        "r72_mode": True,
        "r72_cold_open_relay": True,
        "r73_mode": True,
        "r74_mode": False,
        "r74b_mode": False,
        "r76_mode": True,
        "r76_brain_simulator": True,
        "r77n_conversational_storytelling": True,
        "r78v_5tone_siren": True,
        "r82_mode": True,
        "us_anti_clone_v7": True,
        "opening_mode": "myth_flip_claim",
        "previous_opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "core_reveal_sentence_index": 12,
        "sentence_beats": list(range(1, 18)),
        "prosody_gears": [
            "surprised_lift",
            "brisk",
            "insider_reveal",
            "brisk",
            "insider_reveal",
            "surprised_lift",
            "brisk",
            "hushed_suspense",
            "surprised_lift",
            "brisk",
            "insider_reveal",
            "insider_reveal",
            "surprised_lift",
            "surprised_lift",
            "hushed_suspense",
            "brisk",
            "deadpan_drop",
        ],
        "gap_before_sec": [
            0.0,
            0.40,
            0.18,
            0.18,
            0.20,
            0.18,
            0.20,
            0.20,
            0.34,
            0.18,
            0.20,
            0.32,
            0.18,
            0.28,
            0.18,
            0.18,
            0.22,
        ],
        "sentence_speakers": ["narrator"] * 17,
        "acts": [
            {"act": 1, "name": "Cold_Open_And_UCL_Drone", "sentences": sentences[0:3]},
            {"act": 2, "name": "Fixed_Brain_Myth_To_Map", "sentences": sentences[3:6]},
            {"act": 3, "name": "Posterior_Hippocampus_Growth", "sentences": sentences[6:8]},
            {"act": 4, "name": "Taxi_Vs_Bus_Hippocampus_Compare", "sentences": sentences[8:11]},
            {"act": 5, "name": "Detour_Wiring_And_Trainees", "sentences": sentences[11:13]},
            {"act": 6, "name": "Anterior_Shape_Memory_Tradeoff", "sentences": sentences[13:17]},
        ],
        "sentences": sentences,
        "narration_sentences": sentences,
        "display_sentences": display_sentences,
        "omit_experiment_nicknames": [],
        "viewer_description": viewer_description,
        "thumbnail": {
            "hook_text": "BRAIN GREW?!",
            "cover_sentence_index": 1,
        },
        "debate_question": "Do you still navigate local streets from memory, or do you leave turn-by-turn phone maps on everywhere?",
        "data_stamps": data_stamps,
    }

    real_world_targets = [
        {
            "target_id": "ucl_wilkins_portico",
            "category": "institution",
            "label": "University College London Wilkins Building Portico & Main Quad",
            "queries": ["Wilkins Building UCL", "University College London portico"],
            "architectural_traits": "iconic classical Portland-stone Corinthian portico dome and grand stone staircase overlooking the sunlit gravel Main Quad courtyard at University College London",
            "facade_close_traits": "fluted Portland-stone Corinthian columns, wide stone portico steps, and sunlit tall Georgian sash windows",
        },
        {
            "target_id": "charing_cross_black_cabs",
            "category": "urban_setting",
            "label": "Charing Cross & Trafalgar Square London Black Cabs & Red Buses",
            "queries": ["London black cab Trafalgar Square", "Red bus Charing Cross London"],
            "architectural_traits": "classic Portland-stone London street junction around Charing Cross and Trafalgar Square with glossy black London taxicabs and bright red double-decker buses",
        },
        {
            "target_id": "structural_mri_scanner_bore",
            "category": "scientific_apparatus",
            "label": "3T Structural Brain MRI Scanner Bore & Motorized Patient Bed",
            "queries": ["3T MRI scanner bore", "Magnetic resonance imaging scanner"],
            "architectural_traits": "clean white clinical cylindrical 3T structural MRI scanner gantry with illuminated circular bore tunnel and padded motorized sliding patient bed",
        },
        {
            "target_id": "london_eye_thames_wheel",
            "category": "urban_setting",
            "label": "London Eye Cantilevered Observation Wheel & River Thames Embankment",
            "queries": ["London Eye River Thames embankment", "London Eye South Bank"],
            "architectural_traits": "giant white cantilevered London Eye observation wheel with glass capsules rising beside the sunlit Portland-stone River Thames embankment",
        },
        {
            "target_id": "london_red_bus_stop_roundel",
            "category": "urban_setting",
            "label": "London Iconic Red Bus Stop Flag Post, Glass Shelter & Double-Decker Bus Lane",
            "queries": ["London bus stop roundel red bus", "Red double-decker bus stop London"],
            "architectural_traits": "iconic London red-and-white circular bus stop flag post, glass shelter, and bright red double-decker bus aligned along a straight Portland-stone London avenue",
        },
    ]

    def _human_clip(
        c_no: int,
        s_idx: int,
        act: int,
        scene_id: str,
        *,
        beat_index: int = 1,
        beat_weight: float = 1.0,
        grammar: str = "expressive_vinyl_world",
        camera_move: str = "gentle_push_in",
        location_id: str,
        environment: str,
        cast: str,
        cast_roles: list[str],
        action: str,
        consequence: str,
        expression_id: str = "calm_focused_nod",
        ref_filename: str,
        real_world_target_id: str | None = None,
        human_action_relay: bool = False,
        r72_cold_open_relay: bool = False,
        spatial_relay_cut: bool = False,
        arrow_3d_mode: str | None = None,
        flight_speed_ramp: float | None = None,
        crop_zoom: float = 1.0,
        src_start_sec: float | None = None,
        src_end_sec: float | None = None,
        transition_out: str = "action_impact_cut",
        full_trajectory_span: bool = False,
    ) -> dict[str, Any]:
        d: dict[str, Any] = {
            "id": c_no,
            "clip_number": c_no,
            "sentence_index": s_idx,
            "end_sentence_index": s_idx,
            "beat_index": beat_index,
            "beat_weight": beat_weight,
            "act": act,
            "scene_id": scene_id,
            "grammar": grammar,
            "visual_grammar": grammar,
            "camera": camera_move,
            "camera_move": camera_move,
            "location_id": location_id,
            "environment": environment,
            "cast": cast,
            "cast_roles": cast_roles,
            "action": action,
            "consequence": consequence,
            "expression_id": expression_id,
            "cameo_easter_egg": False,
            "transition_to_next": transition_out,
            "transition_out": transition_out,
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "reference_image": f"03_visuals/reference_images/{ref_filename}",
            "start_frame_image": f"03_visuals/reference_images/{ref_filename}",
            "end_reference_image": None,
            "end_frame_image": None,
            "single_start_frame_lock": True,
            "brain_clip": False,
            "render_engine": "google_flow",
            "flow_input_mode": "VIDEO_FRAMES",
            "full_trajectory_span": full_trajectory_span,
            "dual_keyframe_parallax": False,
            "real_world_target_id": real_world_target_id,
            "human_action_relay": human_action_relay,
            "r72_cold_open_relay": r72_cold_open_relay,
        }
        if crop_zoom > 1.001:
            d["crop_zoom"] = round(crop_zoom, 4)
        if spatial_relay_cut:
            d["spatial_relay_cut"] = True
        if arrow_3d_mode:
            d["arrow_3d_mode"] = arrow_3d_mode
        if flight_speed_ramp is not None:
            d["flight_speed_ramp"] = flight_speed_ramp
        if src_start_sec is not None:
            d["src_start_sec"] = round(float(src_start_sec), 4)
        if src_end_sec is not None:
            d["src_end_sec"] = round(float(src_end_sec), 4)
        return d

    def _brain_clip(
        c_no: int,
        s_idx: int,
        act: int,
        scene_id: str,
        *,
        camera_move: str,
        material_mode: str,
        neural_state: str,
        callout_mode: str,
        start_region: str,
        end_region: str,
        regions: list[str],
        dimmed_regions: list[str],
        prompt: str,
        ref_filename: str,
        r78m_callout: dict[str, Any],
        side_by_side_brain_compare: bool = False,
    ) -> dict[str, Any]:
        return {
            "id": c_no,
            "clip_number": c_no,
            "sentence_index": s_idx,
            "end_sentence_index": s_idx,
            "beat_index": 1,
            "act": act,
            "scene_id": scene_id,
            "grammar": "brain_simulator_3d",
            "visual_grammar": "brain_simulator_3d",
            "render_engine": "google_flow",
            "brain_clip": True,
            "is_3d_flight": True,
            "cameo_easter_egg": False,
            "location_id": "brain_studio",
            "camera": camera_move,
            "camera_move": camera_move,
            "callout_mode": callout_mode,
            "neural_state": neural_state,
            "start_neural_state": neural_state,
            "brain_region": start_region,
            "start_brain_region": start_region,
            "end_brain_region": end_region,
            "regions": regions,
            "dimmed_regions": dimmed_regions,
            "scene": prompt,
            "action": prompt,
            "r78m_flow_prompt": prompt,
            "style_profile": "expressive_25d_v8",
            "schema_version": 8,
            "transition_to_next": "hard",
            "transition_out": "hard",
            "target_duration_sec": 5.4,
            "duration_sec": 5.4,
            "flow_input_mode": "VIDEO_FRAMES",
            "single_start_frame_lock": True,
            "src_start_sec": 0.28,
            "material_mode": material_mode,
            "r78m_material_mode": material_mode,
            "reference_image": f"03_visuals/reference_images/{ref_filename}",
            "start_frame_image": f"03_visuals/reference_images/{ref_filename}",
            "callout_enabled": True,
            "anatomy_label": True,
            "callout_style": "r78m_dual",
            "r78m_callout": r78m_callout,
            "side_by_side_brain_compare": side_by_side_brain_compare,
        }

    clips = [
        # S01 (2-cut crisp Cold-Open Hook: 2.2s + 2.7s)
        _human_clip(
            1, 1, 1, "S01A",
            beat_index=1, beat_weight=0.49,
            grammar="expressive_vinyl_world", camera_move="orbital_3d_arc_sweep",
            location_id="london_cab_dashboard",
            environment="bright sunlit glossy black London taxicab driver cockpit with black steering wheel, dashboard phone mount, and open side tray",
            cast="the 2.5D London cabbie man in a dark tweed jacket and flat cap with a smooth earless noseless matte cream-white oval vinyl head (#F5F2EB) and bold 2D charcoal-black ink eyes and eyebrows",
            cast_roles=["protagonist"],
            action="The 2.5D London cabbie man briskly unclips the glowing smartphone mount off the dashboard with one four-fingered cream-white vinyl hand, drops it straight down into the side door tray, and grips the glossy black steering wheel firmly with both hands",
            consequence="bold 2D black ink eyebrows lift in confident focus toward the sunlit street ahead",
            expression_id="curious_head_tilt_perk",
            ref_filename="kf_r82_c01_cab_dash_9x16.png",
            human_action_relay=True,
            crop_zoom=1.0,
            src_start_sec=0.25,
            src_end_sec=3.35,
            full_trajectory_span=True,
            transition_out="action_impact_cut",
        ),
        _human_clip(
            2, 1, 1, "S01B",
            beat_index=2, beat_weight=0.51,
            grammar="expressive_exterior_establishing", camera_move="pan_right",
            location_id="charing_cross_junction_day",
            environment="sunlit smooth Portland-stone London street curve with unmarked plate-free glossy black taxicabs and lush green trees with zero signs and zero license plates",
            cast="the 2.5D London cabbie man in a dark tweed jacket seated inside the open driver window of a plate-free glossy black cab",
            cast_roles=["protagonist"],
            action="Seated inside the open side window of a sleek unmarked glossy black London cab with a completely smooth blank front bumper, the 2.5D cabbie man reaches one arm out the open side window and points briskly around a sunlit stone street curve",
            consequence="the glossy unmarked black cab turns smoothly around the clean stone corner",
            expression_id="calm_focused_nod",
            ref_filename="kf_r82_c02_charing_cross_9x16.png",
            real_world_target_id=None,
            human_action_relay=True,
            transition_out="seamless_relay_cut",
        ),
        # S02 (2-cut UCL University Aerial Drone -> 3T MRI Bore Breach: 2.5s + 2.5s)
        _human_clip(
            3, 2, 1, "S02A",
            beat_index=1, beat_weight=0.50,
            grammar="expressive_exterior_establishing", camera_move="drone_aerial_approach",
            location_id="ucl_wilkins_aerial_quad",
            environment="high-altitude sunlit aerial view over the classical Portland-stone Corinthian portico dome and Main Quad courtyard of University College London",
            cast="miniature 2.5D researchers in white lab coats striding across the sunlit gravel courtyard below",
            cast_roles=["researcher"],
            action="Sweeping high-altitude 3D aerial approach glides downward over sunlit London rooftops straight toward the grand classical Portland-stone Corinthian portico columns and dome overlooking the University College London courtyard as miniature 2.5D doctors walk briskly up the wide stone steps",
            consequence="the sunlit classical stone colonnade and dome fill the frame with crisp architectural parallax",
            expression_id="calm_focused_nod",
            ref_filename="kf_r82_c03_ucl_aerial_drone_9x16.png",
            real_world_target_id="ucl_wilkins_portico",
            human_action_relay=True,
            r72_cold_open_relay=True,
            full_trajectory_span=True,
            flight_speed_ramp=1.28,
            transition_out="seamless_relay_cut",
        ),
        _human_clip(
            4, 2, 1, "S02B",
            beat_index=2, beat_weight=0.50,
            grammar="architectural_cutaway_portal", camera_move="fpv_window_portal_breach",
            location_id="ucl_mri_scanner_suite",
            environment="classical cream-white Portland-stone University College London facade with fluted Corinthian stone pilasters and tall Georgian sash-window cutaway opening into a bright white 3T brain MRI scanner suite",
            cast="the 2.5D neurologist woman in a white lab coat and the cabbie man on the motorized scanner bed",
            cast_roles=["researcher", "protagonist"],
            action="Gliding smoothly inward past the fluted cream-white Portland-stone columns and tall sash-window cutaway into the bright clinical suite, the 2.5D neurologist woman presses the console button as the padded bed slides the cabbie man smoothly toward the illuminated cylindrical MRI bore",
            consequence="crisp 2D black ink brows focus intently beside the glowing circular scanner ring",
            expression_id="calm_focused_nod",
            ref_filename="kf_r82_c04_ucl_mri_breach_9x16.png",
            real_world_target_id="structural_mri_scanner_bore",
            human_action_relay=True,
            r72_cold_open_relay=True,
            full_trajectory_span=True,
            flight_speed_ramp=1.25,
            src_start_sec=0.25,
            transition_out="action_impact_cut",
        ),
        # S03 (2-cut Rainy Moped Ride -> Giant 6-Mile London Street Map Exam: 2.4s + 2.4s)
        _human_clip(
            5, 3, 1, "S03A",
            beat_index=1, beat_weight=0.49,
            grammar="expressive_exterior_establishing", camera_move="pan_right",
            location_id="charing_cross_rainy_corner",
            environment="wet Portland-stone London street roundabout in light rain with glistening puddles",
            cast="the 2.5D trainee man in a bright yellow rain jacket steering a moving commuter moped",
            cast_roles=["protagonist"],
            action="The 2.5D trainee man in a bright yellow rain jacket steers a rolling commuter moped briskly around a wet London stone corner while glancing down at a clear rainproof street-map board clipped to his handlebars",
            consequence="crisp 2D black ink brows lock into determined focus through light rain",
            expression_id="calm_focused_nod",
            ref_filename="kf_r82_c05_moped_rain_9x16.png",
            real_world_target_id="charing_cross_black_cabs",
            human_action_relay=True,
            transition_out="action_impact_cut",
        ),
        _human_clip(
            6, 3, 1, "S03B",
            beat_index=2, beat_weight=0.51,
            grammar="expressive_vinyl_world", camera_move="gentle_push_in",
            location_id="london_knowledge_map_room",
            environment="bright oak London route-testing room with a giant unfolded radial street map spread across the table",
            cast="the 2.5D trainee man in a yellow jacket and an examiner man in a charcoal suit",
            cast_roles=["protagonist", "researcher"],
            action="The 2.5D trainee man leans low over the giant unfolded radial street map and sweeps a red wooden pointer briskly across dozens of winding street turns while the examiner nods and clicks a brass stopwatch",
            consequence="both figures lean in sharply over the dense radial street network",
            expression_id="curious_head_tilt_perk",
            ref_filename="kf_r82_c06_giant_map_exam_9x16.png",
            human_action_relay=True,
            transition_out="action_impact_cut",
        ),
        # S04 (2-cut Fixed-Brain Dogma -> Illuminated MRI Lightbox Comparison: 2.1s + 2.2s)
        _human_clip(
            7, 4, 2, "S04A",
            beat_index=1, beat_weight=0.49,
            grammar="expressive_vinyl_world", camera_move="gentle_push_in",
            location_id="ucl_neurology_study_desk",
            environment="sunlit oak neurology study desk with a heavy leather-bound volume and rigid white plaster skull model",
            cast="the 2.5D senior neurologist woman in a navy blazer",
            cast_roles=["researcher"],
            action="The 2.5D senior neurologist woman in a navy blazer slams the heavy leather-bound volume shut onto the oak desk with one firm hand and taps the rigid white plaster skull model beside it",
            consequence="crisp 2D black ink eyebrows narrow in skeptical challenge",
            expression_id="squint_suspicion_lean",
            ref_filename="kf_r82_c07_fixed_book_desk_9x16.png",
            real_world_target_id="ucl_wilkins_portico",
            human_action_relay=True,
            transition_out="action_impact_cut",
        ),
        _human_clip(
            8, 4, 2, "S04B",
            beat_index=2, beat_weight=0.51,
            grammar="expressive_vinyl_world", camera_move="gentle_push_in",
            location_id="ucl_mri_scanner_suite",
            environment="bright clinical UCL brain imaging room with a large glowing wall lightbox right above a foreground oak worktable",
            cast="the 2.5D senior neurologist woman in a navy blazer and a 2.5D colleague researcher in a white lab coat standing close in the foreground",
            cast_roles=["researcher"],
            action="Standing large in the foreground, both the 2.5D senior neurologist woman in a navy blazer and the white-coated colleague lift two wide glowing brain scan film sheets with both hands, stride forward briskly, and snap them side by side onto the bright wall lightbox while sweeping their arms across both scans",
            consequence="both researchers lean in dynamically with crisp 2D black ink eyes widened in discovery",
            expression_id="double_blink_shock",
            ref_filename="kf_r82_c08_mri_lightbox_9x16.png",
            real_world_target_id="structural_mri_scanner_bore",
            human_action_relay=True,
            transition_out="action_impact_cut",
        ),
        # S05..S08 (4 Poised Anti-Spin 3D Brain Cuts: ~4.9s - 5.3s each)
        _brain_clip(
            9, 5, 2, "S05",
            camera_move="sensory_to_brain_drone",
            material_mode="xray_glass",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="eyes",
            end_region="primary visual cortex",
            regions=["eyes", "thalamus", "primary visual cortex"],
            dimmed_regions=[],
            prompt="Poised steady 3D sagittal-oblique glide under 12 degrees of gentle single-plane micro-parallax with locked cranial orientation showing warm golden-amber street-view pulses entering the two translucent optical-glass eyeballs on the left and traveling smoothly along the optic tract to illuminate the rear occipital primary visual cortex in electric ice-cyan inside clean dark studio space",
            ref_filename="ref_r82_cut09_eyes_to_v1.png",
            r78m_callout={
                "left_lbl": "Eyes",
                "right_lbl": "Vision Center",
                "arrow": "fwd",
                "sub": "Street Views Hit Rear Cortex",
                "left_rgb": [246, 196, 95],
                "right_rgb": [72, 224, 255],
                "left_xy": [345, 1185],
                "right_xy": [845, 1075],
                "lock_seed_xy": True,
            },
        ),
        _brain_clip(
            10, 6, 2, "S06",
            camera_move="circuit_cooperation_drone",
            material_mode="cool_matte_silver_31",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="primary visual cortex",
            end_region="hippocampus",
            regions=["primary visual cortex", "hippocampus"],
            dimmed_regions=[],
            prompt="Poised steady macro 3D medial push-in under 12 degrees of gentle single-plane micro-parallax with locked orientation across the sculpted cool matte silver-gray cerebral cortex laced with electric cyan sulcal channels as sky-cyan visual streams converge forward along golden fiber tracts into the curved C-shaped medial temporal hippocampus glowing warm amber-gold inside clean dark studio space",
            ref_filename="ref_r82_cut10_v1_to_hippocampus.png",
            r78m_callout={
                "left_lbl": "Hippocampus",
                "right_lbl": "Vision Stream",
                "arrow": "rev",
                "sub": "Weaves Live 3D Street Map",
                "left_rgb": [246, 196, 95],
                "right_rgb": [72, 224, 255],
                "left_xy": [595, 1315],
                "right_xy": [865, 1085],
                "lock_seed_xy": True,
            },
        ),
        _brain_clip(
            11, 7, 3, "S07",
            camera_move="circuit_cooperation_drone",
            material_mode="cool_matte_silver_31",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="hippocampus",
            end_region="temporal lobe",
            regions=["hippocampus", "temporal lobe"],
            dimmed_regions=[],
            prompt="Poised steady front-coronal 3D cutaway push-in under 10 degrees of gentle single-plane micro-parallax with locked symmetry across the cool matte silver-gray 3D brain as both left and right posterior curved hippocampi swell visibly with dense luminous coral-crimson and electric-cyan gray-matter volume inside clean dark studio space",
            ref_filename="ref_r82_cut11_bilateral_posterior_up.png",
            r78m_callout={
                "left_lbl": "Left Rear Hub",
                "right_lbl": "Right Rear Hub",
                "arrow": "vs",
                "sub": "Posterior Gray Matter Expanded",
                "left_rgb": [255, 86, 104],
                "right_rgb": [72, 224, 255],
                "left_xy": [185, 1315],
                "right_xy": [815, 1315],
                "lock_seed_xy": True,
            },
        ),
        _brain_clip(
            12, 8, 3, "S08",
            camera_move="global_system_orbit_drone",
            material_mode="xray_glass",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="hippocampus",
            end_region="parietal cortex",
            regions=["hippocampus", "parietal cortex"],
            dimmed_regions=[],
            prompt="Poised steady 3D three-quarter lateral push-in under 12 degrees of gentle single-plane micro-parallax across the translucent frosted X-ray optical-glass 3D brain showing the posterior hippocampal tail glowing progressively fuller and brighter in warm amber-gold and coral-crimson along its rear arc inside clean dark studio space",
            ref_filename="ref_r82_cut12_years_driven_growth.png",
            r78m_callout={
                "left_lbl": "Years Driving",
                "right_lbl": "Rear Map Volume",
                "arrow": "fwd",
                "sub": "Grows Larger With Experience",
                "left_rgb": [72, 224, 255],
                "right_rgb": [246, 196, 95],
                "left_xy": [315, 1105],
                "right_xy": [675, 1185],
                "lock_seed_xy": True,
            },
        ),
        # S09..S10 (4-cut Rule R80 @RicksClips3000 3D Volumetric Arrow Spatial Relay: ~2.3s - 2.6s each)
        _human_clip(
            13, 9, 4, "S09A",
            beat_index=1, beat_weight=0.49,
            grammar="spatial_3d_arrow_diorama", camera_move="drone_landmark_ascend",
            location_id="london_eye_south_bank",
            environment="sunlit London South Bank and River Thames embankment beside the giant white cantilevered London Eye wheel",
            cast="miniature glossy black London taxicab along the riverside embankment",
            cast_roles=[],
            action="Sweeping 3D aerial arc skims close past the sunlit white London Eye wheel and Portland-stone Thames embankment as a glossy black London cab rolls briskly below, banking steeply skyward above sunlit rooftops",
            consequence="sunlit Portland-stone street canyons open wide below with strong foreground parallax",
            ref_filename="kf_r80_c09_london_eye_9x16.png",
            real_world_target_id="london_eye_thames_wheel",
            spatial_relay_cut=True,
            arrow_3d_mode="adaptive_landmark_zigzag",
            flight_speed_ramp=1.34,
            full_trajectory_span=True,
            transition_out="whip_pan_blur_8f",
        ),
        _human_clip(
            14, 9, 4, "S09B",
            beat_index=2, beat_weight=0.51,
            grammar="spatial_3d_arrow_diorama", camera_move="topdown_3d_route_glide",
            location_id="london_topdown_zigzag_grid",
            environment="vertical 90-degree top-down miniature London Portland-stone street maze with raised matte-crimson 3D zigzag arrows",
            cast="miniature glossy black London taxicab weaving through side streets",
            cast_roles=[],
            action="Tiny glossy black London cab weaves sharply left and right through tangled side-street turns following thick solid matte-crimson 3D extruded zigzag directional arrows resting on the sunlit asphalt with crisp dark drop shadows",
            consequence="raised 3D crimson arrow blocks connect white circular intersection beacons across the winding street grid",
            ref_filename="kf_r80_c10_taxi_zigzag_topdown_9x16.png",
            real_world_target_id="charing_cross_black_cabs",
            spatial_relay_cut=True,
            arrow_3d_mode="adaptive_landmark_zigzag",
            flight_speed_ramp=1.32,
            full_trajectory_span=True,
            transition_out="whip_pan_blur_8f",
        ),
        _human_clip(
            15, 10, 4, "S10A",
            beat_index=1, beat_weight=0.47,
            grammar="spatial_3d_arrow_diorama", camera_move="drone_landmark_ascend",
            location_id="london_red_bus_stop_curb",
            environment="sunlit London Portland-stone avenue curb with iconic circular red bus stop post, glass shelter, and red double-decker bus",
            cast="miniature bright red London double-decker bus pulling away from the curb",
            cast_roles=[],
            action="Sweeping 3D aerial arc skims past the circular red London bus stop flag post and glass shelter as a bright red double-decker bus pulls straight out along the sunlit lane, soaring steeply skyward above Portland-stone rooftops",
            consequence="the straight central London avenue stretches cleanly ahead under crisp afternoon daylight",
            ref_filename="kf_r80_c11_bus_stop_9x16.png",
            real_world_target_id="london_red_bus_stop_roundel",
            spatial_relay_cut=True,
            arrow_3d_mode="fixed_linear_corridor",
            flight_speed_ramp=1.34,
            full_trajectory_span=True,
            transition_out="seamless_relay_cut",
        ),
        _human_clip(
            16, 10, 4, "S10B",
            beat_index=2, beat_weight=0.53,
            grammar="spatial_3d_arrow_diorama", camera_move="topdown_3d_route_glide",
            location_id="london_topdown_straight_avenue",
            environment="full-bleed vertical 9:16 90-degree top-down sunlit London avenue flanked by smooth unadorned warm cream Portland-stone architectural blocks",
            cast="miniature bright red London double-decker bus driving straight ahead",
            cast_roles=[],
            action="Full-bleed vertical 9:16 90-degree overhead top-down view looking straight down at a smooth unmarked gray asphalt avenue flanked by clean solid warm cream Portland-stone architectural blocks as one miniature bright red London double-decker bus drives straight ahead along one giant unbroken solid matte-crimson 3D extruded directional arrow block casting a crisp dark drop shadow",
            consequence="the straight 3D crimson arrow corridor stretches cleanly from bottom to top edge between smooth cream stone blocks",
            ref_filename="kf_r82_c16_bus_straight_clean_9x16.png",
            real_world_target_id=None,
            spatial_relay_cut=True,
            arrow_3d_mode="fixed_linear_corridor",
            flight_speed_ramp=1.28,
            full_trajectory_span=True,
            transition_out="action_impact_cut",
        ),
        # S11..S12 (HERO Side-by-Side Taxi vs Bus 3D Hippocampus Size Comparison + Active Detour Circuit: ~5.5s each)
        _brain_clip(
            17, 11, 4, "S11",
            camera_move="circuit_cooperation_drone",
            material_mode="cool_matte_silver_31",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="hippocampus",
            end_region="temporal lobe",
            regions=["hippocampus", "temporal lobe"],
            dimmed_regions=[],
            prompt="Poised wide front-coronal 3D side-by-side brain comparison under 6 degrees of subtle micro-parallax keeping both entire whole brains completely inside the frame margins with dark studio space on left and right edges, where the complete left taxi-driver translucent silver-gray brain displays an unmistakably enlarged plump curved posterior hippocampus glowing bright coral-crimson and warm gold deep inside its medial temporal lobes while the complete right bus-driver translucent silver-gray brain displays a small thin flat dormant posterior hippocampus in muted slate-gray",
            ref_filename="ref_r82_cut17_taxi_vs_bus_brain.png",
            side_by_side_brain_compare=True,
            r78m_callout={
                "left_lbl": "Taxi Hippocampus",
                "right_lbl": "Bus Hippocampus",
                "arrow": "vs",
                "sub": "Giant Rear Map  vs  Flat Baseline",
                "left_rgb": [255, 86, 104],
                "right_rgb": [175, 198, 230],
                "left_xy": [200, 1045],
                "right_xy": [812, 1040],
                "lock_seed_xy": True,
            },
        ),
        _brain_clip(
            18, 12, 5, "S12",
            camera_move="circuit_cooperation_drone",
            material_mode="cool_matte_silver_31",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="parietal cortex",
            end_region="hippocampus",
            regions=["parietal cortex", "prefrontal cortex", "hippocampus"],
            dimmed_regions=[],
            prompt="Poised steady 3D mid-sagittal push-in under 8 degrees of gentle single-plane micro-parallax with strictly locked lateral mid-sagittal profile orientation from start to finish and zero view-plane rotation across the sculpted cool matte silver-gray cerebral cortex laced with electric cyan micro-vessels as bright sky-cyan posterior parietal spatial pathways and golden-amber detour streams converge downward into the curved C-shaped medial temporal hippocampus inside clean dark studio space",
            ref_filename="ref_r82_cut18_detour_wiring.png",
            r78m_callout={
                "left_lbl": "Hippocampus",
                "right_lbl": "Sense of Place",
                "arrow": "rev",
                "sub": "Live Detours Wire & Grow Map",
                "left_rgb": [246, 196, 95],
                "right_rgb": [72, 224, 255],
                "left_xy": [515, 1325],
                "right_xy": [765, 835],
                "lock_seed_xy": True,
            },
        ),
        # S13 (4-Year Longitudinal 39/79 Trainees MRI Cohort + Data Stamp #1: ~3.9s)
        _human_clip(
            19, 13, 5, "S13",
            grammar="expressive_exterior_establishing", camera_move="gentle_push_in",
            location_id="ucl_portico_steps",
            environment="sunlit outdoor Portland-stone steps of the University College London portico",
            cast="the 2.5D newly qualified cabbie man in a tweed jacket with a green lapel badge and the researcher woman in a white lab coat",
            cast_roles=["protagonist", "researcher"],
            action="Framed in the lower half of the sunlit stone steps, the 2.5D researcher woman in a white lab coat hands a gleaming green cabbie badge to the cabbie man in a tweed jacket who pins it onto his lapel and pumps a brisk celebratory fist",
            consequence="both figures nod warmly with crisp 2D black ink smiles below clean sunlit upper-frame stone columns",
            expression_id="calm_focused_nod",
            ref_filename="kf_r82_c19_trainees_qualified_9x16.png",
            real_world_target_id="ucl_wilkins_portico",
            transition_out="action_impact_cut",
        ),
        # S14..S15 (Posterior Expansion vs Anterior Shrinkage Trade-Off Inside 1 Skull: ~4.8s + ~5.2s)
        _brain_clip(
            20, 14, 6, "S14",
            camera_move="global_system_orbit_drone",
            material_mode="xray_glass",
            neural_state="active",
            callout_mode="pathway_relay",
            start_region="hippocampus",
            end_region="temporal lobe",
            regions=["hippocampus", "temporal lobe"],
            dimmed_regions=[],
            prompt="Poised steady 3D lateral X-ray optical-glass head push-in under 10 degrees of gentle single-plane micro-parallax revealing the curved hippocampus inside one fixed translucent glass cranium with its rear posterior tail glowing bright golden-amber and electric-cyan behind its cooler slate-gray anterior front zone inside clean dark studio space",
            ref_filename="ref_r82_cut20_fixed_skull_budget.png",
            r78m_callout={
                "left_lbl": "Front Zone",
                "right_lbl": "Giant Rear Map",
                "arrow": "vs",
                "sub": "Inside One Fixed Skull",
                "left_rgb": [175, 198, 230],
                "right_rgb": [246, 196, 95],
                "left_xy": [520, 1165],
                "right_xy": [660, 1055],
                "lock_seed_xy": True,
            },
        ),
        _brain_clip(
            21, 15, 6, "S15",
            camera_move="3p_region_shutdown_pullout",
            material_mode="cool_matte_silver_31",
            neural_state="rerouted",
            callout_mode="pathway_relay",
            start_region="hippocampus",
            end_region="temporal lobe",
            regions=["hippocampus", "temporal lobe"],
            dimmed_regions=[],
            prompt="Poised steady 3D macro sagittal pull-back under 10 degrees of gentle single-plane micro-parallax across the cool matte silver-gray cerebral cortex folds showing the expanded posterior hippocampus blazing with coral-crimson and electric-cyan volume on the left while the anterior hippocampal front tip visibly contracts into darkened muted slate-gray on the right inside clean dark studio space",
            ref_filename="ref_r82_cut21_posterior_vs_anterior.png",
            r78m_callout={
                "left_lbl": "Rear Expanded",
                "right_lbl": "Front Shrank",
                "arrow": "vs",
                "sub": "Plasticity Space Trade-Off",
                "left_rgb": [255, 86, 104],
                "right_rgb": [175, 198, 230],
                "left_xy": [295, 1140],
                "right_xy": [735, 885],
                "lock_seed_xy": True,
            },
        ),
        # S16..S17 (Real Maguire 2006 Rey-Osterrieth Complex Figure Visual Recall Test + Data Stamp #2 21.3 vs 17.3: ~3.4s + ~4.0s)
        _human_clip(
            22, 16, 6, "S16",
            grammar="expressive_vinyl_world", camera_move="gentle_push_in",
            location_id="ucl_rey_figure_test_desk",
            environment="bright sunlit UCL neuropsychology testing table with a black-ink geometric blueprint figure card and two white sketchpads",
            cast="the 2.5D London bus driver man in a navy uniform vest and the cabbie man in a tweed jacket seated side by side",
            cast_roles=["protagonist"],
            action="The 2.5D researcher places a crisp geometric line-drawing card onto the oak desk and lifts it away after a beat as both the bus driver man in a navy vest and the cabbie man pick up pencils over blank white sketchpads",
            consequence="crisp 2D black ink eyes lean forward intensely to recall the brand-new geometric lines",
            expression_id="curious_head_tilt_perk",
            ref_filename="kf_r82_c22_rey_figure_card_9x16.png",
            transition_out="action_impact_cut",
        ),
        _human_clip(
            23, 17, 6, "S17",
            grammar="expressive_vinyl_world", camera_move="gentle_push_in",
            location_id="ucl_rey_figure_test_desk",
            environment="sunlit carved-oak UCL room with mullioned sash windows and walnut desk",
            cast="the 2.5D bus driver man in a navy vest and cabbie man in a tweed jacket",
            cast_roles=["protagonist"],
            action="At the lower walnut desk, the 2.5D bus driver man draws the final sharp black-ink geometric line and holds up his completed pad with both hands while the cabbie man blinks and taps his cap",
            consequence="the bus driver smiles with crisp 2D ink pride beside the cabbie's wry blink",
            expression_id="deadpan_blink_pause",
            ref_filename="kf_r82_c23_rey_recall_result_9x16.png",
            transition_out="hard",
        ),
    ]
    assert len(clips) == 23

    reference_anchors: list[dict[str, Any]] = []
    for c in clips:
        c_no = int(c["clip_number"])
        fn = Path(str(c["reference_image"])).name
        ref_id = Path(fn).stem
        is_b = bool(c.get("brain_clip"))
        is_sp = bool(c.get("spatial_relay_cut"))
        if is_b and bool(c.get("side_by_side_brain_compare")):
            anc_prompt = (
                "Wide zoomed-out vertical 9:16 clinical 3D neuroanatomy comparison render inside clean dark #05080F studio space "
                "with wide empty dark margins on the far left edge, far right edge, top third, and bottom quarter (both whole brains "
                "completely visible from left temporal pole to right temporal pole with zero cropping at any border, zero text, zero labels, zero letters): "
                "two small matched complete translucent cool matte silver-gray 3D human coronal brains floating side by side near center height, "
                "the complete LEFT BRAIN displaying a massively enlarged plump curved posterior hippocampus glowing brightly in coral-crimson and warm gold deep inside its medial temporal lobes, "
                "and the complete RIGHT BRAIN displaying a small thin flat dormant posterior hippocampus in cool muted slate-gray with zero crimson glow."
            )
        elif is_b:
            anc_prompt = (
                f"Vertical 9:16 clinical 3D neuroanatomy render inside clean dark #05080F studio space with generous empty upper-third "
                f"negative space and zero text, zero labels, zero letters: {c['scene']}"
            )
        elif is_sp and c_no == 16:
            anc_prompt = (
                "Full-bleed vertical 9:16 90-degree overhead architectural miniature diorama photograph looking straight down at a wide "
                "smooth unmarked charcoal-gray asphalt London boulevard flanked on left and right by clean minimalist solid warm cream "
                "Portland-stone rooftop slabs (smooth flat stone surfaces with zero windows, zero greenery, zero text, zero road lines): "
                "centered down the middle of the asphalt rests one giant solid matte-crimson (#FF2525) 3D extruded straight directional arrow "
                "casting a crisp dark sunlight drop shadow, with one miniature bright red London double-decker bus driving straight forward "
                "along the raised crimson arrow."
            )
        elif is_sp:
            anc_prompt = str(c["action"])
        elif c_no == 1:
            anc_prompt = (
                "Vertical 9:16 stylized 3D miniature diorama keyframe inside a bright sunlit glossy black London taxicab driver cockpit "
                "from a medium three-quarter front-side angle: the clothed 2.5D London cabbie man in a dark herringbone tweed jacket and "
                "flat cap with a smooth earless hairless noseless matte cream-white oval vinyl head (#F5F2EB) and bold 2D charcoal-black "
                "cartoon ink eyebrows and eyes reaches one four-fingered cream-white vinyl hand to unclip a glowing blank-map smartphone "
                "mount off the black dashboard above the steering wheel, zero text, zero letters, zero numbers."
            )
        elif c_no == 4:
            anc_prompt = (
                "Full-bleed vertical 9:16 stylized 3D architectural miniature diorama cutaway keyframe of University College London's "
                "classical cream-white Portland-stone facade (smooth pale cream stone blocks, fluted Corinthian stone pilasters, and tall "
                "white-framed Georgian sash window cutaway — strictly cream-white Portland stone matching the portico, zero red brick): "
                "through the open classical stone window cutaway sits a bright white clinical 3T structural MRI scanner suite where the "
                "2.5D female neurologist in a white lab coat stands at the control button beside the 2.5D cabbie man lying on the padded "
                "motorized bed before the illuminated circular MRI bore. Smooth matte cream-white oval vinyl heads (#F5F2EB) with bold 2D "
                "charcoal-black ink eyes and eyebrows, zero text, zero signage, zero letters."
            )
        elif c_no == 2:
            anc_prompt = (
                "Full-bleed vertical 9:16 exterior street-level 3D miniature diorama keyframe from outside on a sunlit smooth Portland-stone "
                "London street curve surrounded by green park trees: one sleek unmarked glossy black London taxicab with a completely smooth "
                "blank black front bumper (strictly zero license plate, zero grille badge, zero street signs, zero text) rolls around the clean "
                "stone curve as the 2.5D cabbie man in a dark tweed jacket and flat cap reaches one arm out the open side window to point ahead."
            )
        elif c_no == 23:
            anc_prompt = (
                "Vertical 9:16 stylized 3D miniature diorama keyframe inside a richly textured sunlit UCL wood-paneled testing room "
                "whose entire upper wall features carved geometric oak wainscoting panels, tall dark-framed mullioned sash window grids, "
                "and architectural crown molding; seated side by side in the lower half at a dark walnut table, the 2.5D bus driver man "
                "in a navy uniform vest holds up a crisp black-ink geometric line-drawing pad while the 2.5D cabbie man in a tweed jacket "
                "and flat cap looks at his half-finished pad. Smooth matte cream-white vinyl heads (#F5F2EB) with bold 2D charcoal-black "
                "ink eyes and eyebrows, zero text, zero signage, zero letters."
            )
        else:
            anc_prompt = (
                f"Vertical 9:16 stylized 3D miniature diorama keyframe in {c['environment']}, featuring {c['cast']}. "
                f"Pre-action starting pose for: {c['action']}. Smooth matte cream-white vinyl heads (#F5F2EB) with bold 2D charcoal-black "
                f"ink eyes and eyebrows, crisp 3D woven clothing, zero text, zero signage, zero letters."
            )
        reference_anchors.append(
            {
                "ref_id": ref_id,
                "clip_number": c_no,
                "frame": "start",
                "category": "brain_anchor" if is_b else "clip_keyframe_anchor",
                "role": "brain_start" if is_b else "clip_start_keyframe",
                "scene_id": c["scene_id"],
                "setting": "brain_studio" if is_b else "real_env",
                "location_id": c["location_id"],
                "filename": fn,
                "title": f"Clip {c_no:02d} start anchor",
                "generation_order": 2,
                "conditioned_on": (
                    []
                    if (is_sp or bool(c.get("side_by_side_brain_compare")))
                    else (["xray_brain75_master"] if is_b else ["species_opt1_sheet"])
                ),
                "style_profile": "expressive_25d_v8",
                "prompt": anc_prompt,
                "real_world_target_id": c.get("real_world_target_id"),
                "custom_brain_anchor": is_b,
                "side_by_side_brain_compare": bool(c.get("side_by_side_brain_compare")),
            }
        )

    old_vp = json.loads((old_dir / "02_script" / "visual_plan.json").read_text(encoding="utf-8"))
    visual_plan = {
        "schema": 8,
        "schema_version": 8,
        "dossier_schema_version": 2,
        "project_id": PROJECT_ID,
        "profile": "neuro_diorama",
        "production_profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "shorts_format_profile": "shorts_expressive_v8",
        "topic_focus": "neuroscience",
        "r72_mode": True,
        "r72_cold_open_relay": True,
        "r72_bridge_clips": [3, 4],
        "r73_mode": True,
        "r74_mode": False,
        "r74b_mode": False,
        "r76_mode": True,
        "r76_brain_simulator": True,
        "r77n_conversational_storytelling": True,
        "r78v_5tone_siren": True,
        "r79m_character_motion": True,
        "r80_mode": True,
        "r82_mode": True,
        "zero_clip_reuse": True,
        "real_world_targets": real_world_targets,
        "voice_preset": "el_siren_v4",
        "opening_mode": "myth_flip_claim",
        "ending_mode": "mic_drop",
        "core_reveal_sentence_index": 12,
        "pillar": "brain_health",
        "everyday_domain": "memory",
        "dossier": "maguire_london_taxi_hippocampus",
        "dossier_slug": "maguire_london_taxi_hippocampus",
        "title": "Why London Taxi Drivers Grew Bigger Brains",
        "doi": "10.1073/pnas.070039597",
        "secondary_doi": "10.1002/hipo.20233",
        "mechanism_doi": "10.1016/j.cub.2011.11.018",
        "data_stamps": data_stamps,
        "thumbnail": old_vp["thumbnail"],
        "clips": clips,
        "reference_anchors": reference_anchors,
    }

    metadata = {
        "project_id": PROJECT_ID,
        "pillar": "brain_health",
        "everyday_domain": "memory",
        "title": "Why London Taxi Drivers Grew Bigger Brains",
        "title_char_count": len("Why London Taxi Drivers Grew Bigger Brains"),
        "doi": "10.1073/pnas.070039597",
        "secondary_doi": "10.1002/hipo.20233",
        "mechanism_doi": "10.1016/j.cub.2011.11.018",
        "doi_url": "https://doi.org/10.1073/pnas.070039597",
        "tags": [
            "shorts",
            "london taxi study",
            "the knowledge london",
            "hippocampus",
            "spatial memory",
            "neuroplasticity",
            "neuroscience",
            "psychology",
            "brain health",
            "human memory",
            "cognitive science",
        ],
        "hashtags": ["#shorts"],
        "playlists": [],
        "category": "Education",
        "language": "en-US",
        "profile": "neuro_diorama",
        "style_profile": "expressive_25d_v8",
        "shorts_format_profile": "shorts_expressive_v8",
        "ai_disclosure": True,
        "ai_content_declaration": True,
        "description": f"{viewer_description}\n\n#shorts",
        "pinned_comment": script_doc["debate_question"],
    }

    now_iso = datetime.now(timezone.utc).isoformat()
    manifest = {
        "project_id": PROJECT_ID,
        "title": metadata["title"],
        "pillar": "brain_health",
        "created_at": now_iso,
        "updated_at": now_iso,
        "stages": {
            st: {"status": "pending", "updated_at": now_iso, "artifacts": {}, "errors": []}
            for st in ("01_ideation", "02_script", "03_visuals", "04_audio", "05_assembly", "06_publish")
        },
    }

    if not (proj_dir / "00_project_manifest.json").is_file():
        _atomic_write_json(proj_dir / "00_project_manifest.json", manifest)
    _atomic_write_json(proj_dir / "02_script" / "script.json", script_doc)
    _atomic_write_json(proj_dir / "02_script" / "visual_plan.json", visual_plan)
    _atomic_write_json(proj_dir / "03_visuals" / "visual_plan.json", visual_plan)
    _atomic_write_json(proj_dir / "06_publish" / "metadata.json", metadata)

    # Copy already-verified R80 4-cut arrow & landmark keyframes + channel master sheets so we only generate the new R82 keyframes!
    ref_dst_dir = proj_dir / "03_visuals" / "reference_images"
    ref_old_dir = old_dir / "03_visuals" / "reference_images"
    reusable_refs = (
        "species_opt1_sheet.png",
        "cameo_opt3_sheet.png",
        "cast_sheet_02_clinical_historical_6roles.png",
        "cast_sheet_03_everyday_lifestyle_6roles.png",
        "expressive_conflict_master.png",
        "xray_brain75_master.png",
        "kf_r80_c09_london_eye_9x16.png",
        "kf_r80_c10_taxi_zigzag_topdown_9x16.png",
        "kf_r80_c11_bus_stop_9x16.png",
    )
    for r_fn in reusable_refs:
        src_p = ref_old_dir / r_fn
        dst_p = ref_dst_dir / r_fn
        if src_p.is_file():
            if not dst_p.is_file() or dst_p.stat().st_size != src_p.stat().st_size:
                shutil.copy2(src_p, dst_p)
            register_reference_image(proj_dir, r_fn, "flow_image_generation")

    # Also copy verified thumbnail PNGs from v8_ep09 so R65 v4 thumbnail gates are pre-staged (we will also re-run `main.py thumbnail`!)
    for th_fn in ("thumbnail.png", "thumbnail_selected.png", "thumbnail_var_A.png", "thumbnail_var_B.png", "thumbnail_var_C.png", "thumbnail_contact_sheet.png", "thumbnail_report.json", "thumbnail_qa_report.json"):
        src_th = old_dir / "06_publish" / th_fn
        dst_th = proj_dir / "06_publish" / th_fn
        if src_th.is_file() and (not dst_th.is_file() or dst_th.stat().st_size != src_th.stat().st_size):
            shutil.copy2(src_th, dst_th)

    built_clips = build_flow_prompts(visual_plan, sentences)
    write_flow_prompts_json(proj_dir / "03_visuals", built_clips)

    ref_specs = build_reference_image_specs(visual_plan, sentences)
    _atomic_write_json(proj_dir / "03_visuals" / "reference_image_specs.json", ref_specs)

    contract = compile_episode_qa_contract(visual_plan, sentences, built_clips, script_doc=script_doc)
    _atomic_write_json(proj_dir / "03_visuals" / "episode_qa_contract.json", contract)

    print(f"Built {PROJECT_ID}: {len(sentences)} sentences, {len(built_clips)} clips, {len(reference_anchors)} anchors.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
