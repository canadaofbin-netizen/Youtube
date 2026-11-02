"""Tests for R62 Dynamic Per-Episode QA Contract Compiler & 3-Stage Multimodal Gate."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np

from pipeline import config as cfg
from pipeline.depiction_rules import LiteralAnalogyCutawayRule, validate_zero_flesh_and_crystal_specimen
from pipeline.dynamic_episode_qa import (
    compile_episode_qa_contract,
    compute_ceramic_highlight_ratio,
    compute_green_turf_ratio,
    verify_clip_multimodal_contract,
    verify_pre_flow_contract,
)
from pipeline.flow_prompt_builder import build_flow_prompts
from pipeline.plain_language import to_display_text, to_expressive_tts_text

ROOT = Path(cfg.WORKSPACE_ROOT)
GOLDEN_V65_DIR = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "phineas_gage_iron_rod" / "diorama_v6_dynamic"


def test_phineas_phonetic_tts_vs_clean_subtitle_display() -> None:
    raw = "Minutes later, Phineas Gage sits up — sounds impossible, right?"
    tts = to_expressive_tts_text(raw)
    disp = to_display_text(raw)
    assert "Fin-ee-us Gage" in tts
    assert "Phineas Gage" in disp
    assert "Fin-ee-us" not in disp


def test_clothed_ceramic_trauma_and_literal_analogy_rules() -> None:
    trauma_scene = (
        "Isometric 3D architectural cutaway diorama of a granite ledge. "
        "A featureless matte-white bisque-ceramic figure wearing a dark brimmed cap, charcoal waistcoat, and boots "
        "stands on the rock shelf as a tapered iron rod shoots straight upward cleanly through its smooth matte-white "
        "ceramic ovoid head, knocking its cap into the air."
    )
    assert validate_zero_flesh_and_crystal_specimen(trauma_scene, "arch_cutaway_diorama") == []

    football_scene = LiteralAnalogyCutawayRule.compose(
        "a lush green-turf football stadium field miniature with crisp unnumbered white yard-line stripes",
        "a glowing amber trajectory arc lands cleanly at the first-quarter stripe of the green football field",
        "pullback_parallax_reveal",
    )
    assert validate_zero_flesh_and_crystal_specimen(football_scene, "literal_analogy_cutaway") == []


def test_dynamic_episode_qa_gate1_catches_abstract_grid_and_passes_golden_v65() -> None:
    script_doc = json.loads((GOLDEN_V65_DIR / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((GOLDEN_V65_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]
    clips = build_flow_prompts(visual_plan, sentences)

    contract = compile_episode_qa_contract(visual_plan, sentences, clips, script_doc=script_doc)
    analogy_ids = {a["analogy_id"] for a in contract["analogy_locks"]}
    assert {"football_field", "bowling_ball", "baseball_bat", "playing_card"}.issubset(analogy_ids)
    assert len(contract["cast_clip_locks"]) >= 8

    issues = verify_pre_flow_contract(visual_plan, sentences, clips, script_doc=script_doc)
    assert issues == [], f"Expected 0 Gate 1 issues on Golden Gage v6.5, got: {issues}"

    # Regressing football field back to an abstract oak grid MUST fail Gate 1 immediately
    bad_clips = [dict(c) for c in clips]
    for c in bad_clips:
        if c.get("sentence_index") == 13:
            c["scene"] = "Macro shot of a miniature dark-oak field grid divided into four equal recessed brass bays."
    bad_issues = verify_pre_flow_contract(visual_plan, sentences, bad_clips, script_doc=script_doc)
    assert any("football field" in x.lower() for x in bad_issues)


def test_gate2_green_turf_and_ceramic_cv_signatures(tmp_path: Path) -> None:
    # Synthetic dark-void clip WITH green stadium turf -> passes football_field contract
    green_mp4 = tmp_path / "clip_green.mp4"
    dark_mp4 = tmp_path / "clip_no_green.mp4"
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")

    for out_p, add_green in ((green_mp4, True), (dark_mp4, False)):
        vw = cv2.VideoWriter(str(out_p), fourcc, 24.0, (360, 640))
        for f_i in range(110):
            frm = np.full((640, 360, 3), (24, 16, 12), dtype=np.uint8)
            if add_green:
                frm[220:430, 50:310] = (45, 145, 38)  # BGR lush green turf
            # Moving white ceramic highlight
            x0 = 60 + (f_i * 2) % 180
            frm[260:330, x0 : x0 + 48] = (232, 232, 232)
            vw.write(frm)
        vw.release()

    sample_green = np.full((640, 360, 3), (24, 16, 12), dtype=np.uint8)
    sample_green[220:430, 50:310] = (45, 145, 38)
    sample_green[260:330, 90:140] = (232, 232, 232)
    assert compute_green_turf_ratio(sample_green) > 0.08
    assert compute_ceramic_highlight_ratio(sample_green) > 0.01

    mock_contract = {
        "analogy_locks": [
            {
                "analogy_id": "football_field",
                "bound_clip_numbers": [15],
                "cv_signature": "green_stadium_turf",
            }
        ],
        "cast_clip_locks": [{"clip_number": 15}],
    }
    ok_rep = verify_clip_multimodal_contract(green_mp4, 15, mock_contract)
    fail_rep = verify_clip_multimodal_contract(dark_mp4, 15, mock_contract)
    assert ok_rep["passed"] is True
    assert fail_rep["passed"] is False
    assert any("missing_green_stadium_turf" in x for x in fail_rep["issues"])


def test_verify_final_mp4_against_contract_save_report_false_is_zero_write() -> None:
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract

    gage_v7 = cfg.PROJECTS_DIR / "gage_diorama_v7_lowpoly"
    if not (gage_v7 / "05_assembly" / "final_shorts_1080x1920.mp4").exists():
        return
    snap_pre = {
        f.relative_to(gage_v7).as_posix(): (f.stat().st_mtime_ns, f.stat().st_size)
        for f in sorted(gage_v7.rglob("*"))
        if f.is_file()
    }
    rep = verify_final_mp4_against_contract(gage_v7, save_report=False)
    snap_post = {
        f.relative_to(gage_v7).as_posix(): (f.stat().st_mtime_ns, f.stat().st_size)
        for f in sorted(gage_v7.rglob("*"))
        if f.is_file()
    }
    assert rep["passed"] is True
    assert snap_pre == snap_post

