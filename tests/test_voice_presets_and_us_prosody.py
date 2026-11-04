from __future__ import annotations

import pytest

from pipeline.config import (
    DEFAULT_DIORAMA_VOICE_PRESET,
    DESCRIPTION_EDITORIAL_TEMPLATES,
    DIORAMA_COLD_OPEN_S3_BANK,
    DIORAMA_CRISIS_BEAT_BANK,
    DIORAMA_MIDPOINT_REHOOK_BANK,
    DIORAMA_V7_COLD_OPEN_S2_PREFIXES,
    DIORAMA_V7_PROSODY_GEAR_RATES,
    DIORAMA_V7_US_PROSODY_BASE_RATE,
    DIORAMA_V7_US_PROSODY_GEAR_RATES,
    DIORAMA_V7_US_PROSODY_MODE,
    DIORAMA_VOICE_PRESETS,
    STORYTELLER_VOCAL_FILTER_FEMALE,
)
from pipeline.flow_prompt_builder import render_prompt
from pipeline.prosody import (
    base_rate_for_mode,
    classify_prosody_gears,
    rate_to_speed,
    resolve_prosody_mode,
)
from pipeline.publish import (
    classify_us_title_archetype,
    render_editorial_description,
    strip_internal_pipeline_tokens,
    validate_diorama_paradox_title,
)
from pipeline.voice_fallback import (
    STORYTELLER_VOCAL_FILTER,
    _resolve_kokoro_voice,
    resolve_diorama_voice_preset,
)


def test_all_five_voice_presets_have_complete_gender_matched_specs():
    expected_ids = {"andrew_v7", "emma_v7", "ava_v7", "aria_v7", "christopher_v7"}
    assert expected_ids.issubset(set(DIORAMA_VOICE_PRESETS.keys()))
    assert DEFAULT_DIORAMA_VOICE_PRESET == "emma_v7"

    for preset_id in expected_ids:
        spec = DIORAMA_VOICE_PRESETS[preset_id]
        assert spec["voice"].startswith("en-US-")
        assert spec["gender"] in {"male", "female"}
        assert spec["kokoro_voice"]
        assert spec["flow_voice_anchor"].startswith("Voice:")

    # Female voices must keep +0Hz natural pitch and avoid 70Hz male chest EQ
    for fem_id in ("emma_v7", "ava_v7", "aria_v7"):
        spec = DIORAMA_VOICE_PRESETS[fem_id]
        assert spec["gender"] == "female"
        assert spec["pitch"] == "+0Hz"
        assert spec["kokoro_voice"].startswith("af_")
        assert "female" in spec["flow_voice_anchor"].lower()

    assert "highpass=f=95" in STORYTELLER_VOCAL_FILTER_FEMALE
    assert "f=70:" not in STORYTELLER_VOCAL_FILTER_FEMALE
    assert STORYTELLER_VOCAL_FILTER != STORYTELLER_VOCAL_FILTER_FEMALE


def test_resolve_diorama_voice_preset_priority_and_fallbacks():
    # Explicit overrides script_doc and visual_plan
    p_id, spec = resolve_diorama_voice_preset(
        voice_preset="emma_v7",
        script_doc={"voice_preset": "ava_v7"},
        visual_plan={"voice_preset": "andrew_v7"},
    )
    assert p_id == "emma_v7"
    assert spec["voice"] == "en-US-EmmaMultilingualNeural"

    # Script fallback when explicit is None
    p_id2, spec2 = resolve_diorama_voice_preset(
        voice_preset=None,
        script_doc={"voice_preset": "ava_v7"},
        visual_plan={"voice_preset": "andrew_v7"},
    )
    assert p_id2 == "ava_v7"
    assert spec2["kokoro_voice"] == "af_heart"

    # Reverse lookup by neural voice ID (both Emma and legacy Andrew)
    p_id3, _ = resolve_diorama_voice_preset(voice="en-US-EmmaMultilingualNeural")
    assert p_id3 == "emma_v7"
    p_id_and, spec_and = resolve_diorama_voice_preset(voice_preset="andrew_v7")
    assert p_id_and == "andrew_v7"
    assert spec_and["voice"] == "en-US-AndrewMultilingualNeural"

    # Empty / unknown falls back cleanly to channel default (emma_v7)
    p_id4, spec4 = resolve_diorama_voice_preset(voice_preset="nonexistent_preset_xyz", script_doc={})
    assert p_id4 == "emma_v7"
    assert spec4["voice"] == "en-US-EmmaMultilingualNeural"

    # Kokoro gender-matched fallback resolution
    assert _resolve_kokoro_voice("en-US-EmmaMultilingualNeural", voice_preset="emma_v7") == "af_bella"
    assert _resolve_kokoro_voice("en-US-AvaMultilingualNeural") == "af_heart"
    assert _resolve_kokoro_voice("en-US-AndrewMultilingualNeural", voice_preset="andrew_v7") == "am_fenrir"
    assert _resolve_kokoro_voice("", voice_preset=None) == "am_fenrir"


