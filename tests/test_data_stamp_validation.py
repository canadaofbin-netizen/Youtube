"""
Unit tests for R70-M v3.1 Data Stamp Validation (`study` / `illustrative` "Concept" modes,
`R70-M9` Zero-Hallucination & Intuitive Diet blocking gate, R71 conflict avoidance,
and 110-dossier `core_facts[].stats` integrity).
"""

from __future__ import annotations

from pipeline.data_stamp_overlay import (
    seed_data_stamps_from_dossier,
    validate_data_stamps,
    validate_r70_m9_stat_integrity,
)
from pipeline.diorama_assembler import resolve_overlay_window_conflicts


def test_study_and_illustrative_concept_validation() -> None:
    sentences = [
        "Kids in the broken-promise room quit after three minutes.",
        "Yet kids who trusted the researcher waited twelve minutes — four times longer!",
        "Only one in fourteen children ate the treat before the researcher returned.",
        "This follows a classic sigmoid ignition curve in decision neuroscience.",
        "And nine of fourteen kids waited the entire fifteen minutes.",
    ]
    script_ok = {
        "data_stamps": [
            {
                "sentence_index": 1,
                "end_sentence_index": 2,
                "mode": "study",
                "preset": "bar_compare",
                "title": "Marshmallow Wait Time",
                "doi": "10.1016/j.cognition.2012.08.004",
                "source_citation": "Kidd et al. (2013, Cognition)",
                "bars": [
                    {"label": "Broken Promise", "value": 3.0, "unit": "min"},
                    {"label": "Kept Promise", "value": 12.0, "unit": "min"},
                ],
            },
            {
                "sentence_index": 5,
                "mode": "illustrative",
                "preset": "curve_marker",
                "title": "Trust Ignition Threshold",
                "concept": "Sigmoid trust threshold",
                "fn": "sigmoid",
            },
        ]
    }
    errs, warns = validate_data_stamps(script_ok, sentences, return_warnings=True)
    assert errs == []
    assert warns == []

    # Illustrative mode with a DOI must be rejected (R70-M3)
    bad_illustrative = {
        "data_stamps": [
            {
                "sentence_index": 4,
                "mode": "illustrative",
                "preset": "curve_marker",
                "title": "Fake Study Curve",
                "concept": "Sigmoid",
                "doi": "10.1016/j.cognition.2012.08.004",
            }
        ]
    }
    errs_ill = validate_data_stamps(bad_illustrative, sentences)
    assert any("R70-M3" in e for e in errs_ill)


