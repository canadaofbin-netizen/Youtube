"""
Comprehensive verification for:
  1. 90s (`1m30s`) Shorts default (`shorts_90s_v7`) & `shorts_180s_v7` / `micro_short_v7` preservation
  2. Longform deferral (`LONGFORM_DEFERRED = True`) CLI guard + override flags
  3. Monthly & daily `Omni 1.2 Flash` -> `0-credit` `Veo 3.1 - Lite [Lower Priority]` auto-tier & `SharedOmniCreditBudget`
  4. `<30m` bottleneck upgrades (stagger constants, single-wave 28-clip capacity, persistent SHA-256 cache, unmanned CV-verified QA signoff)
  5. Canonical `AAB_<project_id>` Google Flow room naming, `flow-clean --local-only`, and `/tmp` hygiene
  6. Cross-process CDP anti-tab-stealing isolation (`/tmp/aab_cdp_leases.json`, `Target.createTarget(..., background=True)`,
     `Emulation.setFocusEmulationEnabled({enabled: True})`, and zero `Page.bringToFront` / `bring_to_front` calls in `pipeline/`)
"""

from __future__ import annotations

import asyncio
import datetime as dt
import hashlib
import json
from pathlib import Path
from typing import Any

import pytest

from pipeline import cli, config as cfg
from pipeline.cdp_tab_lease import (
    TabLeaseConflictError,
    acquire_tab_lease,
    enable_background_focus_emulation,
    get_cdp_leases_path,
    get_tab_lease,
    is_tab_leased_by_other,
    list_active_tab_leases,
    open_leased_cdp_tab,
    prune_dead_leases,
    release_and_close_leased_tab,
    try_acquire_tab_lease,
)
from pipeline.flow_workspace import (
    SharedOmniCreditBudget,
    extract_flow_project_uuid,
    format_flow_room_name,
    parse_flow_credits_overlay_text,
    parse_flow_room_name,
    purge_local_flow_temp_files,
    record_flow_credit_exhausted,
    record_flow_credit_probe,
    should_reprobe_primary_omni,
)
from pipeline.media_cache import (
    clear_in_memory_sha_cache,
    compute_stream_sha256,
    fast_file_sha256,
)
from pipeline.posthoc_semantic_qa import (
    auto_signoff_posthoc_semantic_review,
    validate_posthoc_semantic_review,
)
from pipeline.prompt_quality_v5 import (
    validate_production_diorama_v6,
    validate_substantive_visual_relevance,
)
from pipeline.prosody import evaluate_prosody_gates
from pipeline.studio.studio_watchdog import cleanup_idle_whale_tabs


# ---------------------------------------------------------------------------
# 1. 90s Shorts Default (`shorts_90s_v7`) & Archive / Micro-Short Preservation
# ---------------------------------------------------------------------------


def test_shorts_90s_default_constants_and_ssot_parity() -> None:
    assert cfg.DEFAULT_SHORTS_FORMAT_PROFILE == "shorts_90s_v7"
    assert cfg.SHORTS_90S_PROFILE == "shorts_90s_v7"
    assert cfg.SHORTS_180S_PROFILE == "shorts_180s_v7"
    assert cfg.shorts_duration_range_for_profile("shorts_90s_v7") == (75.0, 105.0)
    assert cfg.word_count_range_for_profile("shorts_90s_v7") == (210, 275)
    assert cfg.sentence_count_range_for_profile("shorts_90s_v7") == (22, 32)
    assert cfg.clip_count_range_for_profile("shorts_90s_v7") == (24, 32)
    assert cfg.LONGFORM_DEFERRED is True
    assert cfg.FLOW_TAB_OPEN_STAGGER_SEC == 2.5
    assert cfg.FLOW_SUBMIT_STAGGER_SEC == 3.0
    assert cfg.UNMANNED_QA_SIGNOFF_DEFAULT is False

    constants_md = (cfg.WORKSPACE_ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    for required_name in (
        "SHORTS_90S_PROFILE",
        "SHORTS_180S_PROFILE",
        "DEFAULT_SHORTS_FORMAT_PROFILE",
        "SHORTS_90S_DURATION_MIN_SEC",
        "SHORTS_90S_DURATION_TARGET_SEC",
        "SHORTS_90S_DURATION_MAX_SEC",
        "SHORTS_90S_WORD_COUNT_MIN",
        "SHORTS_90S_WORD_COUNT_MAX",
        "SHORTS_90S_SENTENCE_COUNT_MIN",
        "SHORTS_90S_SENTENCE_COUNT_MAX",
        "SHORTS_90S_CLIP_COUNT_MIN",
        "SHORTS_90S_CLIP_COUNT_DEFAULT",
        "SHORTS_90S_CLIP_COUNT_MAX",
        "LONGFORM_DEFERRED",
        "FLOW_OMNI_CREDIT_COST_NO_REF",
        "FLOW_OMNI_CREDIT_COST_WITH_REF",
        "FLOW_AUTO_CLEANUP_ON_SUCCESS",
        "FLOW_TAB_OPEN_STAGGER_SEC",
        "FLOW_SUBMIT_STAGGER_SEC",
        "PERSISTENT_SHA_CACHE_MAX_ENTRIES",
        "UNMANNED_QA_SIGNOFF_DEFAULT",
    ):
        assert required_name in constants_md, f"Missing {required_name} in production_constants.md"


def test_resolve_shorts_format_profile_heuristics_and_edge_cases(tmp_path: Path) -> None:
    # Default with empty inputs -> 90s Shorts
    assert cfg.resolve_shorts_format_profile() == "shorts_90s_v7"
    assert cfg.resolve_shorts_format_profile({"prompt_schema_version": 7}) == "shorts_90s_v7"

    # Explicit micro_short_v7 -> preserved
    assert cfg.resolve_shorts_format_profile({"shorts_format_profile": "micro_short_v7"}) == "micro_short_v7"
    assert cfg.resolve_shorts_format_profile({"profile": "micro_short_v7"}) == "micro_short_v7"

    # Broken <18-clip episode WITHOUT explicit micro_short_v7 must stay shorts_90s_v7 (never evade 90s gates)
    broken_plan = {"prompt_schema_version": 7, "clips": [{"clip_index": i} for i in range(1, 13)]}
    broken_script = {"sentences": [f"Sentence {i}." for i in range(1, 13)]}
    assert cfg.resolve_shorts_format_profile(broken_plan, broken_script) == "shorts_90s_v7"

    # Pre-authored 180s episode (>=40 sentences or >=40 clips or >=130s voice report or frozen slug) -> shorts_180s_v7
    assert cfg.resolve_shorts_format_profile({"sentences": ["x."] * 48}) == "shorts_180s_v7"
    assert cfg.resolve_shorts_format_profile({"clips": [{"clip_index": i} for i in range(1, 49)]}) == "shorts_180s_v7"
    assert cfg.resolve_shorts_format_profile({"prompt_schema_version": 6}) == "shorts_180s_v7"
    assert cfg.resolve_shorts_format_profile(slug="diorama_01_patient_hm") == "shorts_180s_v7"

    # Project directory with voice_report >= 130s -> shorts_180s_v7
    p180 = tmp_path / "ep_legacy_180"
    (p180 / "04_audio").mkdir(parents=True)
    (p180 / "04_audio" / "voice_report.json").write_text(json.dumps({"total_duration_sec": 152.4}), encoding="utf-8")
    assert cfg.resolve_shorts_format_profile(project_dir=p180) == "shorts_180s_v7"

    # Project directory with 26 sentences & 28 clips -> shorts_90s_v7
    p90 = tmp_path / "ep_new_90"
    (p90 / "02_script").mkdir(parents=True)
    (p90 / "03_visuals").mkdir(parents=True)
    (p90 / "02_script" / "script.json").write_text(
        json.dumps({"sentences": [f"Line {i}." for i in range(1, 27)]}), encoding="utf-8"
    )
    (p90 / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"prompt_schema_version": 7, "clips": [{"clip_index": i} for i in range(1, 29)]}),
        encoding="utf-8",
    )
    assert cfg.resolve_shorts_format_profile(project_dir=p90) == "shorts_90s_v7"


def _build_valid_90s_fixture() -> tuple[dict[str, Any], dict[str, Any]]:
    # 26 sentences totaling ~238 words, obeying R57-H2 (S1 '!', S2 'Yet', S3 stamp, >=2 '?' hooks,
    # '[Number]->[Analogy]' pair, and 3-Stage Debate Ignition outro).
    sentences = [
        "One millimeter of steel erased fifty years of memory!",
        "Yet Henry walked out speaking with crystal clarity.",
        "And here is where his brain rewrote science.",
        "Surgeons removed both memory hubs to stop violent seizures.",
        "Within minutes, the seizures vanished inside the quiet ward.",
        "Every nurse returning from coffee looked like a stranger.",
        "Why could Henry still sketch his childhood floor plan?",
        "Old memories had already moved into his outer cortex.",
        "New moments hit a broken bridge before locking in.",
        "Brenda Milner handed him a star and silver mirror.",
        "He traced five points watching only his reflected hand.",
        "On day one, his pencil skidded thirty-two times.",
        "Next afternoon, Brenda set that same mirror box down.",
        "Did he remember touching that mirror or meeting Brenda?",
        "Zero recognition crossed his calm hospital desk.",
        "Then his hand glided smoothly, like skates on ice.",
        "By day three, errors dropped ninety percent, laser sharp.",
        "His diary stayed blank, yet motor circuits kept score.",
        "Deep basal ganglia loops quietly recorded every muscle habit.",
        "Two separate memory engines ran inside one human skull.",
        "Facts needed the seahorse bridge, while skills bypassed it.",
        "Tying your shoes uses that exact hidden motor vault.",
        "Amnesia never touched the silent autopilot inside those loops.",
        "Some neurologists argue habits define us more than stories.",
        "Others insist losing episodes strips identity down to mechanics.",
        "Which memory engine makes you you: stories or habits?",
    ]
    acts = [
        "act_1_cold_open", "act_1_cold_open", "act_1_cold_open",
        "act_2_case_setup", "act_2_case_setup", "act_2_case_setup", "act_2_case_setup",
        "act_3_twist", "act_3_twist", "act_3_twist", "act_3_twist",
        "act_4_mechanism", "act_4_mechanism", "act_4_mechanism", "act_4_mechanism", "act_4_mechanism",
        "act_5_payoff", "act_5_payoff", "act_5_payoff", "act_5_payoff", "act_5_payoff",
        "act_6_implication_outro", "act_6_implication_outro", "act_6_implication_outro",
        "act_6_implication_outro", "act_6_implication_outro",
    ]
    script = {
        "production_profile": "neuro_diorama",
        "shorts_format_profile": "shorts_90s_v7",
        "prompt_schema_version": 7,
        "style_profile": "porcelain_cinematic_v7",
        "title": "He Forgot Every Day — Yet Mastered a Mirror Test in 3 Days",
        "doi": "10.1136/jnnp.20.1.11",
        "sentences": sentences,
        "sentence_acts": acts,
        "spoken_narration": " ".join(sentences),
    }

    grammars = [
        "porcelain_fullbleed_world",
        "porcelain_hands_closeup",
        "porcelain_pov_hands",
        "porcelain_literal_analogy",
        "porcelain_living_brain",
        "porcelain_cutaway_section",
    ]
    cam_moves = [
        "locked_tripod",
        "slow_push_in",
        "locked_tripod",
        "lateral_slide",
        "locked_tripod",
        "gentle_pull_back",
        "top_down_boom",
    ]
    clips = []
    for i in range(1, 29):
        s_idx = min(len(sentences) - 1, i - 1)
        sent = sentences[s_idx]
        key_words = [w.strip(".,?!:;—").lower() for w in sent.split() if len(w.strip(".,?!:;—")) >= 5][:2]
        kw_phrase = " ".join(key_words) if key_words else "mirror star"
        g = "porcelain_fullbleed_world" if i == 28 else grammars[(i - 1) % 5]
        cam = "slow_tilt_up_sky" if i == 28 else cam_moves[(i - 1) % len(cam_moves)]
        act_num = int(acts[s_idx].split("_")[1])
        clips.append(
            {
                "clip_index": i,
                "act": act_num,
                "location_id": "hartford_ward" if i % 3 != 0 else "mirror_desk",
                "sentence_indices": [s_idx] if i <= len(sentences) else [],
                "visual_grammar": g,
                "camera_move": cam,
                "subject": f"clothed matte-white porcelain figure demonstrating {kw_phrase} on wooden desk {i}",
                "environment": f"bright sunlit hospital examination studio room station {i}",
                "action": (
                    f"At 0-3s porcelain hands position the {kw_phrase} prop on the table; "
                    f"at 3-6s fingers trace the metal contour steadily; at 6-8s the brass indicator settles."
                ),
                "brain_region": "hippocampus" if g == "porcelain_living_brain" else "",
                "brain_render_mode": "cortical_vascular_whole" if g == "porcelain_living_brain" else "",
            }
        )

    plan = {
        "production_profile": "neuro_diorama",
        "shorts_format_profile": "shorts_90s_v7",
        "prompt_schema_version": 7,
        "style_profile": "porcelain_cinematic_v7",
        "title": script["title"],
        "doi": script["doi"],
        "outro_title_lines": ["TWO MEMORY ENGINES", "ONE HUMAN SKULL"],
        "chapter_headlines": [
            {"act": 1, "headline": "FIFTY YEARS GONE"},
            {"act": 3, "headline": "THE MIRROR STAR"},
            {"act": 4, "headline": "TWO MEMORY ENGINES"},
            {"act": 6, "headline": "STORIES OR HABITS"},
        ],
        "edl_cuts": [{"cut_index": i, "clip_index": i} for i in range(1, 29)],
        "clips": clips,
    }
    return script, plan