def test_dynamic_us_v7_prosody_rates_and_anticlone_banks():
    assert resolve_prosody_mode("dynamic_us_v7", {}, v7_mode=True) == DIORAMA_V7_US_PROSODY_MODE
    assert resolve_prosody_mode(None, {"prosody_mode": "dynamic_us_v7"}, v7_mode=True) == "dynamic_us_v7"
    assert resolve_prosody_mode("dynamic_us_v7", {}, v7_mode=False) == "uniform_108x"

    assert base_rate_for_mode("dynamic_us_v7") == DIORAMA_V7_US_PROSODY_BASE_RATE == "+7%"
    assert DIORAMA_V7_US_PROSODY_GEAR_RATES == {"rush": "+10%", "stamp": "+4%", "brisk": "+7%"}
    # US 45+ rates are strictly calmer than dynamic_rush_v7 brisk (+15%) and rush (+12%)
    assert rate_to_speed(DIORAMA_V7_US_PROSODY_GEAR_RATES["brisk"]) < rate_to_speed(
        DIORAMA_V7_PROSODY_GEAR_RATES["brisk"]
    )
    assert rate_to_speed(DIORAMA_V7_US_PROSODY_GEAR_RATES["rush"]) < rate_to_speed(
        DIORAMA_V7_PROSODY_GEAR_RATES["rush"]
    )

    # Anti-Clone transition & re-hook banks recognized by classify_prosody_gears
    assert len(DIORAMA_COLD_OPEN_S3_BANK) >= 10
    assert len(DIORAMA_CRISIS_BEAT_BANK) >= 10
    assert len(DIORAMA_MIDPOINT_REHOOK_BANK) >= 8
    assert len(DIORAMA_V7_COLD_OPEN_S2_PREFIXES) >= 5

    sample_sents = [
        "Most parents think a quiet baby is a calm baby!",
        "Yet inside one famous playroom, the calmest toddlers had racing hearts.",
        "Psychologists proved it with Mary Ainsworth's Strange Situation.",
        "Here is where the circuit broke.",
    ]
    gears = classify_prosody_gears(sample_sents, {"acts": [{"sentences": sample_sents}]})
    assert gears[0] == "rush"
    assert gears[1] == "rush"
    assert gears[2] == "stamp"
    assert gears[3] == "stamp"


def test_flow_prompt_injects_female_voice_anchor_when_emma_selected():
    prompt_str = render_prompt(
        scene="A matte-white porcelain mother mannequin sets a toddler on a playmat and reaches for a wooden ring stack",
        narration="In 1970, Mary Ainsworth watched fifty-six toddlers enter an unfamiliar room.",
        voice="emma_v7",
    )
    assert "female" in prompt_str.lower()
    assert "baritone" not in prompt_str.lower()


def test_us_title_archetypes_and_editorial_description_sanitization():
    # All 5 US High-CTR title archetypes validate cleanly
    valid_titles = [
        ("Calm Outside, Racing Heart Inside: The Toddler Paradox", "two_clause_paradox"),
        ("Why Do Ignored Babies Stop Crying So Fast?", "open_loop_question"),
        ("1970 Strange Situation: How Babies Hide Panic", "year_experiment_stamp"),
        ("Your Brain Remembers Every Childhood Goodbye: Attachment", "direct_brain_address"),
        ("8 Three-Minute Rooms, 3 Lifelong Attachment Styles", "numeric_contrast"),
    ]
    for title_txt, expected_arch in valid_titles:
        assert classify_us_title_archetype(title_txt) == expected_arch
        assert validate_diorama_paradox_title(title_txt) == []

    # 3 consecutive identical archetypes trigger diversity warning
    dup_issues = validate_diorama_paradox_title(
        "Calm Face, Spiking Cortisol: Hidden Stress",
        adjacent_titles=[
            "Quiet Play, Racing Pulse: Attachment Mask",
            "No Tears, High Alarm: Avoidant Infants",
        ],
    )
    assert any("3 consecutive episodes" in x for x in dup_issues)

    # Internal token stripper removes pipeline jargon and leftover empty parens
    dirty = "Strange Situation (porcelain_cinematic_v7) [emma_v7] dynamic_us_v7"
    assert strip_internal_pipeline_tokens(dirty) == "Strange Situation"

    # All 4 editorial templates include R4/R9 markers and differ in copy
    rendered = [
        render_editorial_description(
            title="1970 Strange Situation: How Babies Hide Panic (emma_v7)",
            doi_or_url="10.2307/1127388",
            source_summary="Mary Ainsworth measured infant reunion behavior across eight episodes.",
            hashtags=["#Shorts", "#Neuroscience", "#Psychology"],
            template_id=tmpl_id,
        )
        for tmpl_id in DESCRIPTION_EDITORIAL_TEMPLATES
    ]
    assert len(set(rendered)) == len(DESCRIPTION_EDITORIAL_TEMPLATES)
    for desc in rendered:
        assert "emma_v7" not in desc
        assert "Source & Verification: https://doi.org/10.2307/1127388" in desc
        assert "AI Disclosure:" in desc


def test_asr_tokens_folds_double_s_coarticulated_inflections():
    from pipeline.prosody import _asr_tokens

    assert _asr_tokens("But here is the twist: goodbye tears missed the real story!") == _asr_tokens(
        "But here is the twist goodbye tears miss the real story"
    )
    assert _asr_tokens("Signals passed the prefrontal bridge") == _asr_tokens(
        "Signal pass the prefrontal bridge"
    )
    assert _asr_tokens("glass") != _asr_tokens("glad")

