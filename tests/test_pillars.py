"""Tests for the 7 canonical ALL ABOUT BRAIN Content Pillars (`pipeline/pillars.py`)."""

from __future__ import annotations

from pipeline.config import NARRATIVE_STYLE_SPECS, PILLAR_DEFAULT_STYLE_MAP, resolve_narrative_style
from pipeline.pillars import PILLARS_DATA, get_pillar, list_all_pillars


def test_all_seven_pillars_and_style_mapping() -> None:
    pillars = list_all_pillars()
    assert len(pillars) == 7
    expected_ids = {
        "bci_tech",
        "brain_mysteries",
        "brain_history",
        "bci_ethics",
        "brain_basics",
        "brain_news",
        "brain_health",
    }
    assert {p.id for p in pillars} == expected_ids
    assert set(PILLARS_DATA.keys()) == expected_ids

    for pillar in pillars:
        assert get_pillar(pillar.id) == pillar
        assert get_pillar(pillar.name) == pillar
        assert get_pillar(pillar) == pillar
        assert pillar.name
        assert pillar.target_theme
        assert pillar.architectural_metaphor
        assert pillar.academic_domain
        assert pillar.default_narrative_style in NARRATIVE_STYLE_SPECS
        default_style = PILLAR_DEFAULT_STYLE_MAP[pillar.id]
        assert default_style in NARRATIVE_STYLE_SPECS
        assert resolve_narrative_style("", pillar.id) == default_style

    # Fallback on unknown label returns bci_tech
    assert get_pillar("unknown_custom_label").id == "bci_tech"