def test_r70_m9_blocks_truncated_years_generic_labels_sd_and_banned_presets() -> None:
    # 1. Exact negative fixture from CEO audit: "In 1970 ... 56 infants" -> 197.0 vs 56.0 + generic labels
    ainsworth_fact = (
        "In 1970, Mary Ainsworth and Barbara Wittig observed 56 middle-class infants "
        "in the 20-minute Strange Situation laboratory procedure."
    )
    bad_ainsworth_stat = {
        "format": "group_means",
        "preset": "bar_compare",
        "mode": "study",
        "title": "Quantitative Study Comparison",
        "bars": [
            {"label": "Baseline / Group 1", "value": 197.0, "unit": ""},
            {"label": "Experimental / Group 2", "value": 56.0, "unit": ""},
        ],
        "doi": "10.2307/1127388",
        "source_citation": "Ainsworth & Wittig (1970)",
    }
    m9_errs = validate_r70_m9_stat_integrity(bad_ainsworth_stat, ainsworth_fact)
    assert any("truncated-year artifact" in e for e in m9_errs)
    assert any("banned placeholder title/label" in e for e in m9_errs)

    # 2. Banned presets (`raincloud`, `violin_box`), `mode="derived"`, `2x1` layout, and `sd` field
    bad_derived_stat = {
        "layout": "2x1",
        "preset": "raincloud",
        "mode": "derived",
        "title": "Wait Time",
        "groups": [
            {"label": "Unreliable", "mean": 3.0, "sd": 0.6, "unit": "min"},
            {"label": "Reliable", "mean": 12.0, "sd": 2.4, "unit": "min"},
        ],
    }
    m9_errs_2 = validate_r70_m9_stat_integrity(bad_derived_stat, "Wait time rose from 3 to 12 minutes.")
    assert any("2x1 multi-panel layout is forbidden" in e for e in m9_errs_2)
    assert any("banned non-intuitive preset" in e for e in m9_errs_2)
    assert any("forbidden mode='derived'" in e for e in m9_errs_2)
    assert any("banned academic dispersion field 'sd'" in e for e in m9_errs_2)

    # 3. Regex word-slicing / unbalanced parens / dangling function words (CEO Phase 3 audit cases)
    bad_regex_sliced = {
        "preset": "bar_compare",
        "mode": "study",
        "title": "Four-Card Puzzle (: Outcome Rate (%)",
        "bars": [
            {"label": "Structured Episodes La", "value": 3.0, "unit": "min"},
            {"label": "Control Cohort", "value": 24.0, "unit": "min"},
        ],
        "doi": "10.2307/1127388",
        "source_citation": "Wason (1968)",
    }
    m9_errs_3 = validate_r70_m9_stat_integrity(
        bad_regex_sliced,
        "8 structured episodes lasting 3 minutes each (24 minutes total).",
    )
    assert any("banned placeholder" in e for e in m9_errs_3)
    assert any("unbalanced parentheses" in e for e in m9_errs_3)
    assert any("dangling/truncated word" in e for e in m9_errs_3)

    # 4. Hard cap `> 2` data_stamps per episode (`DATA_STAMP_MAX_PER_EPISODE == 2`)
    sents = ["One.", "Two.", "Three.", "Four.", "Five.", "Six.", "Seven.", "Eight.", "Nine.", "Ten."]
    three_stamps = {
        "data_stamps": [
            {"sentence_index": 1, "mode": "illustrative", "preset": "curve_marker", "title": "C1", "concept": "C1"},
            {"sentence_index": 5, "mode": "illustrative", "preset": "curve_marker", "title": "C2", "concept": "C2"},
            {"sentence_index": 9, "mode": "illustrative", "preset": "curve_marker", "title": "C3", "concept": "C3"},
        ]
    }
    errs_cap = validate_data_stamps(three_stamps, sents)
    assert any("R70-M1" in e and "> max 2" in e for e in errs_cap)


def test_natural_language_number_matching_and_warning_separation() -> None:
    sentences = [
        "Only one in fourteen kids ate the marshmallow early.",
        "Sentence two.",
        "Sentence three.",
    ]
    script_single = {
        "data_stamps": [
            {
                "sentence_index": 1,
                "mode": "study",
                "preset": "dot_array",
                "title": "Ate Marshmallow Early",
                "highlighted_k": 1,
                "total_n": 14,
                "doi": "10.1016/j.cognition.2012.08.004",
                "source_citation": "Kidd et al. (2013)",
            }
        ]
    }
    errs, warns = validate_data_stamps(script_single, sentences, return_warnings=True)
    assert errs == []
    assert any("R70-M5" in w for w in warns)


def test_r71_anatomy_callout_conflict_avoidance() -> None:
    stamps = [{"start_sec": 10.0, "end_sec": 15.0, "title": "Hero Graph"}]
    callouts = [
        {"canonical_region": "amygdala", "start_sec": 11.0, "end_sec": 14.0},
        {"canonical_region": "prefrontal cortex", "start_sec": 14.0, "end_sec": 19.5},
        {"canonical_region": "hippocampus", "start_sec": 22.0, "end_sec": 26.0},
    ]
    kept, conflicts = resolve_overlay_window_conflicts(stamps, callouts, buffer_sec=2.0)
    regions_kept = [c["canonical_region"] for c in kept]
    assert "amygdala" not in regions_kept
    assert "prefrontal cortex" in regions_kept
    assert "hippocampus" in regions_kept
    pfc = next(c for c in kept if c["canonical_region"] == "prefrontal cortex")
    assert pfc["start_sec"] == 17.0
    assert len(conflicts) == 2


