"""Unit tests for the sentence-level prosody engine (R63-P) and render guards (F-1..F-5)."""

from __future__ import annotations

import json
from pathlib import Path

import numpy as np
import pytest

from pipeline.config import (
    DIORAMA_V7_PROSODY_GEAR_RATES,
    DIORAMA_V7_PROSODY_GEARS,
    DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP,
)
from pipeline.prosody import (
    apply_emphasis,
    base_rate_for_mode,
    classify_prosody_gears,
    fade_edges,
    measure_internal_max_silence,
    plan_sentence_prosody,
    rate_to_speed,
    resolve_prosody_mode,
)

SCRIPT = {
    "acts": [
        {"sentences": ["People joke about goldfish memory, but he forgot in minutes!", "Yet his hands learned in three days!", "This is the true story of Patient H.M.", "Here is what went wrong in Hartford."]},
        {"sentences": ["He met a doctor.", "She gave him a number.", "Was it gone forever?"]},
        {"sentences": ["Then he traced a star.", "Yet the mirror flipped every move.", "Then he glided cleanly.", "Then he smiled.", "Which proves memory is many systems."]},
        {"sentences": ["x."]},
        {"sentences": ["Then a.", "Yet b.", "Then c.", "Yet d."]},
        {"sentences": ["Which is why it matters."]},
    ]
}
SENTS = [s for a in SCRIPT["acts"] for s in a["sentences"]]


def test_resolve_mode_defaults_and_overrides():
    assert resolve_prosody_mode(None, {}, v7_mode=True) == "dynamic_us_v7"
    assert resolve_prosody_mode(None, {"prosody_mode": "uniform_108x"}, v7_mode=True) == "uniform_108x"
    assert resolve_prosody_mode(None, {"prosody_mode": "dynamic_rush_v7"}, v7_mode=True) == "dynamic_rush_v7"
    assert resolve_prosody_mode("uniform_110x", {"prosody_mode": "dynamic_rush_v7"}, v7_mode=True) == "uniform_110x"
    assert resolve_prosody_mode("dynamic_rush_v7", {}, v7_mode=False) == "uniform_108x"
    assert resolve_prosody_mode("bogus", {}, v7_mode=True) == "dynamic_us_v7"
    assert base_rate_for_mode("uniform_110x") == "+10%"
    assert base_rate_for_mode("dynamic_rush_v7") == "+8%"
    assert base_rate_for_mode("dynamic_us_v7") == "+7%"
    assert base_rate_for_mode("uniform_108x") is None


def test_gear_classification_rules():
    g = classify_prosody_gears(SENTS, SCRIPT)
    assert g[0] == "rush" and g[1] == "rush"          # hook sentences
    assert g[2] == "stamp"                             # case stamp
    assert g[3] == "stamp"                             # signature diagnostic opener
    assert g[4] == "brisk"
    assert g[6] == "stamp"                             # Act-boundary question
    assert g[11] == "stamp"                            # 'Which proves'
    assert g[-1] == "stamp"


def test_rush_streak_cap_demotes_fourth():
    g = classify_prosody_gears(SENTS, SCRIPT)
    act5 = g[13:17]  # four consecutive Act 5 'Then/Yet' lines
    assert act5[:3] == ["rush", "rush", "rush"]
    assert act5[3] == "brisk"


def test_manual_override_wins():
    doc = {**SCRIPT, "prosody_gears": {"5": "rush"}}
    assert classify_prosody_gears(SENTS, doc)[4] == "rush"


def test_plan_factors_gaps_and_clamp():
    plan = plan_sentence_prosody(SENTS, SCRIPT, "dynamic_rush_v7")
    assert plan[0]["gap_before_sec"] == 0.0
    stamp = plan[2]
    assert stamp["gear"] == "stamp" and stamp["gap_before_sec"] == DIORAMA_V7_PROSODY_GEARS["stamp"]["gap_before"]
    assert abs(stamp["target_tempo"] - 1.08) < 1e-3
    for prev, cur in zip(plan, plan[1:]):
        if cur["gap_before_sec"] < 0.10:
            assert abs(cur["base_wsola_factor"] - prev["base_wsola_factor"]) <= DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP + 1e-6
    act2_first = plan[4]
    assert act2_first["act_boundary_before"] and act2_first["gap_before_sec"] >= 0.20


