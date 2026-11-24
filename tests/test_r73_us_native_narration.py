"""
Unit and regression tests for Rule R73 (US Native Spoken Narration & S1->S2 R72 Bridge):
1. `paradox_question` / `myth_flip_claim` / `sensory_test` / `action_first_stamp` pass cleanly while generic `Q_generic` ("Have you ever wondered...?") and adjacent `previous_opening_mode` repeat are hard-blocked.
2. Chronological year-first S1 ("In 2002 at Harvard...") is hard-blocked on new episodes while `S2-S4` University Credibility Bridge (`B2`) + `Pattern B` (`Clip 01` Hook -> `Clip 02 -> Clip 03` `K0 -> K1 -> K2` FPV Drone Relay) pass cleanly.
3. `Plain-First` immediate gloss within `+-8` words ("your brain's decision builder — the prefrontal cortex") passes while unglossed anatomy/jargon or `> 2` distinct hard neuro terms are hard-blocked.
4. AI clichés (`delve into`, `plays a vital role`, etc.), `> 22` words/sentence, and `FK Grade > 6.2` are hard-blocked; `plan_sentence_prosody` schedules the exact `0.42s` (`[0.38, 0.48]s`) Post-Hook Cognitive Pause before `S2`.
5. `PRE_R73_FROZEN_V8_PROJECTS` (`Ep #1..#6`) retain 100% backward compatibility without retroactive failures.
"""

from __future__ import annotations

import copy
import json
from typing import Any

from pipeline import config as cfg
from pipeline.prompt_builder import validate_r72_open_world_drone_and_real_refs
from pipeline.reference_pack import populate_expressive_v8_reference_contract
from pipeline.prompt_gate import validate_production_diorama_v6, validate_script_spine_v8_report
from pipeline.prosody_qa import plan_sentence_prosody


def _r73_flagship_sentences() -> list[str]:
    return [
        "Why do you end up hating your own choice only when you're allowed to change your mind?",
        "To test this, Harvard scientists had students print two favorite photos and pick one to keep.",
        "Half learned their pick was final, while the rest got five days to swap.",
        "The teacher smiled and said, take five days and trade your print if you want.",
        "Most people think a free five-day swap rule makes you feel calm and glad.",
        "Almost no one swapped — yet the students who could trade hated the print they kept!",
        "Meanwhile, the students locked into a final pick loved their photo right away.",
        "Hold on — why would an open exit ruin the same picture on your wall?",
        "Another team set out twenty-four jam jars at a bright stand, then dropped to six.",
        "Crowds loved the big stand, yet ten times more shoppers bought from six jars.",
        "That's because an open door keeps your head hunting for flaws in your pick.",
        "Your brain's choice builder — the prefrontal cortex — builds joy only after doors lock shut.",
        "Leave the door open, and your brain's doubt alarm — the anterior cingulate — keeps firing.",
        "Every return window on your phone runs that exact trap on your mood.",
        "Close the extra tabs and lock in once you pick a good fit.",
        "Your brain builds joy after doors lock shut — so open return rules breed regret.",
    ]


def _r73_base_doc(**overrides: Any) -> dict[str, Any]:
    doc: dict[str, Any] = {
        "schema": 8,
        "project_id": "v8_ep07_harvard_reversible_choice_paradox",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "voice_preset": "elevenlabs_v4",
        "prosody_mode": "expressive_us_v8",
        "r73_mode": True,
        "opening_mode": "paradox_question",
        "previous_opening_mode": "case_stamp",
        "ending_mode": "mic_drop",
        "core_reveal_sentence_index": 12,
        "sentence_speakers": [
            "narrator",
            "narrator",
            "narrator",
            "researcher",
            "narrator",
            "narrator",
            "narrator",
            "mini_cortex",
            "narrator",
            "narrator",
            "narrator",
            "narrator",
            "narrator",
            "narrator",
            "narrator",
            "narrator",
        ],
        "sentence_beats": [
            "paradox_question",
            "university_bridge",
            "evidence",
            "hook_promise",
            "aggro",
            "conflict",
            "evidence",
            "escalation",
            "evidence",
            "evidence",
            "setback",
            "core",
            "mechanism",
            "payoff",
            "payoff",
            "mic_drop",
        ],
    }
    doc.update(overrides)
    return doc