def test_multi_stamp_seeding_from_dossier_stats() -> None:
    dossier = {
        "primary_doi": "10.1016/j.cognition.2012.08.004",
        "citation_short": "Kidd et al. (2013)",
        "core_facts": [
            {
                "fact": "Broken-promise kids waited 3 minutes vs 12 minutes in reliable condition.",
                "source_id": "S1",
                "stats": {
                    "format": "group_means",
                    "preset": "bar_compare",
                    "mode": "study",
                    "title": "Marshmallow Wait Time",
                    "bars": [
                        {"label": "Broken Promise", "value": 3.0, "unit": "min"},
                        {"label": "Kept Promise", "value": 12.0, "unit": "min"},
                    ],
                },
            },
            {
                "fact": "Only 1 of 14 children ate the marshmallow in the reliable group vs 9 of 14.",
                "source_id": "S1",
                "stats": {
                    "format": "count_of_n",
                    "preset": "dot_array",
                    "mode": "study",
                    "title": "Waited Full 15 Min",
                    "highlighted_k": 9,
                    "total_n": 14,
                },
            },
        ],
    }
    sents = [
        "Intro sentence one.",
        "Kids waited 3 minutes when lied to, versus 12 minutes when promised reliability.",
        "Bridge sentence three.",
        "Bridge sentence four.",
        "Bridge sentence five.",
        "In fact, 9 of 14 kids waited the entire fifteen minutes!",
    ]
    seeded = seed_data_stamps_from_dossier(dossier, sents)
    assert len(seeded) == 2
    assert seeded[0]["preset"] == "bar_compare"
    assert seeded[1]["preset"] == "dot_array"
    assert seeded[1]["sentence_index"] - seeded[0]["sentence_index"] >= 4


def test_all_110_dossiers_pass_schema_v2_and_r70_m9_stat_integrity() -> None:
    import json
    from pathlib import Path
    from pipeline.research_dossier import validate_dossier

    dossiers_root = Path(__file__).resolve().parents[1] / "BCI_Shorts_Channel" / "research_dossiers"
    dirs = sorted(d for d in dossiers_root.iterdir() if d.is_dir() and not d.name.startswith("."))
    assert len(dirs) >= 110

    full_check_slugs = {
        "blakemore_cerebellar_tickle_prediction",
        "feinstein_patient_sm_fearless_amygdala",
        "scangos_closed_loop_depression_dbs",
        "ainsworth_strange_situation",
        "kidd_marshmallow_reliability_trust",
    }

    total_stats = 0
    for d in dirs:
        meta = json.loads((d / "dossier.json").read_text(encoding="utf-8"))
        assert int(meta.get("schema_version") or 0) >= 2, f"{d.name} schema_version < 2"
        facts = meta.get("core_facts") or []
        assert len(facts) >= 5, f"{d.name} has {len(facts)} core_facts (< 5)"
        stats_blocks = [
            (f, f["stats"])
            for f in facts
            if isinstance(f, dict) and isinstance(f.get("stats"), dict) and (f["stats"].get("format") or f["stats"].get("preset"))
        ]
        assert 1 <= len(stats_blocks) <= 2, f"{d.name} has {len(stats_blocks)} stats blocks (expected 1..2)"
        total_stats += len(stats_blocks)
        for f_obj, st_b in stats_blocks:
            m9_errs = validate_r70_m9_stat_integrity(st_b, str(f_obj.get("fact") or ""), p_tag=d.name)
            assert m9_errs == [], f"{d.name} failed R70-M9: {m9_errs}"

        if d.name in full_check_slugs:
            res = validate_dossier(d, require_schema_v2=True)
            assert res["ready"], f"{d.name} failed full Schema v2 + R70-M9 validation: {res['issues']}"
            assert res["checklist"].get("depth_standard") is True
            assert res["issues"] == []

    assert 110 <= total_stats <= 220


def test_upper_chart_headroom_luma_distinguishes_dark_i02_void_from_bright_rooms(tmp_path) -> None:
    """Canonical I02 lower-44% dark-void brain backdrops (upper Y=8..42% luma < 24) skip redundant blur+dim scrim while bright rooms keep it."""
    import cv2
    import numpy as np
    from pipeline.data_stamp_overlay import _measure_upper_chart_headroom_luma

    w, h = 540, 960
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    # 1) Canonical I02 dark-void upper headroom (#040711) + bright chalk-white lower brain (Y=46..92%)
    i02_mp4 = tmp_path / "i02_dark_headroom.mp4"
    vw = cv2.VideoWriter(str(i02_mp4), fourcc, 10, (w, h))
    frm = np.full((h, w, 3), (17, 7, 4), dtype=np.uint8)  # BGR for #040711
    frm[int(h * 0.46) : int(h * 0.92), int(w * 0.12) : int(w * 0.88)] = (210, 205, 200)
    for _ in range(10):
        vw.write(frm)
    vw.release()
    luma_i02 = _measure_upper_chart_headroom_luma(i02_mp4, 0.4, w, h)
    assert luma_i02 < 24.0, f"expected I02 dark upper headroom < 24.0, got {luma_i02}"

    # 2) Bright sunlit room backdrop (upper Y=8..42% bright cream wall)
    room_mp4 = tmp_path / "bright_room.mp4"
    vw2 = cv2.VideoWriter(str(room_mp4), fourcc, 10, (w, h))
    frm2 = np.full((h, w, 3), (210, 222, 232), dtype=np.uint8)
    for _ in range(10):
        vw2.write(frm2)
    vw2.release()
    luma_room = _measure_upper_chart_headroom_luma(room_mp4, 0.4, w, h)
    assert luma_room >= 24.0, f"expected bright room upper headroom >= 24.0, got {luma_room}"


