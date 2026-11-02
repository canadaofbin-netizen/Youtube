"""R57-H2 Schema v7 3-sentence cold-open gate + P2 recalibration (approved HM Plan B, 2026-10-31)."""
from pipeline.config import PROSODY_P2_HOOK_END_MAX_SEC, PROSODY_P2_STAMP_END_MAX_SEC
from pipeline.prompt_quality_v5 import validate_cold_open_v7

GOLDEN = [
    "People joke about goldfish memory — real goldfish remember months, but he forgot faces in minutes!",
    "Yet his hands mastered a brand-new skill in just three days!",
    "This is the true story of Patient H.M.",
    "Here is what went wrong in Hartford, nineteen fifty-three.",
]


def test_golden_cold_open_passes():
    assert validate_cold_open_v7(GOLDEN) == []


def test_weak_cold_open_flags_each_beat():
    bad = [
        "Imagine losing your left arm ten years ago.",
        "His brain kept feeling the missing hand every single day for years and years.",
        "Doctors were puzzled.",
    ]
    issues = " ".join(validate_cold_open_v7(bad))
    assert "S1 hook must end with '!'" in issues
    assert "S2 contrast has" in issues
    assert "S2 must open with a contrast word" in issues
    assert "S3 must be the case stamp" in issues


def test_case_stamp_must_name_case_and_short_scripts_fail():
    assert any("must name the case" in i for i in validate_cold_open_v7(GOLDEN[:2] + ["This is the true story of."]))
    assert validate_cold_open_v7(GOLDEN[:2])


def test_p2_thresholds_fit_approved_cold_open():
    # Approved HM Plan B render: S2 ends 8.44s, S3 case stamp ends 10.93s
    assert 8.44 <= PROSODY_P2_HOOK_END_MAX_SEC
    assert 10.93 <= PROSODY_P2_STAMP_END_MAX_SEC


def test_asr_tokens_fold_orthographic_variants_only():
    from pipeline.prosody import _asr_tokens

    assert _asr_tokens("This is the true story of Patient H.M.")[-2:] == _asr_tokens("patient hm") == _asr_tokens("patient H M")
    assert _asr_tokens("a brand-new skill") == _asr_tokens("a brand new skill")
    assert _asr_tokens("juggled balls and test") == _asr_tokens("juggle balls and tests")
    # genuine mis-hearings must still differ
    assert _asr_tokens("brains run") != _asr_tokens("rains run")