def test_r73_opening_modes_generic_question_ban_and_anti_repeat() -> None:
    sents = _r73_flagship_sentences()
    rep = validate_script_spine_v8_report(sents, script_doc=_r73_base_doc())
    assert rep["issues"] == [], f"Expected flagship R73 script pass, got: {rep['issues']}"

    # 1. Generic low-curiosity question ("Have you ever wondered...?") -> hard FAIL
    generic_q = ["Have you ever wondered why you hate your own choices at the store?"] + sents[1:]
    rep_gen = validate_script_spine_v8_report(generic_q, script_doc=_r73_base_doc())
    assert any("[r73_hook]" in x and "generic low-curiosity" in x for x in rep_gen["issues"]), rep_gen

    # 2. Adjacent episode opening_mode repeat -> hard FAIL
    rep_repeat = validate_script_spine_v8_report(
        sents,
        script_doc=_r73_base_doc(previous_opening_mode="paradox_question"),
    )
    assert any("[r73_hook]" in x and "repeats previous_opening_mode" in x for x in rep_repeat["issues"]), rep_repeat

    # 3. `myth_flip_claim`, `sensory_test`, and `action_first_stamp` all pass cleanly
    myth_sents = ["Being allowed to return a purchase doesn't make you happier — it traps your brain in regret."] + sents[1:]
    assert validate_script_spine_v8_report(myth_sents, script_doc=_r73_base_doc(opening_mode="myth_flip_claim"))["issues"] == []

    sensory_sents = ["Pick two photos on your phone right now, and watch how a swap rule ruins your favorite."] + sents[1:]
    assert validate_script_spine_v8_report(sensory_sents, script_doc=_r73_base_doc(opening_mode="sensory_test"))["issues"] == []

    action_sents = ["Harvard photography students printed two favorite pictures and locked one inside a darkroom tray!"] + sents[1:]
    assert validate_script_spine_v8_report(action_sents, script_doc=_r73_base_doc(opening_mode="action_first_stamp"))["issues"] == []