def test_dark_void_i02_subject_top_detection_and_compact_chart_zero_overlap(tmp_path) -> None:
    """Line & bar_compare Study charts compacted for Canonical I02 lower brains stay strictly above the detected brain crown with >=40px dark-void margin."""
    import cv2
    import numpy as np
    from pipeline.data_stamp_overlay import (
        _detect_dark_void_lower_subject_top_y,
        render_data_stamp_rgba_frame,
    )

    w, h = 1080, 1920
    brain_top_y = 819
    mp4 = tmp_path / "i02_c21_sim.mp4"
    vw = cv2.VideoWriter(str(mp4), cv2.VideoWriter_fourcc(*"mp4v"), 10, (w, h))
    frm = np.full((h, w, 3), (17, 7, 4), dtype=np.uint8)
    frm[brain_top_y : int(h * 0.90), int(w * 0.14) : int(w * 0.86)] = (210, 205, 200)
    for _ in range(10):
        vw.write(frm)
    vw.release()

    det_y = _detect_dark_void_lower_subject_top_y(mp4, [0.2, 0.5, 0.8], w, h)
    assert det_y is not None and abs(det_y - brain_top_y) <= 6, f"expected ~{brain_top_y}, got {det_y}"

    # 1) Line chart (C21 style) with compact max_y_frac stays >=44px above brain_top_y (819px -> <=775px)
    compact_frac_c21 = (det_y - 46.0) / float(h)
    line_stamp = {
        "mode": "study",
        "preset": "line",
        "chart": "line",
        "style": "ink_pen",
        "title": "Exp. 3 Memory Error Rate",
        "unit": "%",
        "bars": [
            {"label": "Stay Room", "value": 11.0, "unit": "%"},
            {"label": "1 Doorway", "value": 14.0, "unit": "%"},
            {"label": "Return Room", "value": 16.0, "unit": "%"},
        ],
        "doi": "10.1080/17470218.2011.571267",
        "source_citation": "Radvansky et al. (2011)",
    }
    im_line = render_data_stamp_rgba_frame(line_stamp, t_rel=2.6, total_dur=3.6, width=w, height=h, max_y_frac=compact_frac_c21)
    bbox_line = im_line.getbbox()
    assert bbox_line is not None
    assert bbox_line[3] <= brain_top_y - 40, f"line chart bottom {bbox_line[3]}px intrudes on brain top {brain_top_y}px"

    # 2) Bar compare chart (C11 style, brain at 771px) stays strictly above 771px with zero overlap
    brain_top_c11 = 771
    compact_frac_c11 = (brain_top_c11 - 46.0) / float(h)
    bar_stamp = {
        "mode": "study",
        "preset": "bar_compare",
        "chart": "bar_compare",
        "style": "ink_pen",
        "title": "Object Memory Error Rate",
        "unit": "%",
        "bars": [
            {"label": "Same Room Walk", "value": 23.0, "unit": "%"},
            {"label": "Through Doorway", "value": 28.0, "unit": "%"},
        ],
        "doi": "10.1080/17470218.2011.571267",
        "source_citation": "Radvansky et al. (2011)",
    }
    im_bar = render_data_stamp_rgba_frame(bar_stamp, t_rel=2.8, total_dur=3.85, width=w, height=h, max_y_frac=compact_frac_c11)
    bbox_bar = im_bar.getbbox()
    assert bbox_bar is not None
    assert bbox_bar[3] <= brain_top_c11 - 40, f"bar_compare bottom {bbox_bar[3]}px intrudes on brain top {brain_top_c11}px"