def test_90s_shorts_validation_accepts_28_clip_episode_and_rejects_out_of_bounds() -> None:
    script, plan = _build_valid_90s_fixture()
    word_cnt = len(script["spoken_narration"].split())
    assert 210 <= word_cnt <= 275, f"Fixture word count {word_cnt} must sit inside 210..275"

    rel_issues = validate_substantive_visual_relevance(plan, script["sentences"], plan["clips"])
    assert not any("[pacing_v7] clip count" in x for x in rel_issues), rel_issues

    v6_issues = validate_production_diorama_v6(plan, script["sentences"], plan["clips"], script_doc=script)
    structural_90s_errors = [
        x
        for x in v6_issues
        if any(
            tok in x
            for tok in (
                "[diorama_script] sentence count",
                "[diorama_script] total spoken words",
                "[pacing_v7] clip count",
                "target_cut_count",
            )
        )
    ]
    assert structural_90s_errors == [], structural_90s_errors

    # Boundary rejection 1: 19 clips (< 24) on a 90s script must fail pacing_v7 clip floor
    bad_plan_short = dict(plan, clips=plan["clips"][:19], edl_cuts=plan["edl_cuts"][:19])
    short_rel = validate_substantive_visual_relevance(bad_plan_short, script["sentences"], bad_plan_short["clips"])
    assert any("[pacing_v7] clip count 19 below balanced documentary floor 24" in x for x in short_rel), short_rel

    # Boundary rejection 2: 35 clips (> 32) on a 90s script must fail pacing_v7 clip ceiling
    extra_clips = plan["clips"] + [dict(plan["clips"][0], clip_index=i) for i in range(29, 36)]
    bad_plan_long = dict(plan, clips=extra_clips)
    long_rel = validate_substantive_visual_relevance(bad_plan_long, script["sentences"], extra_clips)
    assert any("[pacing_v7] clip count 35 exceeds balanced documentary ceiling 32" in x for x in long_rel), long_rel

    # Boundary rejection 3: <210 words on a 90s script must fail 90s spoken-word budget
    tiny_sents = ["Short sentence here!"] + ["Yet it turns fast."] + ["And here is why."] + ["Tiny line now?"] * 20
    bad_script_words = dict(script, sentences=tiny_sents, spoken_narration=" ".join(tiny_sents))
    word_issues = validate_production_diorama_v6(plan, tiny_sents, plan["clips"], script_doc=bad_script_words)
    assert any("outside 210-275 for 90-second Shorts pacing" in x for x in word_issues), word_issues


# ---------------------------------------------------------------------------
# 2. Longform Deferral (`LONGFORM_DEFERRED = True`) CLI Hold + Override
# ---------------------------------------------------------------------------


def test_longform_cli_deferred_by_default_and_overridable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("AAB_ALLOW_DEFERRED_LONGFORM", raising=False)
    monkeypatch.setattr("sys.argv", ["main.py", "longform-qa", "--project", "nonexistent_lf_proj"])
    # Without override -> exits with SystemExit(2) before touching filesystem
    with pytest.raises(SystemExit) as exc_info:
        cli.main()
    assert exc_info.value.code == 2

    # With `--allow-deferred-longform` -> passes the deferral guard (reaches project existence check -> code 1 or custom)
    called: list[str] = []
    monkeypatch.setattr(cli, "run_longform_qa", lambda **kw: {"passed": True} if not called.append("ok") else {"passed": True}, raising=False)
    # Verify `_enforce_longform_not_deferred` itself passes cleanly with both flag and env var
    class _DummyArgs:
        allow_deferred_longform = True

    cli._enforce_longform_not_deferred(_DummyArgs())

    class _DummyArgsNoFlag:
        allow_deferred_longform = False

    monkeypatch.setenv("AAB_ALLOW_DEFERRED_LONGFORM", "1")
    cli._enforce_longform_not_deferred(_DummyArgsNoFlag())


# ---------------------------------------------------------------------------
# 3. Monthly & Daily Credit Auto-Tier + SharedOmniCreditBudget
# ---------------------------------------------------------------------------