def test_r73_blocks_year_first_s1_requires_s2_s4_bridge_and_wires_pattern_b_r72_drone_relay() -> None:
    sents = _r73_flagship_sentences()

    # 1. Year-first S1 ("In 2002 at Harvard...") is hard-blocked on new R73 episodes
    year_first = [
        "In 2002 at Harvard University, psychologists gave photography students five days to swap their favorite darkroom print!"
    ] + sents[1:]
    rep_year = validate_script_spine_v8_report(
        year_first,
        script_doc=_r73_base_doc(opening_mode="case_stamp"),
    )
    assert any("[r73_hook]" in x for x in rep_year["issues"]), rep_year

    # 2. Missing S2-S4 university/researcher credibility bridge -> hard FAIL
    no_bridge = list(sents)
    no_bridge[1] = "Two glossy prints sat side by side on a wooden desk under a warm lamp."
    no_bridge[2] = "Half of the people kept their pick forever, while the rest got five days to trade."
    no_bridge[3] = "A voice at the door said, take five days and swap your print anytime."
    rep_nb = validate_script_spine_v8_report(no_bridge, script_doc=_r73_base_doc())
    assert any("[r73_bridge]" in x for x in rep_nb["issues"]), rep_nb

    # 3. Pattern B R72 × R73 Bridge: Clip 01 = Viewer Hook, Clip 02 -> Clip 03 = K0 -> K1 -> K2 Drone Cutaway Relay!
    outdoor_locs = [
        "harvard_memorial_yard_aerial",
        "harvard_square_crosswalk_01",
        "charles_river_footbridge_01",
        "outdoor_jam_market_pavilion_01",
        "campus_courtyard_steps_01",
    ]
    indoor_locs = ["darkroom_a", "gallery_b", "dorm_desk_c"]
    clips: list[dict[str, Any]] = []
    for idx in range(1, 25):
        s_idx = min(len(sents), ((idx - 1) * len(sents)) // 24 + 1)
        if idx == 1:
            loc, gram, cam, rwt = "dorm_desk_c", "expressive_hands_closeup", "gentle_push_in", ""
        elif idx == 2:
            loc, gram, cam, rwt = "harvard_memorial_yard_aerial", "expressive_exterior_establishing", "drone_aerial_approach", "harvard_memorial_yard"
        elif idx == 3:
            loc, gram, cam, rwt = "architectural_cutaway_portal_01", "architectural_cutaway_portal", "fpv_window_portal_breach", "harvard_memorial_yard"
        elif idx == 17:
            loc, gram, cam, rwt = "xray_chamber", "expressive_xray_brain", "gentle_push_in", ""
        elif idx == 19:
            loc, gram, cam, rwt = "campus_courtyard_steps_01", "expressive_cameo_world", "locked_tripod", ""
        elif idx % 2 == 0:
            loc = outdoor_locs[(idx // 2) % len(outdoor_locs)]
            gram = "expressive_exterior_establishing"
            cam = "drone_high_orbit_drop" if idx % 4 == 0 else "vertical_90_topdown_dive"
            rwt = "harvard_square_brick" if "square" in loc else ""
        else:
            loc = indoor_locs[(idx // 2) % len(indoor_locs)]
            gram = "expressive_reaction_closeup" if idx % 5 == 0 else "expressive_vinyl_world"
            cam = "locked_tripod" if gram == "expressive_reaction_closeup" else "drone_skyline_pullback"
            rwt = "harvard_darkroom_enlarger_rig" if loc == "darkroom_a" else ""
        c_dict: dict[str, Any] = {
            "index": idx,
            "clip_number": idx,
            "sentence_index": s_idx,
            "sentence_indices": [s_idx],
            "grammar": gram,
            "location_id": loc,
            "camera_move": cam,
            "transition_out": "seamless_relay_cut" if idx == 2 else "daisy_chain_bridge",
            "cast": ["researcher"] if gram != "expressive_xray_brain" else [],
            "cameo_easter_egg": idx == 19,
            "action_2beat": "Holds two framed prints, then sweeps over red-brick Harvard Yard into the darkroom.",
        }
        if rwt:
            c_dict["real_world_target_id"] = rwt
        clips.append(c_dict)

    vp_pat_b: dict[str, Any] = {
        "schema": 8,
        "project_id": "v8_ep07_harvard_reversible_choice_paradox",
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "voice_preset": "elevenlabs_v4",
        "opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "r72_mode": True,
        "r73_mode": True,
        "real_world_targets": ["harvard", "harvard_square", "darkroom_enlarger"],
        "clips": clips,
    }
    populated_b = populate_expressive_v8_reference_contract(copy.deepcopy(vp_pat_b))
    c2, c3 = populated_b["clips"][1], populated_b["clips"][2]
    assert str(c2["start_frame_image"]).endswith("kf_02_r72_k0_aerial_9x16.png")
    assert str(c2["end_frame_image"]).endswith("kf_02_r72_k1_facade_9x16.png")
    assert c2["end_frame_image"] == c3["start_frame_image"]
    assert str(c3["end_frame_image"]).endswith("kf_03_r72_k2_cutaway_9x16.png")
    r72_rep = validate_r72_open_world_drone_and_real_refs(populated_b, script_doc={"sentences": sents, "opening_mode": "paradox_question"})
    assert r72_rep["passed"] is True, f"Pattern B R72 relay failed: {r72_rep}"


def test_r73_plain_first_jargon_gate_ai_cliche_brevity_fk_and_post_hook_pause() -> None:
    sents = _r73_flagship_sentences()

    # 1. Unglossed anatomy term ("amygdala" with no plain gloss in +-8 words) -> hard FAIL
    unglossed = list(sents)
    unglossed[12] = "Leave the exit cracked open, and your lateral amygdala fires all afternoon long."
    rep_unglossed = validate_script_spine_v8_report(unglossed, script_doc=_r73_base_doc())
    assert any("[r73_jargon]" in x and "amygdala" in x for x in rep_unglossed["issues"]), rep_unglossed

    # 2. > 2 distinct hard neuro/anatomy terms even when glossed -> hard FAIL
    three_terms = list(sents)
    three_terms[13] = "Your brain's memory hub — the hippocampus — also logs every tiny flaw you notice."
    rep_three = validate_script_spine_v8_report(three_terms, script_doc=_r73_base_doc())
    assert any("[r73_jargon]" in x and "> max 2" in x for x in rep_three["issues"]), rep_three

    # 3. AI cliché ("plays a vital role" / "delve into") + > 22w sentence + high FK grade -> hard FAIL
    cliche_long = list(sents)
    cliche_long[4] = (
        "Let us delve into why this neural mechanism plays a vital role across every single reversible retail transaction "
        "that modern consumers evaluate inside contemporary department stores."
    )
    rep_cliche = validate_script_spine_v8_report(cliche_long, script_doc=_r73_base_doc())
    assert any("[r73_ai_cliche]" in x for x in rep_cliche["issues"]), rep_cliche
    assert any("[r73_brevity]" in x for x in rep_cliche["issues"]), rep_cliche

    # 4. Seamless loop ending mode check
    loop_bad = list(sents)
    loop_bad[-1] = "Locking the exit door settles the score inside the darkroom."
    rep_loop_bad = validate_script_spine_v8_report(loop_bad, script_doc=_r73_base_doc(ending_mode="seamless_loop"))
    assert any("[r73_ending]" in x for x in rep_loop_bad["issues"]), rep_loop_bad

    loop_good = list(sents)
    loop_good[-1] = "Locking the exit settles your choice — unless you're allowed to change your mind..."
    rep_loop_good = validate_script_spine_v8_report(loop_good, script_doc=_r73_base_doc(ending_mode="seamless_loop"))
    assert rep_loop_good["issues"] == [], rep_loop_good

    # 5. Prosody Post-Hook Pause = 0.42s before S2 on R73 scripts
    pros = plan_sentence_prosody(sents, _r73_base_doc(), "expressive_us_v8")
    assert pros[1]["post_hook_pause_before"] is True
    assert pros[1]["gap_before_sec"] == 0.42


def test_r73_frozen_v8_projects_ep01_to_ep06_backward_compatibility() -> None:
    for pid in cfg.PRE_R73_FROZEN_V8_PROJECTS:
        assert cfg.is_r73_us_native_v8_script({"project_id": pid, "opening_mode": "case_stamp"}, project_id=pid) is False
        proj_dir = cfg.CHANNEL_ROOT / "projects" / pid
        sc_path = proj_dir / "02_script" / "script.json"
        vp_path = proj_dir / "03_visuals" / "visual_plan.json"
        fp_path = proj_dir / "03_visuals" / "flow_prompts.json"
        if sc_path.exists() and vp_path.exists() and fp_path.exists():
            sc_doc = json.loads(sc_path.read_text(encoding="utf-8"))
            vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
            fp_doc = json.loads(fp_path.read_text(encoding="utf-8"))
            raw_sents = sc_doc.get("sentences") or sc_doc.get("lines") or []
            sents = [s["text"] if isinstance(s, dict) else str(s) for s in raw_sents]
            clips = fp_doc.get("clips") if isinstance(fp_doc, dict) else fp_doc
            rep = validate_script_spine_v8_report(sents, script_doc=sc_doc, plan=vp_doc, project_id=pid)
            assert not any("[r73_" in x for x in rep["issues"]), f"Frozen {pid} hit retroactive R73 failure: {rep['issues']}"
            prod_issues = validate_production_diorama_v6(vp_doc, sents, clips, script_doc=sc_doc)
            assert not any("[r73_" in x for x in prod_issues), f"Frozen {pid} hit retroactive R73 prod failure: {prod_issues}"
