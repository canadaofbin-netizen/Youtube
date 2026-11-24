"""
Unit and regression tests for Rule R68-H (`case_stamp` first-2-second year + institution/person opening hook):
1. Real-year + university action stamp (`"In 2013 at the University of Rochester..."`) passes with 0 issues & 0 advisories.
2. Real-year + named patient (`"In 1999, neuroscientists studied an amnesic patient named Eugene..."`) and duration + named person/MIT (`"For fifty-five years, Patient H.M. shook Brenda Milner's hand every morning at MIT."`) pass.
3. Weak hypothetical `"Imagine you are four years old in a university playroom..."` is hard-blocked on new v8 scripts (both via `validate_script_spine_v8_report` and `validate_production_diorama_v6`), while preserved on `PRE_R68H_FROZEN_V8_PROJECTS` (`project_id="v8_pilot_03_marshmallow_trust_previs"`).
4. Missing year/duration anchor, >22 words, <10 words, '?' ending, missing institution/person anchor, and dry paper-abstract openers (`"In 2013 at Harvard, a study was published..."`) are all hard-blocked.
5. `dossier seed --style-profile expressive_25d_v8` (`seed_diorama_visual_plan`) writes `"opening_mode": "case_stamp"` by default.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

from pipeline import config as cfg
from pipeline.prompt_gate import (
    validate_production_diorama_v6,
    validate_script_spine_v8,
    validate_script_spine_v8_report,
)
from pipeline.research_dossier import init_dossier, seed_diorama_visual_plan


def _base_v8_tail_sentences() -> list[str]:
    return [
        "First, a friendly helper promised giant new crayons — then walked back in empty-handed.",
        "Most parents blame pure willpower when a child eats the treat early.",
        "A second group met a reliable helper who actually brought the promised art set.",
        "Then both groups sat alone with one sweet treat on a small plate.",
        "Kids in the broken-promise room grabbed and ate it after just three minutes.",
        "Wait, what happened when kids knew the adult kept every word?",
        "Children in the reliable room waited twelve full minutes — four times longer!",
        "Over half sat calmly until the timer rang at fifteen minutes.",
        "They weren't born with magical self-control inside that quiet room.",
        "You see, your prefrontal cortex, your planning center, weighs whether waiting pays off.",
        "When promises break, your reward center says grab what's real right now.",
        "When trust holds steady, waiting twelve minutes suddenly feels like a smart bet.",
        "Broken promises train anyone to chase quick rewards instead of long goals.",
        "What looks like weak willpower is often a smart brain pricing broken trust.",
    ]


def _base_v8_doc(**overrides: object) -> dict[str, object]:
    beats = [
        "case_stamp",
        "hook_promise",
        "aggro",
        "evidence",
        "evidence",
        "conflict",
        "escalation",
        "evidence",
        "evidence",
        "setback",
        "core",
        "mechanism",
        "payoff",
        "payoff",
        "climax_cut",
    ]
    doc: dict[str, object] = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "format_profile": "shorts_expressive_v8",
        "opening_mode": "case_stamp",
        "core_reveal_sentence_index": 11,
        "foil_sentence_indices": [],
        "sentence_beats": beats,
    }
    doc.update(overrides)
    return doc


def test_r68h_constants_and_agents_md_size_lock() -> None:
    assert cfg.EXPRESSIVE_V8_DEFAULT_OPENING_MODE == "immediate_brain_shock"
    assert cfg.EXPRESSIVE_V8_LEGACY_CASE_STAMP_OPENING_MODE == "case_stamp"
    assert cfg.EXPRESSIVE_V8_ALLOWED_OPENING_MODES == (
        "immediate_brain_shock",
        "bizarre_experiment",
        "paradox_action",
        "paradox_question",
        "myth_flip_claim",
        "sensory_test",
        "action_first_stamp",
        "action",
        "case_stamp",
        "question",
        "situation",
    )
    assert cfg.EXPRESSIVE_V8_OPENING_CASE_STAMP_MIN_WORDS == 10
    assert cfg.EXPRESSIVE_V8_OPENING_CASE_STAMP_MAX_WORDS == 22
    assert cfg.EXPRESSIVE_V8_CASE_STAMP_ANCHOR_WINDOW_WORDS == 9
    assert cfg.PRE_R68H_FROZEN_V8_PROJECTS == (
        "v8_pilot_01_sleep_first_night_watch",
        "v8_pilot_02_sleep_night_watch_cam3d",
        "v8_pilot_03_marshmallow_trust_previs",
    )
    agents_md = cfg.WORKSPACE_ROOT / ".agents" / "AGENTS.md"
    raw = agents_md.read_bytes()
    assert len(raw) < 10_240, f"AGENTS.md byte size {len(raw)} >= 10,240"
    assert len(raw.decode("utf-8").splitlines()) <= 78


def test_r68h_valid_case_stamp_openers_pass_cleanly() -> None:
    tail = _base_v8_tail_sentences()

    # 1. Year + University + concrete experiment action (18w)
    s1_rochester = (
        "In 2013 at the University of Rochester, researchers broke a promise to four-year-olds right before the Marshmallow Test!"
    )
    rep1 = validate_script_spine_v8_report([s1_rochester] + tail, script_doc=_base_v8_doc())
    assert rep1["issues"] == [], f"Expected Rochester case_stamp pass, got: {rep1['issues']}"
    assert rep1["advisories"] == [], f"Expected 0 advisories, got: {rep1['advisories']}"

    # Also verify `action_open` beat tag remains accepted without advisory
    doc_action_beat = _base_v8_doc(
        sentence_beats=["action_open"] + list(_base_v8_doc()["sentence_beats"])[1:]  # type: ignore[index]
    )
    rep1_beat = validate_script_spine_v8_report([s1_rochester] + tail, script_doc=doc_action_beat)
    assert rep1_beat["issues"] == []
    assert rep1_beat["advisories"] == []

    # 2. Year + neuroscientists + named clinical patient (16w)
    s1_eugene = "In 1999, neuroscientists studied an amnesic patient named Eugene whose conscious memory had been wiped out."
    rep2 = validate_script_spine_v8_report([s1_eugene] + tail, script_doc=_base_v8_doc())
    assert rep2["issues"] == [], f"Expected 1999 Eugene case_stamp pass, got: {rep2['issues']}"

    # 3. Duration stamp ("For fifty-five years") + Patient H.M. + Brenda Milner + MIT (13w)
    s1_hm = "For fifty-five years, Patient H.M. shook Brenda Milner's hand every morning at MIT."
    rep3 = validate_script_spine_v8_report([s1_hm] + tail, script_doc=_base_v8_doc())
    assert rep3["issues"] == [], f"Expected Patient H.M. duration case_stamp pass, got: {rep3['issues']}"


def test_r68h_imagine_blocked_on_new_projects_and_preserved_on_frozen_pilots() -> None:
    tail = _base_v8_tail_sentences()
    s1_imagine = (
        "Imagine you are four years old in a university playroom, and a helper walks back in empty-handed!"
    )

    # Hard-blocked on any new v8 project (even if opening_mode='action' is explicitly passed)
    new_rep = validate_script_spine_v8_report(
        [s1_imagine] + tail,
        script_doc=_base_v8_doc(project_id="v8_ep_04_new_project", opening_mode="action"),
    )
    assert any("weak hypothetical opener" in x for x in new_rep["issues"]), new_rep

    # Also hard-blocked via `validate_production_diorama_v6`
    prod_issues = validate_production_diorama_v6(
        {"schema": 8, "style_profile": "expressive_25d_v8", "project_id": "v8_ep_04_new_project", "zero_clip_reuse": False},
        [s1_imagine] + tail,
        [],
        script_doc=_base_v8_doc(project_id="v8_ep_04_new_project", opening_mode="action"),
    )
    assert any("weak hypothetical opener" in x for x in prod_issues), prod_issues

    # Preserved on frozen pilot `v8_pilot_03_marshmallow_trust_previs`
    frozen_rep = validate_script_spine_v8_report(
        [s1_imagine] + tail,
        script_doc=_base_v8_doc(project_id="v8_pilot_03_marshmallow_trust_previs"),
    )
    assert frozen_rep["issues"] == [], f"Frozen pilot_03 must pass without modification: {frozen_rep['issues']}"


def test_r68h_rejects_missing_year_overlength_missing_entity_and_dry_abstract() -> None:
    tail = _base_v8_tail_sentences()

    # 1. Missing year / temporal stamp in first 9 words -> FAIL
    no_year = "At the University of Rochester, researchers broke a promise to four-year-olds right before the Marshmallow Test!"
    issues_no_year = validate_script_spine_v8([no_year] + tail, script_doc=_base_v8_doc())
    assert any("year/decade or duration stamp" in x for x in issues_no_year), issues_no_year

    # Year pushed past word 9 -> FAIL
    late_year = "Inside a quiet brightly lit university playroom with colorful toys in 2013, researchers broke a promise!"
    issues_late_year = validate_script_spine_v8([late_year] + tail, script_doc=_base_v8_doc())
    assert any("within first 9 words" in x for x in issues_late_year), issues_late_year

    # 2. > 22 words -> FAIL
    over_22w = (
        "In 2013 at the University of Rochester, researchers deliberately broke a solemn promise about giant new crayons "
        "to twenty-eight four-year-olds right before starting the famous test!"
    )
    issues_over = validate_script_spine_v8([over_22w] + tail, script_doc=_base_v8_doc())
    assert any("outside 10-22" in x for x in issues_over), issues_over

    # 3. Missing institution/place/researcher/patient anchor -> FAIL
    no_entity = "In 2013, four-year-olds failed the Marshmallow Test inside a quiet playroom after a broken promise!"
    issues_no_ent = validate_script_spine_v8([no_entity] + tail, script_doc=_base_v8_doc())
    assert any("institution/clinic/place or named researcher/patient" in x for x in issues_no_ent), issues_no_ent

    # 4. Dry paper-abstract opener -> FAIL
    dry_abstracts = [
        "In 2013 at Harvard, a study was published about memory loss in older adults.",
        "In 2015 at Stanford, this study examined how broken promises change childhood self-control.",
        "In 2018 at Oxford, this paper investigates decision fatigue across courtroom judges.",
    ]
    for dry_s1 in dry_abstracts:
        issues_dry = validate_script_spine_v8([dry_s1] + tail, script_doc=_base_v8_doc())
        assert any("dry paper-abstract phrasing" in x for x in issues_dry), (dry_s1, issues_dry)

    # 5. Question '?' ending in case_stamp mode -> FAIL
    q_s1 = "In 2013 at the University of Rochester, why did researchers break a promise to kids?"
    issues_q = validate_script_spine_v8([q_s1] + tail, script_doc=_base_v8_doc())
    assert any("not a '?' question" in x for x in issues_q), issues_q


def test_r68h_dossier_seed_expressive_v8_defaults_to_case_stamp(tmp_path: Path) -> None:
    d_root = tmp_path / "dossiers"
    d_dir = init_dossier("r68h_seed_check", "Rochester Trust Marshmallow Case", "habits", root=d_root)
    seeded_vp = seed_diorama_visual_plan(
        d_dir,
        root=d_root,
        schema_version=8,
        style_profile="expressive_25d_v8",
        overwrite=True,
    )
    assert seeded_vp["opening_mode"] == "immediate_brain_shock"
    assert seeded_vp["ending_mode"] == "mic_drop"
    sc_path = d_dir / "diorama_v8_expressive" / "script.json"
    assert sc_path.exists()
    sc_doc = json.loads(sc_path.read_text(encoding="utf-8"))
    assert sc_doc["opening_mode"] == "immediate_brain_shock"
    assert sc_doc["ending_mode"] == "mic_drop"

    # Also verify CLI `main.py dossier seed --style-profile expressive_25d_v8`
    cli_dir = init_dossier("r68h_cli_seed_check", "Iowa Fearless Amygdala Case", "disease", root=d_root)
    proc = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "main.py",
            "dossier",
            "seed",
            "--slug",
            "r68h_cli_seed_check",
            "--root",
            str(d_root),
            "--style-profile",
            "expressive_25d_v8",
            "--write",
            "--overwrite",
        ],
        cwd=str(cfg.WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert proc.returncode == 0
    cli_sc = json.loads((cli_dir / "diorama_v8_expressive" / "script.json").read_text(encoding="utf-8"))
    assert cli_sc["opening_mode"] == "immediate_brain_shock"
    assert cli_sc["ending_mode"] == "mic_drop"