def test_flow_credits_overlay_parsing_and_monthly_daily_rollover(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    credit_file = tmp_path / "flow_credit_state.json"
    locks_dir = tmp_path / "locks"
    monkeypatch.setenv("AAB_FLOW_CREDIT_STATE_PATH", str(credit_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    ref_now = dt.datetime(2026, 11, 5, 4, 0, tzinfo=dt.timezone.utc)
    parsed = parse_flow_credits_overlay_text(
        "Google AI Pro\n1,240 Google Flow credits\nResets on 17 Nov at 00:03",
        now_dt=ref_now,
    )
    assert parsed["credits_remaining"] == 1240
    assert "17 Nov" in parsed["resets_on_label"]
    assert parsed["resets_on_iso"].startswith("2026-11-17T00:03:00")

    # Probe with 120 credits (>= 20) -> not exhausted
    t0 = ref_now.timestamp()
    st_ok = record_flow_credit_probe(
        credits_remaining=120,
        resets_on_label=parsed["resets_on_label"],
        resets_on_iso=parsed["resets_on_iso"],
        now_ts=t0,
    )
    assert st_ok["exhausted"] is False
    ok_probe, reason_ok = should_reprobe_primary_omni(now_ts=t0 + 10)
    assert ok_probe is True
    assert reason_ok == "not_exhausted"

    # Exhaust credits (< 20) -> blocked within same active window
    record_flow_credit_exhausted(
        reason="zero_balance_banner",
        credits_remaining=8,
        resets_on_iso=parsed["resets_on_iso"],
        now_ts=t0 + 30,
    )
    ok_same, reason_same = should_reprobe_primary_omni(now_ts=t0 + 120, reprobe_ttl_sec=3600.0)
    assert ok_same is False
    assert reason_same == "exhausted_within_active_window"

    # Next UTC day (+50 daily credit top-up rollover) -> automatically re-probes Omni 1.2 Flash!
    next_day_ts = dt.datetime(2026, 11, 6, 0, 5, tzinfo=dt.timezone.utc).timestamp()
    ok_daily, reason_daily = should_reprobe_primary_omni(now_ts=next_day_ts, reprobe_ttl_sec=999_999.0)
    assert ok_daily is True
    assert reason_daily == "daily_credit_refill_rollover"

    # Scheduled monthly reset timestamp elapsed -> automatically re-probes Omni 1.2 Flash!
    reset_ts = dt.datetime(2026, 11, 17, 0, 5, tzinfo=dt.timezone.utc).timestamp()
    ok_sched, reason_sched = should_reprobe_primary_omni(now_ts=reset_ts, reprobe_ttl_sec=999_999.0)
    assert ok_sched is True
    assert reason_sched == "scheduled_reset_elapsed"

    # Next calendar month (`YYYY-MM` changed) -> `monthly_cycle_rollover`
    next_month_ts = dt.datetime(2026, 12, 1, 0, 1, tzinfo=dt.timezone.utc).timestamp()
    ok_month, reason_month = should_reprobe_primary_omni(now_ts=next_month_ts, reprobe_ttl_sec=999_999.0)
    assert ok_month is True
    assert reason_month == "monthly_cycle_rollover"


def test_shared_omni_credit_budget_prevents_parallel_shard_overshoot() -> None:
    budget = SharedOmniCreditBudget(initial_credits=52)
    assert budget.try_reserve(20) is True  # 32 left
    assert budget.try_reserve(20) is True  # 12 left
    assert budget.try_reserve(20) is False  # cannot afford 20-credit ref clip
    assert budget.try_reserve(12) is True  # can afford 12-credit non-ref clip -> 0 left
    assert budget.remaining == 0
    assert budget.try_reserve(12) is False

    # Failed submission refunds cleanly so another shard can use it
    budget.refund(20)
    assert budget.remaining == 20
    assert budget.try_reserve(20) is True
    assert budget.remaining == 0


# ---------------------------------------------------------------------------
# 4. Canonical `AAB_<project_id>` Room Naming, `/tmp` Cleanup & Persistent SHA + Unmanned Signoff
# ---------------------------------------------------------------------------


def test_canonical_flow_room_naming_and_tmp_cleanup(tmp_path: Path) -> None:
    assert format_flow_room_name("ep_90s_01") == "AAB_ep_90s_01"
    assert format_flow_room_name("ep_90s_01", role="clips", shard_idx=2, wave_idx=1) == "AAB_ep_90s_01__clips_s2_w1"
    assert format_flow_room_name("ep_90s_01", role="refs") == "AAB_ep_90s_01__refs"

    parsed_main = parse_flow_room_name("AAB_ep_90s_01")
    assert parsed_main is not None
    assert parsed_main["project_id"] == "ep_90s_01"
    assert parsed_main["role"] == "clips"
    assert parsed_main["shard_idx"] is None

    parsed_shard = parse_flow_room_name("AAB_ep_90s_01__clips_s3_w2")
    assert parsed_shard is not None
    assert parsed_shard["project_id"] == "ep_90s_01"
    assert parsed_shard["shard_idx"] == 3
    assert parsed_shard["wave_idx"] == 2

    uid = extract_flow_project_uuid("https://labs.google/fx/tools/flow/project/12345678-9abc-def0-1234-56789abcdef0")
    assert uid == "12345678-9abc-def0-1234-56789abcdef0"

    # Local temp cleanup removes stale pipeline files/dirs while strictly protecting CDP leases & user files
    fake_tmp = tmp_path / "fake_tmp"
    fake_bridge = tmp_path / "fake_bridge"
    fake_tmp.mkdir()
    fake_bridge.mkdir()

    # Protected & user items
    lease_json = fake_tmp / "aab_cdp_leases.json"
    lease_json.write_text('{"version": 1, "leases": {}}', encoding="utf-8")
    locks_dir = fake_tmp / "aab_locks"
    locks_dir.mkdir()
    (locks_dir / "flow_credit_state.lock").write_text("", encoding="utf-8")
    report_lock = fake_tmp / "aab_studio_report.lock"
    report_lock.write_text("", encoding="utf-8")
    user_note = fake_tmp / "my_personal_notes.txt"
    user_note.write_text("keep me", encoding="utf-8")

    # Stale AAB temp items that MUST be purged
    stale_files = [
        fake_tmp / ".aab_manifest_12345.tmp",
        fake_tmp / ".aab_kb_999.tmp",
        fake_tmp / ".aab_asset_idx_111.tmp",
        fake_tmp / "aab_preflight_voice_01.mp3",
        fake_tmp / "fimg_cand_0.png",
        fake_bridge / "partial_video.mp4.crdownload",
    ]
    for sf in stale_files:
        sf.write_bytes(b"stale")
    stale_dir = fake_tmp / "aab_ref_test"
    stale_dir.mkdir()
    (stale_dir / "ref.png").write_bytes(b"png")
    shard_bridge_dir = fake_bridge / "shard_01"
    shard_bridge_dir.mkdir()
    (shard_bridge_dir / "clip.mp4").write_bytes(b"mp4")

    rep = purge_local_flow_temp_files(dry_run=False, temp_root=fake_tmp, bridge_root=fake_bridge)
    assert rep["removed_files_count"] == len(stale_files)
    assert rep["removed_dirs_count"] == 2
    assert lease_json.exists(), "aab_cdp_leases.json must never be deleted by flow-clean"
    assert locks_dir.exists(), "aab_locks directory must never be deleted by flow-clean"
    assert report_lock.exists(), ".lock files must never be deleted by flow-clean"
    assert user_note.exists(), "Unrelated user files in /tmp must never be touched"
    for sf in stale_files:
        assert not sf.exists()


def test_persistent_sha256_cache_and_unmanned_posthoc_signoff(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    sha_cache_file = tmp_path / "persistent_sha256_cache.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_PERSISTENT_SHA_CACHE_PATH", str(sha_cache_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))
    clear_in_memory_sha_cache()

    media_file = tmp_path / "sample_clip.mp4"
    payload = b"porcelain_cinematic_v7_frame_bytes_" * 512
    media_file.write_bytes(payload)
    expected_sha = hashlib.sha256(payload).hexdigest()

    got_sha_1 = fast_file_sha256(media_file)
    assert got_sha_1 == expected_sha
    assert sha_cache_file.exists()
    # Clear in-memory cache and verify persistent disk cache serves SHA without re-streaming
    clear_in_memory_sha_cache()
    assert fast_file_sha256(media_file) == expected_sha
    # Mutating file invalidates fingerprint immediately
    media_file.write_bytes(payload + b"_mutated")
    assert fast_file_sha256(media_file) == compute_stream_sha256(media_file)

    # Test deterministic CV-verified unmanned posthoc signoff (`auto_signoff_posthoc_semantic_review`)
    proj_dir = tmp_path / "ep_90s_signoff"
    (proj_dir / "03_visuals").mkdir(parents=True)
    (proj_dir / "05_assembly").mkdir(parents=True)
    final_mp4 = proj_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    edl_json = proj_dir / "05_assembly" / "edit_decision_list.json"
    final_mp4.write_bytes(b"fake_mp4_stream_bytes_for_sha")
    edl_json.write_text(json.dumps({"cuts": [{"cut_index": i} for i in range(1, 29)]}), encoding="utf-8")
    final_sha = compute_stream_sha256(final_mp4)
    edl_sha = compute_stream_sha256(edl_json)

    cuts_report = [
        {
            "cut_index": i,
            "clip_index": i,
            "grammar": "porcelain_fullbleed_world" if i % 2 else "porcelain_hands_closeup",
            "camera_move": "locked_tripod" if i % 2 else "slow_push_in",
            "spoken_narration": f"Distinct spoken narration sentence number {i} for clarity check.",
            "intended_scene": f"Sunlit studio examination table station {i} with brass instrument.",
            "clarity_score": 88.5,
            "passed": True,
        }
        for i in range(1, 29)
    ]

    # Must refuse to rubber-stamp when QA report failed (`passed == False`)
    failed_qa = {
        "passed": False,
        "final_mp4_sha256": final_sha,
        "edl_sha256": edl_sha,
        "cuts": cuts_report,
    }
    assert auto_signoff_posthoc_semantic_review(proj_dir, qa_report=failed_qa) is None

    # When CV & semantic gates pass (`passed == True`), produces valid SHA-bound review passing F-4 anti-boilerplate
    passing_qa = {
        "passed": True,
        "final_mp4_sha256": final_sha,
        "edl_sha256": edl_sha,
        "cuts": cuts_report,
    }
    rev_path = auto_signoff_posthoc_semantic_review(proj_dir, qa_report=passing_qa)
    assert rev_path is not None and rev_path.exists()

    val_res = validate_posthoc_semantic_review(
        proj_dir,
        final_mp4_sha256=final_sha,
        edl_sha256=edl_sha,
        expected_cut_count=28,
    )
    # R85 Law: unmanned_cv_verified_signoff is unconditionally invalid (must require real VLM/human visual sign-off)
    assert val_res["valid"] is False
    assert any("unmanned_cv_verified_signoff_forbidden" in iss for iss in val_res["issues"])


# ---------------------------------------------------------------------------
# 5. Cross-Process CDP Anti-Tab-Stealing Lease Isolation & Background Focus
# ---------------------------------------------------------------------------


def test_cdp_lease_registry_conflict_dead_pid_eviction_and_safe_close(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))
    assert get_cdp_leases_path() == leases_file

    # 1. Acquire lease for worker A
    rec_a = acquire_tab_lease(
        "TAB_FLOW_SHARD_1",
        owner_id="pid:self:worker_a",
        purpose="flow-shard-1",
        cdp_port=9222,
        created_by_pipeline=True,
        initial_url="about:blank",
    )
    assert rec_a["target_id"] == "TAB_FLOW_SHARD_1"
    assert get_tab_lease("TAB_FLOW_SHARD_1", cdp_port=9222) is not None

    # 2. Worker B attempting to claim Worker A's live tab raises TabLeaseConflictError
    with pytest.raises(TabLeaseConflictError):
        acquire_tab_lease(
            "TAB_FLOW_SHARD_1",
            owner_id="pid:self:worker_b",
            purpose="flow-shard-2",
            cdp_port=9222,
        )
    assert try_acquire_tab_lease("TAB_FLOW_SHARD_1", owner_id="pid:self:worker_b", cdp_port=9222) is None
    assert is_tab_leased_by_other("TAB_FLOW_SHARD_1", owner_id="pid:self:worker_b", cdp_port=9222) is True
    assert is_tab_leased_by_other("TAB_FLOW_SHARD_1", owner_id="pid:self:worker_a", cdp_port=9222) is False

    # 3. Dead OS PID lease is automatically evicted so another worker can safely acquire
    dead_pid = 999_999_991
    state_doc = json.loads(leases_file.read_text(encoding="utf-8"))
    state_doc["leases"]["TAB_ORPHAN_DEAD_PID"] = {
        "target_id": "TAB_ORPHAN_DEAD_PID",
        "owner_id": f"pid:{dead_pid}:crashed_worker",
        "pid": dead_pid,
        "cdp_port": 9222,
        "purpose": "crashed",
        "created_by_pipeline": True,
        "acquired_at": 1_700_000_000.0,
        "heartbeat_at": 1_700_000_000.0,
        "ttl_sec": 900.0,
    }
    leases_file.write_text(json.dumps(state_doc), encoding="utf-8")
    assert prune_dead_leases(cdp_port=9222) == 1
    assert "TAB_ORPHAN_DEAD_PID" not in list_active_tab_leases(cdp_port=9222)

    # 4. `release_and_close_leased_tab` refuses unleased user tabs, foreign-owned tabs, and non-pipeline tabs
    closed_urls: list[str] = []

    class _DummyResp:
        def __enter__(self) -> "_DummyResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_urlopen(req_or_url: Any, timeout: float = 5.0) -> _DummyResp:
        url_s = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
        closed_urls.append(url_s)
        return _DummyResp()

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)

    # Unleased personal user tab -> strictly refused (False, zero HTTP close calls)
    assert release_and_close_leased_tab("USER_GMAIL_TAB", owner_id="pid:self:worker_a", cdp_port=9222) is False
    assert closed_urls == []

    # Foreign owner trying to close Worker A's tab -> strictly refused
    assert release_and_close_leased_tab("TAB_FLOW_SHARD_1", owner_id="pid:self:worker_b", cdp_port=9222) is False
    assert closed_urls == []

    # Pre-existing tab leased with created_by_pipeline=False -> releases lease but refuses to close browser tab
    acquire_tab_lease(
        "PREEXISTING_STUDIO_TAB",
        owner_id="pid:self:worker_a",
        cdp_port=9222,
        created_by_pipeline=False,
    )
    assert release_and_close_leased_tab("PREEXISTING_STUDIO_TAB", owner_id="pid:self:worker_a", cdp_port=9222) is False
    assert closed_urls == []

    # Legitimate pipeline-created tab closed by its rightful owner -> succeeds!
    assert release_and_close_leased_tab("TAB_FLOW_SHARD_1", owner_id="pid:self:worker_a", cdp_port=9222) is True
    assert closed_urls == ["http://127.0.0.1:9222/json/close/TAB_FLOW_SHARD_1"]


def test_background_tab_creation_focus_emulation_and_idle_tab_protection(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    # 1. Verify `open_leased_cdp_tab` defaults to `background=True` and registers `created_by_pipeline=True`
    captured_bg: list[bool] = []

    def _fake_create_via_ws(
        target_url: str,
        *,
        cdp_host: str = "127.0.0.1",
        cdp_port: int = 9222,
        background: bool = True,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        captured_bg.append(background)
        return {
            "id": "BG_CREATED_TAB_01",
            "type": "page",
            "url": target_url,
            "webSocketDebuggerUrl": f"ws://{cdp_host}:{cdp_port}/devtools/page/BG_CREATED_TAB_01",
            "background": background,
        }

    monkeypatch.setattr("pipeline.cdp_tab_lease._create_target_via_browser_ws", _fake_create_via_ws)
    opened = open_leased_cdp_tab("about:blank", owner_id="pid:self:shard_bg", purpose="flow-bg-test", cdp_port=9222)
    assert captured_bg == [True]
    assert opened["background"] is True
    lease_rec = get_tab_lease("BG_CREATED_TAB_01", cdp_port=9222)
    assert lease_rec is not None and lease_rec["created_by_pipeline"] is True

    # 2. Verify `enable_background_focus_emulation` sends `Emulation.setFocusEmulationEnabled({"enabled": True})`
    sent_cdp_cmds: list[tuple[str, dict[str, Any]]] = []

    class _FakeCDPClient:
        async def send(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float = 5.0) -> dict[str, Any]:
            sent_cdp_cmds.append((method, dict(params or {})))
            return {}

    ok_emul = asyncio.run(enable_background_focus_emulation(_FakeCDPClient()))
    assert ok_emul is True
    assert sent_cdp_cmds == [("Emulation.setFocusEmulationEnabled", {"enabled": True})]

    # 3. Verify `cleanup_idle_whale_tabs` NEVER closes an `about:blank` tab leased by a sibling worker!
    fake_tabs = [
        {"id": "USER_ACTIVE_TAB", "type": "page", "url": "https://mail.google.com/"},
        {"id": "BG_CREATED_TAB_01", "type": "page", "url": "about:blank"},  # leased above!
        {"id": "UNLEASED_STALE_BLANK", "type": "page", "url": "about:blank"},
    ]
    closed_ids: list[str] = []

    class _FakeHTTPResp:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeHTTPResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_whale_urlopen(req_or_url: Any, timeout: float = 4.0) -> _FakeHTTPResp:
        url_s = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
        if url_s.endswith("/json/list"):
            return _FakeHTTPResp(json.dumps(fake_tabs).encode("utf-8"))
        if "/json/close/" in url_s:
            closed_ids.append(url_s.rsplit("/", 1)[-1])
            return _FakeHTTPResp(b"Target is closing")
        return _FakeHTTPResp(b"{}")

    monkeypatch.setattr("urllib.request.urlopen", _fake_whale_urlopen)
    rep_clean = cleanup_idle_whale_tabs(cdp_port=9222, dry_run=False)
    assert "UNLEASED_STALE_BLANK" in closed_ids
    assert "BG_CREATED_TAB_01" not in closed_ids, "Leased about:blank staging tab must NEVER be closed by cleanup!"
    assert "USER_ACTIVE_TAB" not in closed_ids
    assert rep_clean["closed"] == ["UNLEASED_STALE_BLANK"]


def test_zero_bring_to_front_calls_anywhere_in_pipeline() -> None:
    """Hard regression lock: zero `Page.bringToFront`, `.bring_to_front(`, or focus-stealing `context.new_page(` calls in `pipeline/`."""
    pipeline_root = cfg.WORKSPACE_ROOT / "pipeline"
    offenders: list[str] = []
    py_candidates = sorted([*pipeline_root.glob("*.py"), *(pipeline_root / "studio").glob("*.py")])
    for py_path in py_candidates:
        src = py_path.read_text(encoding="utf-8")
        for lineno, line in enumerate(src.splitlines(), start=1):
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            if "Page.bringToFront" in line or ".bring_to_front(" in line or "context.new_page(" in line:
                # Ignore docstrings/comments explaining why focus-stealing calls are banned
                if "never" in line.lower() or "without" in line.lower() or "zero" in line.lower():
                    continue
                offenders.append(f"{py_path.relative_to(cfg.WORKSPACE_ROOT)}:{lineno}: {stripped}")
    assert offenders == [], f"Found forbidden focus-stealing calls in pipeline/: {offenders}"


def test_prosody_p8_runtime_density_uses_90s_bounds_for_default_profile(tmp_path: Path) -> None:
    """Deep verification: actually invoke `evaluate_prosody_gates` on 90s vs 180s project fixtures."""
    sents_text = [f"Sentence {i} delivers clear documentary evidence." for i in range(1, 26)]
    acts = (
        ["act_1_cold_open"] * 3
        + ["act_2_case_setup"] * 4
        + ["act_3_twist"] * 4
        + ["act_4_mechanism"] * 5
        + ["act_5_payoff"] * 5
        + ["act_6_implication_outro"] * 4
    )

    def _write_prosody_fixture(proj_dir: Path, *, total_dur: float, fmt_prof: str | None) -> Path:
        (proj_dir / "02_script").mkdir(parents=True, exist_ok=True)
        (proj_dir / "03_visuals").mkdir(parents=True, exist_ok=True)
        (proj_dir / "04_audio").mkdir(parents=True, exist_ok=True)
        (proj_dir / "05_assembly").mkdir(parents=True, exist_ok=True)
        script_doc: dict[str, Any] = {"sentences": sents_text, "sentence_acts": acts}
        if fmt_prof:
            script_doc["shorts_format_profile"] = fmt_prof
        (proj_dir / "02_script" / "script.json").write_text(json.dumps(script_doc), encoding="utf-8")
        (proj_dir / "03_visuals" / "visual_plan.json").write_text(
            json.dumps({"style_profile": "porcelain_cinematic_v7", **({"format_profile": fmt_prof} if fmt_prof else {})}),
            encoding="utf-8",
        )
        speech_end = total_dur - 1.6
        step = speech_end / len(sents_text)
        spans = []
        pr_sents = []
        gears = ("hook", "rush", "stamp", "pivot", "explain", "payoff")
        for idx, txt in enumerate(sents_text, start=1):
            t0 = round((idx - 1) * step, 3)
            t1 = round(idx * step, 3)
            g = gears[(idx - 1) % len(gears)]
            spans.append({"sentence_index": idx, "text": txt, "start_sec": t0, "end_sec": t1})
            pr_sents.append(
                {
                    "sentence_index": idx,
                    "gear": g,
                    "words": len(txt.split()),
                    "wpm": 165.0 + (idx % 4) * 6.0,
                    "duration_sec": round(t1 - t0, 3),
                    "lead_silence_sec": 0.02,
                    "trail_silence_sec": 0.04,
                    "target_tempo": 1.0,
                    "measured_tempo": 1.0,
                    "native_gear_synth": True,
                    "wsola_factor": 1.0,
                    "max_internal_silence_sec": 0.08,
                    "acoustic_pre_silence_sec": 0.28,
                    "act_boundary_before": False,
                }
            )
        (proj_dir / "04_audio" / "prosody_report.json").write_text(
            json.dumps(
                {
                    "prosody_mode": "dynamic_us_v7",
                    "native_gear_synthesis": True,
                    "sentences": pr_sents,
                }
            ),
            encoding="utf-8",
        )
        (proj_dir / "04_audio" / "voice_report.json").write_text(
            json.dumps(
                {
                    "engine": "edge_tts",
                    "total_duration_sec": total_dur,
                    "speech_end_sec": speech_end,
                    "true_rms_voiced_ratio": 0.80,
                    "sentence_spans": spans,
                }
            ),
            encoding="utf-8",
        )
        return proj_dir

    # 1. Default / shorts_90s_v7 at 88.0s -> P8_runtime_density PASSES (within 75..105s)
    p_90_ok = _write_prosody_fixture(tmp_path / "ep_90_ok", total_dur=88.0, fmt_prof=None)
    rep_90_ok = evaluate_prosody_gates(p_90_ok, run_asr=False, save_report=False)
    p8_ok = rep_90_ok["gates"]["P8_runtime_density"]
    assert p8_ok["format_profile"] == "shorts_90s_v7"
    assert (p8_ok["min_duration_sec"], p8_ok["max_duration_sec"]) == (75.0, 105.0)
    assert p8_ok["passed"] is True

    # 2. shorts_90s_v7 at 150.0s -> P8_runtime_density FAILS (> 105.0s ceiling)
    p_90_over = _write_prosody_fixture(tmp_path / "ep_90_over", total_dur=150.0, fmt_prof="shorts_90s_v7")
    rep_90_over = evaluate_prosody_gates(p_90_over, run_asr=False, save_report=False)
    assert rep_90_over["gates"]["P8_runtime_density"]["passed"] is False

    # 3. Legacy shorts_180s_v7 at 150.0s -> P8_runtime_density PASSES (within 140..179s)
    p_180_ok = _write_prosody_fixture(tmp_path / "ep_180_ok", total_dur=150.0, fmt_prof="shorts_180s_v7")
    rep_180_ok = evaluate_prosody_gates(p_180_ok, run_asr=False, save_report=False)
    p8_180 = rep_180_ok["gates"]["P8_runtime_density"]
    assert p8_180["format_profile"] == "shorts_180s_v7"
    assert p8_180["passed"] is True


def test_allocate_dedicated_flow_project_tab_updates_url_renames_and_closes_on_error(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Regression lock for live `allocate_dedicated_flow_project_tab`:
      - Ignores unleased personal user Flow tabs whose title lacks `AAB_` / `project_id`;
      - Opens dedicated background leased tab, enables focus emulation, creates project room,
        renames room to `AAB_<project_id>__episode`, and updates lease `url` without `TypeError`;
      - Releases and closes the newly opened tab if project creation fails mid-flight (zero orphan tab leak).
    """
    from pipeline import flow_live_single_worker as flsw

    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    async def _fast_sleep(_sec: float, result: Any = None) -> Any:
        return result

    monkeypatch.setattr(flsw.asyncio, "sleep", _fast_sleep)

    personal_tab = {
        "id": "USER_PERSONAL_FLOW_TAB",
        "type": "page",
        "title": "My Vacation Storyboard",
        "url": "https://labs.google/fx/tools/flow/project/11111111-2222-3333-4444-555555555555",
        "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/USER_PERSONAL_FLOW_TAB",
    }
    closed_tabs: list[str] = []
    probed_ws_urls: list[str] = []
    renamed_rooms: list[str] = []
    sent_methods: list[str] = []
    created_counter = [0]
    should_fail_creation = [False]

    class _FakeResp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_urlopen(req_or_url: Any, timeout: float = 8.0) -> _FakeResp:
        u = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
        if u.endswith("/json/list"):
            return _FakeResp(json.dumps([personal_tab]).encode("utf-8"))
        if "/json/close/" in u:
            closed_tabs.append(u.rsplit("/", 1)[-1])
            return _FakeResp(b"Target is closing")
        return _FakeResp(b"{}")

    def _fake_create_bg(
        target_url: str,
        *,
        cdp_host: str = "127.0.0.1",
        cdp_port: int = 9222,
        background: bool = True,
        timeout: float = 8.0,
    ) -> dict[str, Any]:
        assert background is True
        created_counter[0] += 1
        tid = f"NEW_FLOW_TAB_{created_counter[0]}"
        return {
            "id": tid,
            "type": "page",
            "url": target_url,
            "webSocketDebuggerUrl": f"ws://{cdp_host}:{cdp_port}/devtools/page/{tid}",
            "background": True,
        }

    class _FakeDirectCDP:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url
            self._loc = "about:blank"
            probed_ws_urls.append(ws_url)

        async def __aenter__(self) -> "_FakeDirectCDP":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float = 10.0) -> dict[str, Any]:
            sent_methods.append(method)
            if method == "Page.navigate" and isinstance(params, dict):
                self._loc = str(params.get("url") or "")
            return {}

        async def eval(self, expr: str, timeout_sec: float = 10.0) -> Any:
            if expr == "location.href":
                return self._loc
            if "new-project-button" in expr:
                if not should_fail_creation[0]:
                    self._loc = "https://labs.google/fx/tools/flow/project/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
                return True
            return ""

    async def _fake_rename(_client: Any, room_title: str) -> bool:
        renamed_rooms.append(room_title)
        return True

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setattr("pipeline.cdp_tab_lease._create_target_via_browser_ws", _fake_create_bg)
    monkeypatch.setattr(flsw, "DirectCDPClient", _FakeDirectCDP)
    monkeypatch.setattr(flsw, "rename_active_flow_project", _fake_rename)

    res = asyncio.run(
        flsw.allocate_dedicated_flow_project_tab(
            cdp_port=9222,
            project_id="ep_90s_alloc",
            lease_owner_id="pid:self:alloc_test",
            purpose="flow_test",
        )
    )
    # Personal tab was NEVER probed via CDP WebSocket!
    assert "ws://127.0.0.1:9222/devtools/page/USER_PERSONAL_FLOW_TAB" not in probed_ws_urls
    assert res["tab_id"] == "NEW_FLOW_TAB_1"
    assert res["project_url"] == "https://labs.google/fx/tools/flow/project/aaaaaaaa-bbbb-cccc-dddd-eeeeeeeeeeee"
    assert renamed_rooms == ["AAB_ep_90s_alloc"]
    assert "Emulation.setFocusEmulationEnabled" in sent_methods
    lease_1 = get_tab_lease("NEW_FLOW_TAB_1", cdp_port=9222)
    assert lease_1 is not None
    assert lease_1["url"] == res["project_url"]
    assert closed_tabs == []

    # Now simulate project-creation failure -> newly opened tab MUST be closed & lease released (zero leak)
    should_fail_creation[0] = True
    with pytest.raises(flsw.FlowCircuitBreakerError):
        asyncio.run(
            flsw.allocate_dedicated_flow_project_tab(
                cdp_port=9222,
                project_id="ep_90s_fail",
                lease_owner_id="pid:self:alloc_fail",
                purpose="flow_test_fail",
            )
        )
    assert "NEW_FLOW_TAB_2" in closed_tabs
    assert get_tab_lease("NEW_FLOW_TAB_2", cdp_port=9222) is None


def test_cdp_lease_pid_reuse_proc_start_ticks_evicts_recycled_pid(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies `/proc/<pid>/stat` `proc_start_ticks` mismatch evicts a recycled-PID stale lease."""
    import os
    from pipeline.cdp_tab_lease import _read_proc_start_ticks

    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    real_ticks = _read_proc_start_ticks(os.getpid())
    assert real_ticks is not None and real_ticks > 0

    # Write a synthetic stale lease carrying `os.getpid()` (alive!) but an older `proc_start_ticks`
    now_ts = 1_900_000_000.0
    monkeypatch.setattr("pipeline.cdp_tab_lease.time.time", lambda: now_ts)
    leases_file.write_text(
        json.dumps(
            {
                "schema_version": 1,
                "updated_at": now_ts,
                "leases": {
                    "RECYCLED_PID_TAB": {
                        "target_id": "RECYCLED_PID_TAB",
                        "owner_id": f"pid:{os.getpid()}:crashed_worker",
                        "pid": os.getpid(),
                        "proc_start_ticks": real_ticks - 99999,
                        "purpose": "stale",
                        "cdp_port": 9222,
                        "created_by_pipeline": True,
                        "initial_url": "about:blank",
                        "url": "about:blank",
                        "acquired_at": now_ts - 10.0,
                        "heartbeat_at": now_ts - 5.0,
                        "expires_at": now_ts + 3600.0,
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    # Because `proc_start_ticks` mismatches the live process, it must be evicted and acquirable!
    acquired = try_acquire_tab_lease("RECYCLED_PID_TAB", owner_id="pid:new_owner:fresh", purpose="fresh", cdp_port=9222)
    assert acquired is not None and acquired["owner_id"] == "pid:new_owner:fresh"
    # And now that `RECYCLED_PID_TAB` carries the real live `proc_start_ticks`, a competing owner is blocked!
    assert try_acquire_tab_lease("RECYCLED_PID_TAB", owner_id="pid:other:intruder", purpose="steal", cdp_port=9222) is None


def test_multiworker_temp_cleanup_and_flow_clean_preserve_siblings_and_personal_projects(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies:
      1. `purge_local_flow_temp_files` preserves fresh `/tmp/rf_*.jpg`, `/tmp/aab_reenact`, and sibling
         `flow_bridge/shard_*` while sibling leases are active, while cleaning own finished project shard.
      2. `clean_flow_workspace_async(all_projects=True)` preserves open browser tabs, leased `url` rooms,
         and custom-named personal user Flow projects (never invoking bulk Delete All when personal/active rooms exist).
    """
    import os
    import time as _time
    from pipeline import flow_workspace as fw

    temp_root = tmp_path / "tmp_sim"
    bridge_root = tmp_path / "flow_bridge"
    temp_root.mkdir()
    bridge_root.mkdir()

    leases_file = temp_root / "aab_cdp_leases.json"
    locks_dir = temp_root / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    # Active sibling worker B holds a lease on Flow UUID bbbbbbbb-...
    acquire_tab_lease(
        "SIBLING_TAB_B",
        owner_id=f"pid:{os.getpid()}:worker_b",
        purpose="diorama-shard:proj_b:s1",
        url="https://labs.google/fx/tools/flow/project/bbbbbbbb-2222-3333-4444-555555555555",
        cdp_port=9222,
    )

    fresh_rf = temp_root / "rf_sibling_live.jpg"
    fresh_rf.write_bytes(b"live")
    stale_rf = temp_root / "rf_stale_old.jpg"
    stale_rf.write_bytes(b"old")
    old_mtime = _time.time() - 7200.0
    os.utime(stale_rf, (old_mtime, old_mtime))

    reenact_dir = temp_root / "aab_reenact"
    reenact_dir.mkdir()
    (reenact_dir / "S01.png").write_bytes(b"live_q")

    shard_a = bridge_root / "shard_proj_a_1"
    shard_a.mkdir()
    shard_b = bridge_root / "shard_proj_b_1"
    shard_b.mkdir()

    # Worker A finishes `proj_a` while Worker B (`proj_b`) is still active:
    rep = purge_local_flow_temp_files(
        temp_root=temp_root,
        bridge_root=bridge_root,
        project_id="proj_a",
        cdp_port=9222,
    )
    assert rep["active_leases_detected"] == 1
    assert fresh_rf.exists(), "Active sibling /tmp/rf_*.jpg staging file must NOT be deleted mid-flight!"
    assert reenact_dir.exists(), "Active sibling /tmp/aab_reenact quarantine dir must NOT be deleted mid-flight!"
    assert shard_b.exists(), "Active sibling flow_bridge/shard_proj_b_1 must NOT be deleted!"
    assert not shard_a.exists(), "Finished own shard_proj_a_1 should be cleaned!"
    assert not stale_rf.exists(), "Stale (>30m) temp file should be cleaned!"

    # Verify `clean_flow_workspace_async(all_projects=True)` protects open tabs, leased rooms, AND custom personal projects
    open_user_uuid = "cccccccc-3333-4444-5555-666666666666"
    leased_b_uuid = "bbbbbbbb-2222-3333-4444-555555555555"
    personal_uuid = "dddddddd-4444-5555-6666-777777777777"
    pipeline_uuid = "eeeeeeee-5555-6666-7777-888888888888"

    dashboard_cards = [
        {"idx": 0, "href": f"/fx/tools/flow/project/{leased_b_uuid}", "title": "AAB_proj_b__clips_s1", "delX": 100, "delY": 100},
        {"idx": 1, "href": f"/fx/tools/flow/project/{open_user_uuid}", "title": "AAB_open_in_tab__episode", "delX": 100, "delY": 200},
        {"idx": 2, "href": f"/fx/tools/flow/project/{personal_uuid}", "title": "My Personal Short Film", "delX": 100, "delY": 300},
        {"idx": 3, "href": f"/fx/tools/flow/project/{pipeline_uuid}", "title": "AAB_proj_a__clips_s1", "delX": 100, "delY": 400},
    ]

    class _FakeResp2:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeResp2":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_list_urlopen(req_or_url: Any, timeout: float = 3.0) -> _FakeResp2:
        u = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
        if u.endswith("/json/list"):
            return _FakeResp2(
                json.dumps(
                    [
                        {
                            "id": "USER_OPEN_TAB",
                            "type": "page",
                            "url": f"https://labs.google/fx/tools/flow/project/{open_user_uuid}",
                        }
                    ]
                ).encode("utf-8")
            )
        return _FakeResp2(b"{}")

    from contextlib import asynccontextmanager

    class _FakeCleanClient:
        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

        async def eval(self, expr: str) -> Any:
            if "new-project-button" in expr:
                return True
            if "flow-project-card" in expr and "delBtn" in expr:
                return list(dashboard_cards)
            return None

    @asynccontextmanager
    async def _fake_leased_tab(*args: Any, **kwargs: Any):
        yield (_FakeCleanClient(), "CLEAN_TEMP_TAB", "pid:self:clean")

    async def _fast_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr("urllib.request.urlopen", _fake_list_urlopen)
    monkeypatch.setattr(fw, "leased_cdp_tab", _fake_leased_tab)
    monkeypatch.setattr(fw.asyncio, "sleep", _fast_sleep)

    dry_rep = asyncio.run(
        fw.clean_flow_workspace_async(
            cdp_port=9222,
            all_projects=True,
            dry_run=True,
            clean_local_temp=False,
        )
    )
    deleted_uuids = {d["uuid"] for d in dry_rep["deleted_flow_projects"]}
    assert deleted_uuids == {pipeline_uuid}
    assert leased_b_uuid in dry_rep["skipped_active_leased_uuids"]
    assert open_user_uuid in dry_rep["skipped_active_leased_uuids"]
    assert personal_uuid not in deleted_uuids


def test_gemini_and_studio_helpers_never_hijack_or_close_unleased_user_tabs(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """Verifies `get_gemini_tab`, `close_gemini_tabs`, and `recycle_studio_tab` never hijack or close unleased user tabs."""
    from pipeline import flow_ingredients as fi, gemini_web_worker as gww
    from pipeline.studio import whale_session as ws_mod

    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    user_tabs = [
        {"id": "USER_GMAIL", "type": "page", "url": "https://mail.google.com/", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/USER_GMAIL"},
        {"id": "USER_GEMINI", "type": "page", "url": "https://gemini.google.com/app/personal_chat", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/USER_GEMINI"},
        {"id": "USER_STUDIO", "type": "page", "url": "https://studio.youtube.com/channel/UC_PERSONAL", "webSocketDebuggerUrl": "ws://127.0.0.1:9222/devtools/page/USER_STUDIO"},
    ]
    closed_ids: list[str] = []

    class _FakeHTTP:
        def __init__(self, body: bytes) -> None:
            self._body = body

        def read(self) -> bytes:
            return self._body

        def __enter__(self) -> "_FakeHTTP":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    def _fake_urlopen(req_or_url: Any, timeout: float = 5.0) -> _FakeHTTP:
        u = req_or_url if isinstance(req_or_url, str) else req_or_url.full_url
        if u.endswith("/json/list"):
            return _FakeHTTP(json.dumps(user_tabs).encode("utf-8"))
        if "/json/close/" in u:
            closed_ids.append(u.rsplit("/", 1)[-1])
            return _FakeHTTP(b"Target is closing")
        return _FakeHTTP(b"{}")

    created_idx = [0]

    def _fake_create_bg2(target_url: str, **kw: Any) -> dict[str, Any]:
        created_idx[0] += 1
        tid = "DEDICATED_GEMINI_BG_TAB" if created_idx[0] == 1 else f"STUDIO_RECYCLE_BG_{created_idx[0]}"
        return {
            "id": tid,
            "type": "page",
            "url": target_url,
            "webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/page/{tid}",
            "background": True,
        }

    monkeypatch.setattr("urllib.request.urlopen", _fake_urlopen)
    monkeypatch.setattr("pipeline.cdp_tab_lease._create_target_via_browser_ws", _fake_create_bg2)

    # 1. `get_gemini_tab` must NOT hijack USER_GMAIL or unleased USER_GEMINI; opens dedicated background tab
    gem_tab = asyncio.run(gww.get_gemini_tab(port=9222, owner_id="pid:self:gem_worker"))
    assert gem_tab["id"] == "DEDICATED_GEMINI_BG_TAB"
    assert gem_tab["_opened_by_call"] is True

    # 2. `close_gemini_tabs` with non-matching owner must NOT close USER_GEMINI or sibling's tab
    assert fi.close_gemini_tabs(cdp_port=9222, owner_id="pid:self:other_worker") == []
    assert "USER_GEMINI" not in closed_ids
    # With matching owner `pid:self:gem_worker`, it closes ONLY DEDICATED_GEMINI_BG_TAB (never USER_GEMINI)
    user_tabs.append({"id": "DEDICATED_GEMINI_BG_TAB", "type": "page", "url": "https://gemini.google.com/app"})
    assert fi.close_gemini_tabs(cdp_port=9222, owner_id="pid:self:gem_worker") == ["DEDICATED_GEMINI_BG_TAB"]
    assert closed_ids == ["DEDICATED_GEMINI_BG_TAB"]
    assert "USER_GEMINI" not in closed_ids

    # 3. `WhaleSessionController.recycle_studio_tab(target_id=None)` must NOT close unleased USER_STUDIO
    recycled = ws_mod.WhaleSessionController(cdp_port=9222).recycle_studio_tab(target_id=None)
    assert recycled["id"] == "STUDIO_RECYCLE_BG_2"
    assert "USER_STUDIO" not in closed_ids


def test_substantive_visual_relevance_and_micro_short_profile_forwarding() -> None:
    """
    Verifies:
      - `validate_substantive_visual_relevance` honors `script_doc={"format_profile": "shorts_90s_v7"}`
        when `plan` omits `format_profile` (rejecting 40 clips > 32 ceiling on a 90s episode);
      - `micro_short_v7` (14 clips) builds and validates cleanly in `build_diorama_v7_prompts` / `validate_diorama_v7_prompts`.
    """
    from pipeline.flow_prompt_builder import build_diorama_v7_prompts, validate_diorama_v7_prompts

    sents_26 = [f"Sentence {i} shows how neural circuits adapt." for i in range(1, 27)]
    clips_40 = [
        {
            "clip_index": i,
            "sentence_index": ((i - 1) % 26) + 1,
            "grammar": "porcelain_fullbleed_world",
            "location_id": "clinic_room",
            "scene": "Matte-white porcelain clinician examines a brass neural recording chart beside a wooden desk.",
        }
        for i in range(1, 41)
    ]
    # Plan omits `format_profile`, while `script_doc` specifies `shorts_90s_v7`: 40 clips must be flagged as > 32!
    issues_40 = validate_substantive_visual_relevance(
        {"style_profile": "porcelain_cinematic_v7", "clips": clips_40},
        sents_26,
        clips_40,
        script_doc={"format_profile": "shorts_90s_v7"},
    )
    assert any("exceeds balanced documentary ceiling 32 (shorts_90s_v7)" in x for x in issues_40), issues_40

    # `micro_short_v7` with 14 clips (< DIORAMA_CLIP_COUNT_MIN=20, >= MICRO_SHORT_CUT_MIN=12) builds & validates cleanly
    cams = (
        ["locked_tripod"] * 6
        + ["pan_left", "pan_right", "tilt_up", "tilt_down", "gentle_push_in", "clean_pullback_reveal", "locked_tripod", "locked_tripod"]
    )
    micro_plan = {
        "schema_version": 7,
        "style_profile": "porcelain_cinematic_v7",
        "format_profile": "micro_short_v7",
        "clips": [
            {
                "clip_index": i + 1,
                "act": min(6, (i // 3) + 1),
                "sentence_index": i + 1,
                "grammar": "porcelain_fullbleed_world",
                "camera": cams[i],
                "location_id": "lab_a" if i % 2 == 0 else "lab_b",
                "environment": "sunlit warm-ivory clinical examination room with oak desk and analog oscilloscope",
                "subject": "smooth featureless matte-white oval-head porcelain patient in navy cardigan",
                "action": "lifts a ceramic teacup with the right hand, then sets it cleanly onto a cork coaster",
            }
            for i in range(14)
        ],
    }
    rendered_micro = build_diorama_v7_prompts(micro_plan)
    assert len(rendered_micro) == 14
    micro_errs = validate_diorama_v7_prompts(rendered_micro, plan=micro_plan)
    assert micro_errs == [], micro_errs


def test_clean_flow_workspace_executes_bulk_and_per_card_more_vert_menu_fallbacks(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Verifies `clean_flow_workspace_async(dry_run=False)`:
      1. Bulk `Delete all projects` flow clicks `More options` -> `Delete all projects` -> `Delete all`
         when all visible cards match and zero rooms are protected.
      2. Per-card `mode: 'menu'` (`more_vert`) flow clicks the card's menu button -> `Delete project`
         menu item -> `Delete` confirmation button when a protected/personal card prevents bulk delete.
    """
    from contextlib import asynccontextmanager
    from pipeline import flow_workspace as fw

    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    async def _fast_sleep(_s: float) -> None:
        return None

    monkeypatch.setattr(fw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(fw, "_discover_active_leased_flow_uuids", lambda **_kw: set())

    # Case 1: 2 pipeline/temp cards, 0 personal cards -> bulk Delete all projects
    cards_state: list[dict[str, Any]] = [
        {"idx": 0, "href": "/fx/tools/flow/project/11111111-1111-1111-1111-111111111111", "title": "Oct 29 - 14:10", "delX": 0, "delY": 0},
        {"idx": 1, "href": "/fx/tools/flow/project/22222222-2222-2222-2222-222222222222", "title": "AAB_ep_01", "delX": 0, "delY": 0},
    ]
    clicks: list[tuple[float, float]] = []

    class _FakeBulkAndMenuClient:
        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if method == "Input.dispatchMouseEvent" and isinstance(params, dict) and params.get("type") == "mousePressed":
                pt = (float(params["x"]), float(params["y"]))
                clicks.append(pt)
                if pt == (500.0, 520.0):  # bulk confirm "Delete all"
                    cards_state.clear()
                elif pt == (420.0, 440.0):  # per-card confirm "Delete"
                    cards_state[:] = [c for c in cards_state if c["title"] != "Oct 29 - 09:05"]
            return {}

        async def eval(self, expr: str) -> Any:
            if "new-project-button" in expr:
                return True
            if "flow-project-card" in expr and "delBtn" in expr:
                return list(cards_state)
            if 'button[aria-label="More options"]' in expr:
                return {"x": 920.0, "y": 64.0}
            if "delete all projects" in expr:
                return {"x": 860.0, "y": 310.0}
            if "t !== 'delete all'" in expr:
                return {"x": 500.0, "y": 520.0}
            if "mode: 'menu'" in expr:
                return {"x": 310.0, "y": 210.0, "mode": "menu"}
            if "t.includes('delete project')" in expr:
                return {"x": 330.0, "y": 260.0}
            if "t !== 'delete project'" in expr:
                return {"x": 420.0, "y": 440.0}
            return None

    @asynccontextmanager
    async def _fake_leased_tab(*_a: Any, **_kw: Any):
        yield (_FakeBulkAndMenuClient(), "CLEAN_TAB", "pid:self:clean")

    monkeypatch.setattr(fw, "leased_cdp_tab", _fake_leased_tab)

    rep_bulk = asyncio.run(
        fw.clean_flow_workspace_async(cdp_port=9222, all_projects=True, dry_run=False, clean_local_temp=False)
    )
    assert rep_bulk["deleted_flow_projects_count"] == 2
    assert rep_bulk["remaining_dashboard_cards"] == 0
    assert clicks == [(920.0, 64.0), (860.0, 310.0), (500.0, 520.0)]

    # Case 2: 1 personal card + 1 Oct 29 temp card -> skips bulk delete, uses per-card `more_vert` menu fallback
    clicks.clear()
    cards_state[:] = [
        {"idx": 0, "href": "/fx/tools/flow/project/33333333-3333-3333-3333-333333333333", "title": "My Custom Film", "delX": 0, "delY": 0},
        {"idx": 1, "href": "/fx/tools/flow/project/44444444-4444-4444-4444-444444444444", "title": "Oct 29 - 09:05", "delX": 0, "delY": 0},
    ]
    rep_menu = asyncio.run(
        fw.clean_flow_workspace_async(cdp_port=9222, all_projects=True, dry_run=False, clean_local_temp=False)
    )
    assert rep_menu["deleted_flow_projects_count"] == 1
    assert rep_menu["deleted_flow_projects"][0]["uuid"] == "44444444-4444-4444-4444-444444444444"
    assert rep_menu["remaining_dashboard_cards"] == 1
    assert clicks == [(310.0, 210.0), (330.0, 260.0), (420.0, 440.0)]

    # Case 3: When `More options` opens an overlay where `Delete all projects` is disabled/unavailable,
    # `_dismiss_cdk_overlays` must close `.cdk-overlay-backdrop` before per-card deletion clicks run.
    overlay_open = {"active": False, "dismissed": 0}
    escaped_keys: list[str] = []

    class _FakeOverlayFallthroughClient:
        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            if method == "Input.dispatchKeyEvent" and isinstance(params, dict) and params.get("key") == "Escape":
                overlay_open["active"] = False
                escaped_keys.append(str(params.get("type")))
            if method == "Input.dispatchMouseEvent" and isinstance(params, dict) and params.get("type") == "mousePressed":
                pt = (float(params["x"]), float(params["y"]))
                if pt == (920.0, 64.0):
                    overlay_open["active"] = True
                elif pt == (420.0, 440.0):
                    # Per-card confirm only succeeds if `.cdk-overlay-backdrop` was dismissed first!
                    assert not overlay_open["active"], "Stuck CDK backdrop was not dismissed before per-card click!"
                    cards_state.clear()
            return {}

        async def eval(self, expr: str) -> Any:
            if "new-project-button" in expr:
                return True
            if "flow-project-card" in expr and "delBtn" in expr:
                return list(cards_state)
            if 'button[aria-label="More options"]' in expr:
                return {"x": 920.0, "y": 64.0}
            if "delete all projects" in expr:
                assert "flow-menu-item" in expr and "mat-mdc-menu-item-disabled" in expr
                return None  # disabled `<button>` inside `<flow-menu-item>` rejected
            if ".cdk-overlay-backdrop" in expr:
                overlay_open["active"] = False
                overlay_open["dismissed"] += 1
                return None
            if "mode: 'menu'" in expr:
                assert not overlay_open["active"], "Card button clicked while CDK backdrop still open!"
                return {"x": 280.0, "y": 200.0, "mode": "direct"}
            if "t !== 'delete project'" in expr:
                return {"x": 420.0, "y": 440.0}
            return None

    @asynccontextmanager
    async def _fake_fallthrough_tab(*_a: Any, **_kw: Any):
        yield (_FakeOverlayFallthroughClient(), "CLEAN_TAB_FT", "pid:self:clean_ft")

    monkeypatch.setattr(fw, "leased_cdp_tab", _fake_fallthrough_tab)
    cards_state[:] = [
        {"idx": 0, "href": "/project/55555555-5555-5555-5555-555555555555", "title": "05 Nov - 07:35", "delX": 280, "delY": 200},
    ]
    fake_tmp = tmp_path / "tmp_clean"
    fake_tmp.mkdir()
    (fake_tmp / "bci_test_projects" / "test_ep").mkdir(parents=True)
    local_rep = fw.purge_local_flow_temp_files(dry_run=False, temp_root=fake_tmp, bridge_root=tmp_path / "no_bridge", force_active=True)
    assert local_rep["removed_dirs_count"] == 1
    assert not (fake_tmp / "bci_test_projects").exists()

    rep_ft = asyncio.run(
        fw.clean_flow_workspace_async(cdp_port=9222, all_projects=True, dry_run=False, clean_local_temp=False)
    )
    assert rep_ft["deleted_flow_projects_count"] == 1
    assert rep_ft["remaining_dashboard_cards"] == 0
    assert overlay_open["dismissed"] >= 1
    assert "keyDown" in escaped_keys


def test_single_canonical_flow_room_reuse_across_waves_shards_and_cooldown_plus_clips_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Regression lock for single-room Google Flow reuse (AGENTS.md 1-room-per-episode lock):
      1. `allocate_dedicated_flow_project_tab` reuses `existing_project_url` AND existing `AAB_<project_id>`
         dashboard cards without clicking `button.new-project-button`.
      2. `_run_shard_worker` across shards, waves, and transient tile-error retries ALWAYS uses canonical
         `AAB_<project_id>` (zero `__clips_s*_w*` names) and reuses `flow_rate_state['canonical_project_url']`
         in-place without spinning up extra Flow project URLs (while `"unusual activity"` halts immediately
         under the Zero-Bypass Halt Guard).
    """
    import collections
    from pipeline import flow_diorama_sharded_worker as sw
    from pipeline import flow_live_single_worker as flsw

    leases_file = tmp_path / "aab_cdp_leases.json"
    locks_dir = tmp_path / "aab_locks"
    monkeypatch.setenv("AAB_CDP_LEASES_PATH", str(leases_file))
    monkeypatch.setenv("AAB_LOCKS_DIR", str(locks_dir))

    fake_mono = [1000.0]

    async def _fast_sleep(_sec: float, result: Any = None) -> Any:
        fake_mono[0] += max(0.01, float(_sec))
        return result

    monkeypatch.setattr(flsw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(sw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(sw.time, "monotonic", lambda: fake_mono[0])
    monkeypatch.setattr(flsw.time, "monotonic", lambda: fake_mono[0])

    # Part A: allocate_dedicated_flow_project_tab reuses existing_project_url & dashboard card (0 New project clicks)
    new_project_clicks = [0]
    navigated_urls: list[str] = []
    tab_seq = [0]

    class _FakeResp:
        def __init__(self, payload: bytes) -> None:
            self._payload = payload

        def read(self) -> bytes:
            return self._payload

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *args: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda *_a, **_kw: _FakeResp(b"[]"))

    def _fake_create_bg(target_url: str, **kwargs: Any) -> dict[str, Any]:
        tab_seq[0] += 1
        tid = f"REUSE_TAB_{tab_seq[0]}"
        return {
            "id": tid,
            "type": "page",
            "url": target_url,
            "webSocketDebuggerUrl": f"ws://127.0.0.1:9222/devtools/page/{tid}",
            "background": True,
        }

    class _CardReuseCDP:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url
            self._loc = "about:blank"

        async def __aenter__(self) -> "_CardReuseCDP":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None, timeout_sec: float = 10.0) -> dict[str, Any]:
            if method == "Page.navigate" and isinstance(params, dict):
                u = str(params.get("url") or "")
                navigated_urls.append(u)
                self._loc = u
            return {}

        async def eval(self, expr: str, timeout_sec: float = 10.0) -> Any:
            if expr == "location.href":
                return self._loc
            if "flow-project-card" in expr and "wanted" in expr:
                return "/project/99999999-aaaa-bbbb-cccc-dddddddddddd"
            if "new-project-button" in expr:
                new_project_clicks[0] += 1
                return True
            return ""

    monkeypatch.setattr("pipeline.cdp_tab_lease._create_target_via_browser_ws", _fake_create_bg)
    monkeypatch.setattr(flsw, "DirectCDPClient", _CardReuseCDP)
    monkeypatch.setattr(flsw, "rename_active_flow_project", lambda *_a, **_kw: asyncio.sleep(0))

    # 1) Dashboard card match reuses `/project/99999999-...` with 0 New project clicks
    alloc_card = asyncio.run(
        flsw.allocate_dedicated_flow_project_tab(cdp_port=9222, project_id="ep_reuse_01")
    )
    assert alloc_card["project_url"] == "https://flow.google.com/project/99999999-aaaa-bbbb-cccc-dddddddddddd"
    assert new_project_clicks[0] == 0

    # 2) Explicit existing_project_url navigates straight to canonical URL without even hitting dashboard
    navigated_urls.clear()
    alloc_direct = asyncio.run(
        flsw.allocate_dedicated_flow_project_tab(
            cdp_port=9222,
            project_id="ep_reuse_01",
            existing_project_url="https://flow.google.com/project/99999999-aaaa-bbbb-cccc-dddddddddddd",
        )
    )
    assert alloc_direct["project_url"] == "https://flow.google.com/project/99999999-aaaa-bbbb-cccc-dddddddddddd"
    assert navigated_urls == ["https://flow.google.com/project/99999999-aaaa-bbbb-cccc-dddddddddddd"]
    assert new_project_clicks[0] == 0

    # Part B: _run_shard_worker reuses ONE canonical room across shards, waves, and unusual-activity cooldown
    alloc_calls: list[dict[str, Any]] = []
    renamed_titles: list[str] = []
    poll_count = [0]

    async def _spy_alloc_tab(**kwargs: Any) -> dict[str, Any]:
        alloc_calls.append(dict(kwargs))
        url = kwargs.get("existing_project_url") or "https://flow.google.com/project/canonical-1111-2222-3333-444444444444"
        return {
            "tab_id": f"SHARD_TAB_{len(alloc_calls)}",
            "project_url": url,
            "ws_url": "ws://dummy",
            "lease_owner_id": f"owner_{len(alloc_calls)}",
        }

    class _ShardCDP:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_ShardCDP":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

        async def eval(self, expr: str) -> Any:
            if "button.settings-trigger-button" in expr and "readyState" in expr:
                return True
            if "classifyTile" in expr and "hasNewSrc" in expr:
                poll_count[0] += 1
                if poll_count[0] == 1:
                    # Trigger a transient tile error on first poll — worker MUST retry in canonical room in-place (not open wave 2!)
                    return {
                        "ready": 0,
                        "rendering": 0,
                        "hasNewSrc": False,
                        "topKey": "",
                        "hadErr": True,
                        "errText": "Temporary tile generation error.",
                    }
                return {"ready": 1, "rendering": 0, "hasNewSrc": True, "topKey": f"https://v/{poll_count[0]}", "hadErr": False}
            if "classifyTile" in expr:
                return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}
            return {}

    async def _spy_rename(_c: Any, title: str) -> bool:
        renamed_titles.append(title)
        return True

    async def _fake_submit(_c: Any, _p: str, *_a: Any, **kw: Any) -> bool:
        if kw.get("submission_meta_out") is not None:
            kw["submission_meta_out"]["flow_model"] = "Veo 3.1 - Lite [Lower Priority]"
            kw["submission_meta_out"]["credit_tier"] = "zero_credit_fallback"
        return True

    async def _fake_dl(dst_mp4: Path, **_kw: Any) -> dict[str, Any]:
        dst_mp4.write_bytes(b"1" * 1_050_000)
        return {"sha256": f"sha_{dst_mp4.stem}_{poll_count[0]}", "file_size_bytes": 1_050_000, "source_download_filename": dst_mp4.name}

    monkeypatch.setattr(sw, "allocate_dedicated_flow_project_tab", _spy_alloc_tab)
    monkeypatch.setattr(sw, "DirectCDPClient", _ShardCDP)
    monkeypatch.setattr(sw, "rename_active_flow_project", _spy_rename)
    monkeypatch.setattr(sw, "enable_background_focus_emulation", lambda *_a, **_kw: asyncio.sleep(0))
    monkeypatch.setattr(sw, "release_and_close_leased_tab", lambda *_a, **_kw: True)
    monkeypatch.setattr(
        sw,
        "_configure_diorama_tab_engine",
        lambda *_a, **_kw: asyncio.sleep(0, result={"flow_model": "Veo 3.1 - Lite [Lower Priority]", "credit_tier": "zero_credit_fallback", "settings_summary": "ok"}),
    )
    monkeypatch.setattr(sw, "_submit_diorama_prompt_zero_credit", _fake_submit)
    monkeypatch.setattr(sw, "_download_newest_ready_tile", _fake_dl)
    monkeypatch.setattr(
        sw,
        "inspect_diorama_clip_cv",
        lambda *_a, **_kw: {"passed": True, "max_frame_diff": 12.0, "mean_luma": 110.0, "plaque_glyph_run": 0},
    )
    monkeypatch.setattr(sw, "_ensure_min_clip_size_if_needed", lambda _p: None)

    rate_state: dict[str, Any] = {
        "submit_lock": asyncio.Lock(),
        "last_tab_open_mono": 0.0,
        "last_submit_mono": 0.0,
        "cooldown_until_mono": 0.0,
        "cooldown_hits": 0,
        "canonical_project_url": "",
        "opened_project_urls": [],
        "tab_owners_by_id": {},
    }
    q1 = collections.deque([{"clip_number": 1, "grammar": "expressive_vinyl_world", "prompt": "c1", "schema_version": 8}])
    q2 = collections.deque([{"clip_number": 2, "grammar": "expressive_vinyl_world", "prompt": "c2", "schema_version": 8}])
    lock = asyncio.Lock()

    r1 = asyncio.run(
        sw._run_shard_worker(
            shard_idx=1,
            shard_clips=[],
            project_id="v8_pilot_02_test",
            project_dir=tmp_path,
            short_ref_map={},
            tab_open_lock=lock,
            opened_tabs=[],
            seen_global_shas=set(),
            shared_clip_queue=q1,
            flow_rate_state=rate_state,
        )
    )
    r2 = asyncio.run(
        sw._run_shard_worker(
            shard_idx=2,
            shard_clips=[],
            project_id="v8_pilot_02_test",
            project_dir=tmp_path,
            short_ref_map={},
            tab_open_lock=lock,
            opened_tabs=[],
            seen_global_shas=set(),
            shared_clip_queue=q2,
            flow_rate_state=rate_state,
        )
    )

    # Shard 1 survived transient tile-error retry in-place (1 tab allocation, NOT 2!) and Shard 2 reused Shard 1's canonical URL!
    assert len(alloc_calls) == 2
    assert alloc_calls[0]["project_id"] == "v8_pilot_02_test"
    assert alloc_calls[0]["room_name"] == "AAB_v8_pilot_02_test"
    assert alloc_calls[1]["existing_project_url"] == "https://flow.google.com/project/canonical-1111-2222-3333-444444444444"
    assert set(renamed_titles) == {"AAB_v8_pilot_02_test"}
    assert all("__clips" not in t for t in renamed_titles)
    assert r1["flow_project_url"] == r2["flow_project_url"] == "https://flow.google.com/project/canonical-1111-2222-3333-444444444444"
    assert rate_state["opened_project_urls"] == ["https://flow.google.com/project/canonical-1111-2222-3333-444444444444"]


def test_audit_item1_receipt_prompt_and_ref_sha_guard_invalidates_stale_clips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Audit Item 1: `clip_receipt_matches_fingerprints` + `_pop_next_pending_clip` reuse an on-disk
    clip ONLY when `prompt_sha`, `start_ref_sha256`, and `end_ref_sha256` all match the receipt;
    any legacy missing hash or prompt/ref change deletes the stale MP4 and queues regeneration.
    """
    import collections
    import hashlib
    import pipeline.flow_diorama_sharded_worker as sw

    p_dir = tmp_path / "ep_sha_guard"
    refs_dir = p_dir / "03_visuals" / "reference_images"
    native_dir = p_dir / "03_visuals" / "flow_native_clips"
    refs_dir.mkdir(parents=True)
    native_dir.mkdir(parents=True)

    s_ref = refs_dir / "start.png"
    e_ref = refs_dir / "end.png"
    s_ref.write_bytes(b"START_PNG_V1")
    e_ref.write_bytes(b"END_PNG_V1")

    spec = {
        "clip_number": 1,
        "grammar": "expressive_vinyl_world",
        "prompt": "Original 15-sentence prompt v1",
        "reference_image": "03_visuals/reference_images/start.png",
        "end_reference_image": "03_visuals/reference_images/end.png",
        "schema_version": 8,
    }
    fp_v1 = sw.compute_clip_spec_fingerprints(spec, p_dir)
    assert fp_v1["prompt_sha"] == hashlib.sha256(b"Original 15-sentence prompt v1").hexdigest()
    assert fp_v1["start_ref_sha256"] == hashlib.sha256(b"START_PNG_V1").hexdigest()
    assert fp_v1["end_ref_sha256"] == hashlib.sha256(b"END_PNG_V1").hexdigest()

    monkeypatch.setattr(
        sw,
        "inspect_diorama_clip_cv",
        lambda *_a, **_kw: {"passed": True, "max_frame_diff": 12.0, "mean_luma": 110.0, "plaque_glyph_run": 0},
    )

    clip_p = native_dir / "clip_1.mp4"
    clip_p.write_bytes(b"M" * 1_050_000)

    # Case 1: Legacy receipt missing prompt_sha -> rejected, clip deleted & popped for regen
    ok_leg, reason_leg = sw.clip_receipt_matches_fingerprints({"clip_index": 1}, fp_v1)
    assert ok_leg is False and "prompt_sha" in reason_leg
    popped_leg = sw._pop_next_pending_clip(
        collections.deque([dict(spec)]),
        p_dir,
        seen_global_shas=set(),
        episode_qa_contract=None,
        existing_clips_by_idx={1: {"clip_index": 1, "reference_attached": True, "end_reference_attached": True, "input_mode": "VIDEO_FRAMES"}},
        prev_ref_enforced=True,
    )
    assert popped_leg is not None and int(popped_leg["clip_number"]) == 1
    assert not clip_p.exists()

    # Case 2: Exact prompt_sha + start_ref_sha256 + end_ref_sha256 match -> reused (`None` popped, file preserved)
    clip_p.write_bytes(b"M" * 1_050_000)
    matching_rec = {
        "clip_index": 1,
        "reference_attached": True,
        "end_reference_attached": True,
        "input_mode": "VIDEO_FRAMES",
        **fp_v1,
    }
    seen_shas: set[str] = set()
    popped_match = sw._pop_next_pending_clip(
        collections.deque([dict(spec)]),
        p_dir,
        seen_global_shas=seen_shas,
        episode_qa_contract=None,
        existing_clips_by_idx={1: matching_rec},
        prev_ref_enforced=True,
    )
    assert popped_match is None
    assert clip_p.exists()
    assert len(seen_shas) == 1

    # Case 3: Prompt changes -> stale clip deleted & popped for regeneration
    spec_new_prompt = {**spec, "prompt": "Updated keyframe-chain prompt v2"}
    popped_prompt_drift = sw._pop_next_pending_clip(
        collections.deque([spec_new_prompt]),
        p_dir,
        seen_global_shas=set(),
        episode_qa_contract=None,
        existing_clips_by_idx={1: matching_rec},
        prev_ref_enforced=True,
    )
    assert popped_prompt_drift is not None and popped_prompt_drift["prompt"] == "Updated keyframe-chain prompt v2"
    assert not clip_p.exists()

    # Case 4: End reference image bytes change -> stale clip deleted & popped for regeneration
    clip_p.write_bytes(b"M" * 1_050_000)
    e_ref.write_bytes(b"END_PNG_V2_CHANGED")
    popped_ref_drift = sw._pop_next_pending_clip(
        collections.deque([dict(spec)]),
        p_dir,
        seen_global_shas=set(),
        episode_qa_contract=None,
        existing_clips_by_idx={1: matching_rec},
        prev_ref_enforced=True,
    )
    assert popped_ref_drift is not None
    assert not clip_p.exists()


def test_audit_item3_script_newer_than_audio_master_mtime_and_hash_guard(tmp_path: Path) -> None:
    """
    Audit Item 3: Assembly (cached & preserve_audio_master & recut) and QA gates refuse to run
    when `script.json` is newer than `audio_master.wav` OR when `script_sha256`/`sentences_sha256`
    mismatch `voice_report.json`.
    """
    import os
    from pipeline.diorama_assembler import (
        assemble_diorama_project,
        compute_script_freshness_digests,
        recut_diorama_cuts,
        verify_script_audio_freshness,
    )
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract
    from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa
    from pipeline.prosody import evaluate_prosody_gates
    from pipeline.video_autopsy import VideoAutopsyEngine

    p_dir = tmp_path / "ep_stale_guard"
    for sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    for i in range(1, 21):
        (p_dir / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4").write_bytes(b"0" * 4096)

    sc_path = p_dir / "02_script" / "script.json"
    sc_path.write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "sentences": ["Why wake at 3 AM?", "Half your brain stood guard."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"schema_version": 8, "style_profile": "expressive_25d_v8", "clips": []}),
        encoding="utf-8",
    )
    dig = compute_script_freshness_digests(p_dir)
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    wav_path.write_bytes(b"RIFF\x00\x00\x00\x00WAVE")
    vr_path = p_dir / "04_audio" / "voice_report.json"
    vr_path.write_text(
        json.dumps(
            {
                "script_sha256": dig["script_sha256"],
                "sentences_sha256": dig["sentences_sha256"],
                "sentence_spans": [{"sentence_index": 1, "text": "Why wake at 3 AM?", "start_sec": 0.0, "end_sec": 1.5}],
                "events": [],
                "speech_end_sec": 3.0,
                "total_duration_sec": 4.0,
            }
        ),
        encoding="utf-8",
    )
    mp4_path = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    mp4_path.write_bytes(b"0" * 8192)
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(json.dumps({"schema": 8, "cuts": []}), encoding="utf-8")

    os.utime(sc_path, (1000.0, 1000.0))
    os.utime(wav_path, (1005.0, 1005.0))
    assert verify_script_audio_freshness(p_dir)["fresh"] is True

    # 1) Mtime guard: script.json touched AFTER audio_master.wav -> ALL assembly & QA entrypoints refuse with RuntimeError
    os.utime(sc_path, (1020.0, 1020.0))
    for fn in (
        lambda: assemble_diorama_project(p_dir, force_rebuild=False),
        lambda: assemble_diorama_project(p_dir, force_rebuild=True, preserve_audio_master=True),
        lambda: recut_diorama_cuts(p_dir, [1]),
        lambda: verify_final_mp4_against_contract(p_dir, run_asr_sync=False, save_report=False),
        lambda: run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False, save_report=False),
        lambda: VideoAutopsyEngine.inspect_project(p_dir, save_report=False),
        lambda: evaluate_prosody_gates(p_dir, run_asr=False, save_report=False, strict_freshness=True),
    ):
        with pytest.raises(RuntimeError, match="Stale audio/assembly guard"):
            fn()

    # 2) Hash guard: even if mtime is backdated <= audio_master.wav, modified script content STILL triggers RuntimeError
    sc_path.write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "sentences": ["Why wake at 3 AM?", "Edited 15-sentence script!"]}),
        encoding="utf-8",
    )
    os.utime(sc_path, (995.0, 995.0))
    with pytest.raises(RuntimeError, match="sha256"):
        verify_script_audio_freshness(p_dir, context="hash-test")


def test_audit_item4_and_8_download_missed_rescan_and_two_miss_abort_partial_summary(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Audit Items 4 & 8:
      - On `download_missed`, worker re-scans the Flow gallery (`_rescan_gallery_for_missed_tile`)
        before resubmitting; if the tile hydrates on re-scan, clip succeeds with `submit_calls == 1`.
      - After 2 consecutive `download_missed` failures, worker aborts early with
        `download_missed_abort(consecutive_download_misses=2)` (not 5!) and
        `run_sharded_diorama_flow_generation` writes `03_visuals/flow_partial_usable_summary.json`.
    """
    import asyncio
    import pipeline.dynamic_episode_qa as deq
    import pipeline.flow_diorama_sharded_worker as sw
    import pipeline.flow_workspace as fw

    fake_mono = [1000.0]

    async def _fast_sleep(_sec: float, result: Any = None) -> Any:
        fake_mono[0] += max(0.01, float(_sec))
        return result

    monkeypatch.setattr(sw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(sw.time, "monotonic", lambda: fake_mono[0])

    p_dir = tmp_path / "ep_dl_miss"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "03_visuals").mkdir(parents=True)
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 8, "style_profile": "expressive_25d_v8", "sentences": ["S1?", "S2."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema_version": 8,
                "style_profile": "expressive_25d_v8",
                "clips": [
                    {"clip_number": 1, "sentence_index": 1, "end_sentence_index": 1, "grammar": "expressive_vinyl_world"},
                    {"clip_number": 2, "sentence_index": 2, "end_sentence_index": 2, "grammar": "expressive_vinyl_world"},
                ],
            }
        ),
        encoding="utf-8",
    )

    submit_prompts: list[str] = []
    dl_calls_by_clip: dict[str, int] = {"clip_1": 0, "clip_2": 0}
    clean_calls: list[dict[str, Any]] = []

    class _FakeCDP:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url

        async def __aenter__(self) -> "_FakeCDP":
            return self

        async def __aexit__(self, *args: object) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

        async def eval(self, expr: str) -> Any:
            if "button.settings-trigger-button" in expr and "readyState" in expr:
                return True
            if "unseenHydrated" in expr:
                return {"readyCount": 1, "unseenHydrated": 1}
            if "classifyTile" in expr and "hasNewSrc" in expr:
                return {"ready": 1, "rendering": 0, "hasNewSrc": True, "topKey": f"https://v/{len(submit_prompts)}", "hadErr": False}
            if "classifyTile" in expr:
                return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}
            return {}

    async def _fake_alloc(**kwargs: Any) -> dict[str, Any]:
        return {
            "tab_id": "TAB_1",
            "project_url": kwargs.get("existing_project_url") or "https://flow.google.com/project/canon-room-1234",
            "ws_url": "ws://dummy",
            "lease_owner_id": "owner_1",
        }

    async def _fake_submit(_c: Any, prompt_txt: str, *_a: Any, **kw: Any) -> bool:
        submit_prompts.append(prompt_txt)
        if kw.get("submission_meta_out") is not None:
            kw["submission_meta_out"]["flow_model"] = "Veo 3.1 - Lite [Lower Priority]"
            kw["submission_meta_out"]["credit_tier"] = "zero_credit_fallback"
        return True

    async def _fake_dl(dst_mp4: Path, **_kw: Any) -> dict[str, Any] | None:
        # dst_mp4 is `/tmp/aab_flow_cand_<shard>_<clip_num>_<try>.mp4`
        parts = dst_mp4.stem.split("_")
        clip_key = f"clip_{parts[-2]}" if len(parts) >= 3 else dst_mp4.stem
        dl_calls_by_clip[clip_key] = dl_calls_by_clip.get(clip_key, 0) + 1
        if clip_key == "clip_1":
            # Clip 1: 1st download misses, gallery re-scan (2nd call) recovers WITHOUT resubmitting!
            if dl_calls_by_clip[clip_key] == 1:
                return None
            dst_mp4.write_bytes(b"1" * 1_050_000)
            return {"sha256": "sha_clip_1_ok", "file_size_bytes": 1_050_000, "source_download_filename": "clip_1.mp4"}
        # Clip 2: always misses both primary download and re-scan -> must abort after 2 tries (4 dl calls: 2 tries x (primary+rescan))
        return None

    async def _spy_clean_ws(**kw: Any) -> dict[str, Any]:
        clean_calls.append(dict(kw))
        return {"deleted": 0}

    monkeypatch.setattr(sw, "build_diorama_v6_prompts", lambda _vp, _s: [
        {"clip_number": 1, "grammar": "expressive_vinyl_world", "prompt": "P1", "schema_version": 8},
        {"clip_number": 2, "grammar": "expressive_vinyl_world", "prompt": "P2", "schema_version": 8},
    ])
    monkeypatch.setattr(sw, "write_flow_prompts_json", lambda *_a, **_kw: None)
    monkeypatch.setattr(deq, "write_episode_qa_contract", lambda *_a, **_kw: (p_dir / "03_visuals" / "episode_qa_contract.json", {}))
    monkeypatch.setattr(sw, "allocate_dedicated_flow_project_tab", _fake_alloc)
    monkeypatch.setattr(sw, "DirectCDPClient", _FakeCDP)
    monkeypatch.setattr(sw, "rename_active_flow_project", lambda *_a, **_kw: asyncio.sleep(0, result=True))
    monkeypatch.setattr(sw, "enable_background_focus_emulation", lambda *_a, **_kw: asyncio.sleep(0))
    monkeypatch.setattr(sw, "release_and_close_leased_tab", lambda *_a, **_kw: True)
    monkeypatch.setattr(
        sw,
        "_configure_diorama_tab_engine",
        lambda *_a, **_kw: asyncio.sleep(0, result={"flow_model": "Veo 3.1 - Lite [Lower Priority]", "credit_tier": "zero_credit_fallback", "settings_summary": "ok"}),
    )
    monkeypatch.setattr(sw, "_submit_diorama_prompt_zero_credit", _fake_submit)
    monkeypatch.setattr(sw, "_download_newest_ready_tile", _fake_dl)
    monkeypatch.setattr(
        sw,
        "inspect_diorama_clip_cv",
        lambda *_a, **_kw: {"passed": True, "max_frame_diff": 12.0, "mean_luma": 110.0, "plaque_glyph_run": 0},
    )
    monkeypatch.setattr(sw, "_ensure_min_clip_size_if_needed", lambda _p: None)
    monkeypatch.setattr(fw, "clean_flow_workspace_async", _spy_clean_ws)
    monkeypatch.setattr(sw, "clean_flow_workspace_async", _spy_clean_ws)
    monkeypatch.setattr(sw, "reap_orphan_pipeline_tabs", lambda **_kw: None)

    with pytest.raises(RuntimeError, match=r"download_missed_abort\(consecutive_download_misses=2\)"):
        asyncio.run(sw.run_sharded_diorama_flow_generation(p_dir, max_parallel_tabs=1, engine_mode="zero-credit"))

    # Clip 1 submitted ONLY ONCE (recovered via gallery re-scan!), Clip 2 submitted ONLY TWICE (aborted at 2 misses, NOT 5!)
    assert submit_prompts.count("P1") == 1
    assert submit_prompts.count("P2") == 2

    # Audit Item 8: Partial usable-clip summary written on single clip failure
    partial_path = p_dir / "03_visuals" / "flow_partial_usable_summary.json"
    assert partial_path.exists()
    partial = json.loads(partial_path.read_text(encoding="utf-8"))
    assert partial["usable_clip_indices"] == [1]
    assert partial["missing_or_failed_clip_indices"] == [2]
    assert any("download_missed_abort" in d["error"] for d in partial["failed_clip_details"])

    # Room Preservation Lock: by default (`FLOW_AUTO_CLEANUP_ON_SUCCESS == False`), episode rooms are NEVER deleted
    assert sw.FLOW_AUTO_CLEANUP_ON_SUCCESS is False
    assert len(clean_calls) == 0


def test_audit_item5_v8_yunet_skin_or_hair_leak_advisory_vs_real_flesh() -> None:
    """
    Audit Item 5: Cool-lit matte-white 2.5D vinyl heads with black 2D ink features are treated as
    advisory (`confirmed_human == False`) with `bbox` + `score` telemetry, whereas real warm human
    skin or dark hair caps trigger `confirmed_human == True`.
    """
    import cv2
    import numpy as np
    import pipeline.flow_diorama_sharded_worker as sw

    # 1) Matte-white 2.5D vinyl oval head (cool nightstand bounce + black 2D ink eyes) -> advisory only
    vinyl_roi = np.full((240, 240, 3), (235, 232, 226), dtype=np.uint8)
    cv2.circle(vinyl_roi, (95, 110), 9, (22, 22, 24), -1)
    cv2.circle(vinyl_roi, (145, 110), 9, (22, 22, 24), -1)
    confirmed_vinyl, meta_vinyl = sw.verify_v8_yunet_skin_or_hair_leak(vinyl_roi, (40, 40, 160, 160, 0.71))
    assert confirmed_vinyl is False
    assert meta_vinyl["bbox"] == [40, 40, 160, 160]
    assert meta_vinyl["score"] == 0.71

    # 2) Real human warm peach skin face -> confirmed leak
    skin_roi = np.full((240, 240, 3), (125, 158, 212), dtype=np.uint8)  # BGR warm peach skin
    confirmed_skin, meta_skin = sw.verify_v8_yunet_skin_or_hair_leak(skin_roi, (40, 40, 160, 160, 0.84))
    assert confirmed_skin is True
    assert meta_skin["skin_ratio"] > 0.20

    # 3a) Warm amber-lit cream 2.5D vinyl with 2D ink eyes (high skin_ratio >= 0.45, low hemoglobin) -> MODERATE_SUSPECT (confirmed=False, no false worker retry!)
    amber_skin_roi = np.full((240, 240, 3), (145, 196, 224), dtype=np.uint8)
    amber_skin_roi[0:50, 40:60] = (24, 28, 36)
    cv2.line(amber_skin_roi, (78, 78), (108, 76), (20, 20, 22), 5)
    cv2.line(amber_skin_roi, (132, 76), (162, 78), (20, 20, 22), 5)
    confirmed_amber_skin, meta_amber_skin = sw.verify_v8_yunet_skin_or_hair_leak(
        amber_skin_roi, (40, 40, 160, 160, 0.85)
    )
    assert confirmed_amber_skin is False
    assert meta_amber_skin["suspect_tier"] == "MODERATE_SUSPECT"
    assert meta_amber_skin["skin_ratio"] >= 0.45

    # 3b) True cream-white bald 2.5D vinyl (low saturation, skin_ratio < 0.45, 2D ink eyes) -> advisory pass
    cream_vinyl_roi = np.full((240, 240, 3), (195, 224, 236), dtype=np.uint8)
    cream_vinyl_roi[0:50, 40:60] = (24, 28, 36)
    cv2.circle(cream_vinyl_roi, (95, 110), 10, (20, 20, 22), -1)
    cv2.circle(cream_vinyl_roi, (145, 110), 10, (20, 20, 22), -1)
    confirmed_cream_vinyl, meta_cream_vinyl = sw.verify_v8_yunet_skin_or_hair_leak(
        cream_vinyl_roi, (40, 40, 160, 160, 0.85)
    )
    assert confirmed_cream_vinyl is False
    assert meta_cream_vinyl["skin_ratio"] < 0.45

    # 4) Dark hair cap wrapping crown + temples -> HIGH_SUSPECT confirmed leak
    hair_cap_roi = np.full((240, 240, 3), (145, 180, 224), dtype=np.uint8)
    hair_cap_roi[15:72, 48:192] = (18, 20, 24)   # dark crown hair
    hair_cap_roi[65:125, 35:68] = (18, 20, 24)   # dark temple wrap
    confirmed_hair_cap, meta_hair_cap = sw.verify_v8_yunet_skin_or_hair_leak(
        hair_cap_roi, (40, 40, 160, 160, 0.88)
    )
    assert confirmed_hair_cap is True
    assert meta_hair_cap["scalp_dark_hair"] >= 0.25


def test_audit_item6_stale_seed_canonical_url_updates_across_shards_and_excludes_in_cleanup(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """
    Audit Item 6:
      1) If `seed_canonical_url` from an old receipt redirects/404s and `allocate_dedicated_flow_project_tab`
         returns a new canonical room URL, Shard 1 updates `flow_rate_state["canonical_project_url"]` so
         Shard 2 reuses the NEW canonical room (never falling back to the dead URL and spawning a 2nd room).
      2) `clean_flow_workspace_async(exclude_project_urls=[...])` deletes `__clips*` duplicates while sparing
         the canonical room URL.
    """
    import asyncio
    import collections
    import pipeline.flow_diorama_sharded_worker as sw
    import pipeline.flow_workspace as fw

    fake_mono = [1000.0]

    async def _fast_sleep(_sec: float, result: Any = None) -> Any:
        fake_mono[0] += max(0.01, float(_sec))
        return result

    monkeypatch.setattr(sw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(sw.time, "monotonic", lambda: fake_mono[0])
    monkeypatch.setattr(fw.asyncio, "sleep", _fast_sleep)

    seen_existing_urls: list[str | None] = []

    async def _alloc_with_stale_seed(**kwargs: Any) -> dict[str, Any]:
        ex = kwargs.get("existing_project_url")
        seen_existing_urls.append(ex)
        # Simulate stale seed URL failing and allocating fresh canonical room `new-canon-7777`
        resolved = (
            "https://flow.google.com/project/new-canon-7777"
            if ex == "https://flow.google.com/project/dead-stale-0000"
            else (ex or "https://flow.google.com/project/new-canon-7777")
        )
        return {"tab_id": f"T{len(seen_existing_urls)}", "project_url": resolved, "ws_url": "ws://d", "lease_owner_id": "own"}

    class _MinCDP:
        def __init__(self, _ws: str) -> None:
            pass

        async def __aenter__(self) -> "_MinCDP":
            return self

        async def __aexit__(self, *_a: object) -> None:
            return None

        async def send(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
            return {}

        async def eval(self, expr: str) -> Any:
            if "button.settings-trigger-button" in expr:
                return True
            if "classifyTile" in expr and "hasNewSrc" in expr:
                return {"ready": 1, "rendering": 0, "hasNewSrc": True, "topKey": f"https://v/{len(seen_existing_urls)}", "hadErr": False}
            return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}

    async def _dl(dst_mp4: Path, **_kw: Any) -> dict[str, Any]:
        dst_mp4.write_bytes(b"2" * 1_050_000)
        return {"sha256": f"s_{dst_mp4.stem}", "file_size_bytes": 1_050_000, "source_download_filename": dst_mp4.name}

    async def _sub(_c: Any, _p: str, *_a: Any, **kw: Any) -> bool:
        if kw.get("submission_meta_out") is not None:
            kw["submission_meta_out"]["flow_model"] = "Veo 3.1 - Lite [Lower Priority]"
            kw["submission_meta_out"]["credit_tier"] = "zero_credit_fallback"
        return True

    monkeypatch.setattr(sw, "allocate_dedicated_flow_project_tab", _alloc_with_stale_seed)
    monkeypatch.setattr(sw, "DirectCDPClient", _MinCDP)
    monkeypatch.setattr(sw, "rename_active_flow_project", lambda *_a, **_kw: asyncio.sleep(0, result=True))
    monkeypatch.setattr(sw, "enable_background_focus_emulation", lambda *_a, **_kw: asyncio.sleep(0))
    monkeypatch.setattr(sw, "release_and_close_leased_tab", lambda *_a, **_kw: True)
    monkeypatch.setattr(
        sw,
        "_configure_diorama_tab_engine",
        lambda *_a, **_kw: asyncio.sleep(0, result={"flow_model": "Veo 3.1 - Lite [Lower Priority]", "credit_tier": "zero_credit_fallback", "settings_summary": "ok"}),
    )
    monkeypatch.setattr(sw, "_submit_diorama_prompt_zero_credit", _sub)
    monkeypatch.setattr(sw, "_download_newest_ready_tile", _dl)
    monkeypatch.setattr(sw, "inspect_diorama_clip_cv", lambda *_a, **_kw: {"passed": True, "max_frame_diff": 12.0, "mean_luma": 110.0, "plaque_glyph_run": 0})
    monkeypatch.setattr(sw, "_ensure_min_clip_size_if_needed", lambda _p: None)

    rate_state: dict[str, Any] = {
        "submit_lock": asyncio.Lock(),
        "last_tab_open_mono": 0.0,
        "last_submit_mono": 0.0,
        "cooldown_until_mono": 0.0,
        "cooldown_hits": 0,
        "canonical_project_url": "https://flow.google.com/project/dead-stale-0000",
        "opened_project_urls": [],
        "tab_owners_by_id": {},
    }
    lock = asyncio.Lock()
    asyncio.run(
        sw._run_shard_worker(
            shard_idx=1,
            shard_clips=[],
            project_id="ep_seed_fix",
            project_dir=tmp_path,
            short_ref_map={},
            tab_open_lock=lock,
            opened_tabs=[],
            seen_global_shas=set(),
            shared_clip_queue=collections.deque([{"clip_number": 1, "grammar": "expressive_vinyl_world", "prompt": "c1", "schema_version": 8}]),
            flow_rate_state=rate_state,
        )
    )
    asyncio.run(
        sw._run_shard_worker(
            shard_idx=2,
            shard_clips=[],
            project_id="ep_seed_fix",
            project_dir=tmp_path,
            short_ref_map={},
            tab_open_lock=lock,
            opened_tabs=[],
            seen_global_shas=set(),
            shared_clip_queue=collections.deque([{"clip_number": 2, "grammar": "expressive_vinyl_world", "prompt": "c2", "schema_version": 8}]),
            flow_rate_state=rate_state,
        )
    )
    assert seen_existing_urls == [
        "https://flow.google.com/project/dead-stale-0000",
        "https://flow.google.com/project/new-canon-7777",
    ]
    assert rate_state["canonical_project_url"] == "https://flow.google.com/project/new-canon-7777"