def test_gear_rates_match_gear_tempos():
    for g, spec in DIORAMA_V7_PROSODY_GEARS.items():
        assert abs(rate_to_speed(DIORAMA_V7_PROSODY_GEAR_RATES[g]) - float(spec["tempo"])) < 1e-6


def test_dynamic_plan_uses_native_gear_rates_without_wsola():
    plan = plan_sentence_prosody(SENTS, SCRIPT, "dynamic_rush_v7")
    for p in plan:
        # native synthesis: the synth rate reproduces the target tempo (residual < 0.5%, normally exactly 1.0)
        assert abs(rate_to_speed(p["synth_rate"]) * p["wsola_factor"] - p["target_tempo"]) < 1e-3
        if not p["tempo_clamped"]:
            assert p["synth_rate"] == DIORAMA_V7_PROSODY_GEAR_RATES[p["gear"]]
            assert p["wsola_factor"] == 1.0
    assert {p["synth_rate"] for p in plan} <= set(DIORAMA_V7_PROSODY_GEAR_RATES.values()) | {
        p["synth_rate"] for p in plan if p["tempo_clamped"]
    }


def test_native_gear_slices_taken_from_matching_rate_stream(tmp_path: Path):
    """Offline test stub synthesizes distinct per-gear tempos natively without WSOLA."""
    import pipeline.voice_fallback as vf

    p_dir = tmp_path / "stub_gears"
    (p_dir / "03_visuals").mkdir(parents=True)
    (p_dir / "04_audio").mkdir(parents=True)
    (p_dir / "03_visuals" / "visual_plan.json").write_text('{"schema": 7}', encoding="utf-8")
    res = vf.synthesize_continuous_diorama_track(
        p_dir,
        SENTS,
        align_whisper=False,
        script_doc=SCRIPT,
        prosody_mode="dynamic_rush_v7",
        allow_test_stub=True,
    )
    assert res["report"]["engine"] == "test_stub"
    pros_rep = json.loads((p_dir / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
    assert pros_rep["native_gear_synthesis"] is True
    assert all(abs(float(s["wsola_factor"]) - 1.0) < 1e-6 for s in pros_rep["sentences"])


def test_fade_edges_zero_endpoints():
    sr = 16000
    pcm = np.full(sr // 10, 0.5, dtype=np.float32)
    out = fade_edges(pcm, sr)
    assert out[0] == 0.0 and abs(out[-1]) < 1e-6
    assert abs(out[len(out) // 2] - 0.5) < 1e-6


def test_uniform_110_plan_has_no_wsola():
    plan = plan_sentence_prosody(SENTS, SCRIPT, "uniform_110x")
    assert all(p["wsola_factor"] == 1.0 for p in plan)
    assert all(abs(p["target_tempo"] - 1.10) < 1e-6 for p in plan)


def test_emphasis_inserts_pause_and_shifts_words():
    sr = 16000
    pcm = (0.2 * np.sin(np.linspace(0, 400, sr))).astype(np.float32)
    words = [(0.0, 0.3, "Yet"), (0.3, 0.6, "118"), (0.6, 1.0, "IQ")]
    # 1. Default 0.0s pause preserves co-articulation & exact sample length while lifting target word gain
    out_smooth, w_smooth, hits_smooth = apply_emphasis(pcm, sr, words, ["118"])
    assert hits_smooth == 1
    assert len(out_smooth) == len(pcm)
    assert w_smooth == words
    assert float(np.max(np.abs(out_smooth[int(0.35 * sr) : int(0.55 * sr)]))) > float(
        np.max(np.abs(pcm[int(0.35 * sr) : int(0.55 * sr)]))
    )
    assert float(np.max(np.abs(np.diff(out_smooth)))) <= float(np.max(np.abs(np.diff(pcm)))) * 1.2 + 1e-3

    # 2. Explicit positive pause_sec inserts cosine-faded micro-pause & shifts subsequent word timestamps
    out, w2, hits = apply_emphasis(pcm, sr, words, ["118"], pause_sec=0.045)
    assert hits == 1
    assert len(out) > len(pcm)
    assert w2[0] == words[0]
    assert w2[1][0] > words[1][0] and w2[2][0] > words[2][0]
    assert float(np.max(np.abs(np.diff(out)))) <= float(np.max(np.abs(np.diff(pcm)))) * 1.2 + 1e-3


def test_studio_vocoder_humanizer_and_booth_glue_preserve_exact_length():
    from pipeline.voice_fallback import _apply_studio_booth_glue, _humanize_vocoder_pcm

    sr = 48000
    t = np.arange(sr, dtype=np.float32) / float(sr)
    raw = (0.25 * np.sin(2.0 * np.pi * 165.0 * t) + 0.06 * np.sin(2.0 * np.pi * 6400.0 * t)).astype(np.float32)
    warmed = _humanize_vocoder_pcm(raw, sr)
    assert warmed.shape == raw.shape
    assert warmed.dtype == np.float32
    assert float(np.max(np.abs(warmed))) <= 0.96

    glued = _apply_studio_booth_glue(warmed, sr, lead_sec=0.05, speech_end_sec=0.90)
    assert glued.shape == warmed.shape
    assert glued.dtype == np.float32
    # Silence gap between words no longer sits at mathematical 0.0 vacuum
    silent_master = np.zeros(sr, dtype=np.float32)
    silent_master[int(0.1 * sr) : int(0.3 * sr)] = 0.25 * np.sin(2.0 * np.pi * 200.0 * t[: int(0.2 * sr)])
    glued_gap = _apply_studio_booth_glue(silent_master, sr, lead_sec=0.05, speech_end_sec=0.90)
    gap_rms = float(np.sqrt(np.mean(np.square(glued_gap[int(0.5 * sr) : int(0.8 * sr)]))))
    assert 1e-5 < gap_rms < 5e-3


def test_internal_silence_measurement():
    sr = 16000
    tone = (0.3 * np.sin(np.linspace(0, 300, sr // 4))).astype(np.float32)
    gap = np.zeros(int(0.2 * sr), dtype=np.float32)
    pcm = np.concatenate([tone, gap, tone])
    assert 0.17 <= measure_internal_max_silence(pcm, sr) <= 0.22


def test_published_project_guard(tmp_path: Path):
    from pipeline.diorama_assembler import assemble_diorama_project

    p = tmp_path / "proj"
    (p / "06_publish").mkdir(parents=True)
    (p / "06_publish" / "upload_receipt.json").write_text(json.dumps({"video_id": "abc"}), encoding="utf-8")
    with pytest.raises(RuntimeError, match="already published"):
        assemble_diorama_project(p, force_rebuild=True)


def test_template_review_detector(tmp_path: Path):
    from pipeline.posthoc_semantic_qa import validate_posthoc_semantic_review

    p = tmp_path / "proj"
    (p / "05_assembly").mkdir(parents=True)
    rows = [
        {
            "cut_index": i,
            "grammar": "lowpoly_hands_closeup",
            "camera_move": "locked_tripod",
            "viewer_sheet": f"sheet_{i:02d}.jpg",
            "intended_scene": f"unique scene number {i}",
            "spoken_narration": "",
            "auto_populated": False,
            "expresses_intended_meaning": True,
            "observed_visual_summary": f"Verified cut #{i:02d} clarity={90 + i % 7}: clean geometry with zero text plaque detail {i}",
        }
        for i in range(1, 21)
    ]
    rev = {"final_mp4_sha256": "x", "edl_sha256": "y", "cuts": rows}
    (p / "05_assembly" / "posthoc_semantic_review.json").write_text(json.dumps(rev), encoding="utf-8")
    res = validate_posthoc_semantic_review(p, "x", "y", 20)
    assert any("templated_review_notes" in s for s in res["issues"])


def test_master_hf_chain_is_single_light_deesser():
    """Q-2: HF is no longer attenuated three times (vocal lowpass + -3.8dB + master -3dB EQ + strong deesser)."""
    import pipeline.config as cfg
    from pipeline.voice_fallback import STORYTELLER_VOCAL_FILTER

    src = (Path(__file__).resolve().parents[1] / "pipeline" / "diorama_assembler.py").read_text(encoding="utf-8")
    assert "equalizer=f=6500" not in src
    assert "deesser=i=0.58" not in src
    assert "_cfg.DIORAMA_V7_MASTER_DEESSER" in src
    assert cfg.DIORAMA_V7_MASTER_DEESSER.startswith("deesser=i=")
    assert float(cfg.DIORAMA_V7_MASTER_DEESSER.split("i=")[1].split(":")[0]) < 0.58
    assert "lowpass" not in STORYTELLER_VOCAL_FILTER
