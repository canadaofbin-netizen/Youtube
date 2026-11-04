from __future__ import annotations

import inspect
import json
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from pipeline.config import (
    DEFAULT_DIORAMA_VOICE_PRESET,
    DIORAMA_V7_PROSODY_MODE,
    DIORAMA_VOICE_PRESETS,
    PRE_R66_FROZEN_PROJECT_PREFIXES,
    SHORTS_THUMB_MAX_BYTES,
)
from pipeline.prompt_quality_v5 import (
    _PRE_R65_ASSEMBLED_DOSSIERS,
    validate_takeaway_bridge_grammar,
)
from pipeline.prosody import evaluate_prosody_gates_on_audio
from pipeline.research_dossier import resolve_dossier_for_project
from pipeline.studio.community import (
    _strip_emojis_and_bullets,
    validate_debate_pinned_comment_line1,
)
from pipeline.studio.config import SLOT_TIMETABLE
from pipeline.studio.queue_manager import StagingQueueManager
from pipeline.studio.studio_watchdog import scan_go_live_transitions
from pipeline.studio.unschedule_retired_shorts import (
    PROTECTED_PUBLIC_VIDEO_IDS,
    RETIRED_LOWPOLY_SCHEDULED_WHITELIST,
    _is_scheduled_visibility_label,
    resolve_retired_projects,
)
from pipeline.studio.us_diorama_timetable import build_us_prime_timetable
from pipeline.thumbnail_studio import _atomic_save_pil_png


def test_phase1_retired_whitelist_and_public_protection():
    all_19 = resolve_retired_projects("diorama_08..26")
    assert len(all_19) == 19
    assert all_19[0] == ("diorama_08_maguire_london_taxi_hippocampus", "4jNxwVMMxQo")
    assert all_19[-1] == ("diorama_26_clark_doll_experiment_bias", "whXcmzZygN8")

    # Zero overlap with the 13 protected Public videos (R34)
    whitelist_vids = {vid for _, vid in all_19}
    assert whitelist_vids.isdisjoint(PROTECTED_PUBLIC_VIDEO_IDS)
    assert len(PROTECTED_PUBLIC_VIDEO_IDS) == 13

    for pub_tok in (
        "diorama_01_hm_lab_B_dynamic",
        "diorama_07_invisible_gorilla_attention",
        "t8Z_Q8oB9MY",
        "psych_01_habit_loop_basal_ganglia",
        "reenact_01_ainsworth_strange_situation",
    ):
        with pytest.raises(ValueError, match="NOT in the 19-item retired Scheduled whitelist"):
            resolve_retired_projects(pub_tok)

    assert _is_scheduled_visibility_label("Scheduled") is True
    assert _is_scheduled_visibility_label("예약됨") is True
    assert _is_scheduled_visibility_label("Public") is False
    assert _is_scheduled_visibility_label("공개") is False
    assert _is_scheduled_visibility_label("") is False


def test_phase1_watchdog_parses_scheduled_time_et_and_verifies_video_id_match(tmp_path: Path):
    proj_dir = tmp_path / "projects"
    pub = proj_dir / "diorama_08_regenerated" / "06_publish"
    pub.mkdir(parents=True)
    # uploader.py writes `scheduled_time_et` (without `scheduled_at_utc`)
    (pub / "upload_receipt.json").write_text(
        json.dumps(
            {
                "video_id": "NewPorcVid8",
                "visibility": "scheduled",
                "status": "scheduled",
                "scheduled_time_et": "2026-11-04 19:30",
            }
        ),
        encoding="utf-8",
    )
    # Stale receipts from a retired video_id must NOT count as pinned/linked for NewPorcVid8
    (pub / "community_receipt.json").write_text(
        json.dumps({"video_id": "4jNxwVMMxQo", "status": "pinned"}),
        encoding="utf-8",
    )
    (pub / "related_video_receipt.json").write_text(
        json.dumps({"video_id": "4jNxwVMMxQo", "verified": True}),
        encoding="utf-8",
    )

    # Before 2026-11-04 19:30 EST (= 2026-11-05 00:30 UTC): still scheduled
    before = datetime(2026, 11, 5, 0, 15, tzinfo=timezone.utc)
    scan_before = scan_go_live_transitions(projects_dir=proj_dir, now_utc=before)
    assert scan_before["scheduled_count"] == 1
    assert scan_before["due_for_public_transition"] == []

    # After 2026-11-05 00:30 UTC: elapsed -> due for public transition AND flagged for missing pin & link
    after = datetime(2026, 11, 5, 0, 45, tzinfo=timezone.utc)
    scan_after = scan_go_live_transitions(projects_dir=proj_dir, now_utc=after)
    assert [x["project_id"] for x in scan_after["due_for_public_transition"]] == ["diorama_08_regenerated"]
    assert [x["project_id"] for x in scan_after["missing_doi_pin"]] == ["diorama_08_regenerated"]
    assert [x["project_id"] for x in scan_after["missing_related_link"]] == ["diorama_08_regenerated"]


def test_phase2_global_emma_us_v7_defaults_and_unfrozen_08_26():
    assert DEFAULT_DIORAMA_VOICE_PRESET == "emma_v7"
    assert DIORAMA_VOICE_PRESETS["emma_v7"]["pitch"] == "+0Hz"
    assert DIORAMA_V7_PROSODY_MODE == "dynamic_us_v7"
    assert SHORTS_THUMB_MAX_BYTES == 1_950_000

    for i in range(1, 8):
        assert any(f"diorama_{i:02d}_case".startswith(p) for p in PRE_R66_FROZEN_PROJECT_PREFIXES)
    for i in range(8, 27):
        assert not any(f"diorama_{i:02d}_case".startswith(p) for p in PRE_R66_FROZEN_PROJECT_PREFIXES)

    for retired_slug in (
        "maguire_london_taxi_hippocampus",
        "broca_patient_tan_speech_loss",
        "olds_milner_pleasure_center",
        "blindsight_subcortical_vision",
        "asch_conformity_pressure",
        "rizzolatti_mirror_neuron_empathy",
    ):
        assert retired_slug not in _PRE_R65_ASSEMBLED_DOSSIERS


def test_phase2_flow_worker_fail_closed_and_track_a_no_silent_fallback():
    import pipeline.flow_diorama_sharded_worker as fw
    import pipeline.porcelain_anchor_pack as pap
    import pipeline.source_reenactment as sr

    fw_src = inspect.getsource(fw)
    assert "lite_supports_ref = False" not in fw_src
    assert '"reference_attached":' in fw_src

    pap_src = inspect.getsource(pap.ensure_porcelain_reference_pack)
    assert "falling back to Track B" not in pap_src

    sr_src = inspect.getsource(sr.translate_porcelain_keyframes_async)
    assert "guide_cand in cond_paths" in sr_src


def test_phase2_voice_hard_lock_and_acoustic_p3_gear_tempo(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import pipeline.prosody as prosody_mod
    import pipeline.voice_fallback as vf

    def _raise_edge(*_a, **_kw):
        raise RuntimeError("edge-tts transient outage")

    monkeypatch.setattr(vf, "_synthesize_edge_tts_acts", _raise_edge)
    with pytest.raises(RuntimeError, match="allow_kokoro_fallback=False"):
        vf.synthesize_continuous_diorama_track(
            tmp_path / "fail_proj",
            ["Testing fail-closed voice synthesis."],
            voice_preset="emma_v7",
            allow_kokoro_fallback=False,
        )

    # Build a synthetic prosody project to test P3_gear_tempo enforcement
    p_dir = tmp_path / "proj_p3"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "04_audio").mkdir(parents=True)
    sents = [
        "Your brain erases half the room right now!",
        "Yet you swear your vision is complete.",
        "Inside Harvard's 1999 lab, Daniel Simons tested why.",
        "Volunteers counted basketball passes across the court.",
        "How did half miss a gorilla?",
        "Attention gates visual cortex like a spotlight.",
        "So the next time you drive, scan twice.",
    ]
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"sentences": sents, "prosody_mode": "dynamic_us_v7", "voice_preset": "emma_v7"}),
        encoding="utf-8",
    )
    import wave

    wav_path = p_dir / "04_audio" / "audio_master.wav"
    sr_hz = 24000
    t = np.linspace(0, 14.0, sr_hz * 14, endpoint=False)
    tone = (0.12 * np.sin(2 * np.pi * 220 * t) * 32767).astype(np.int16)
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr_hz)
        wf.writeframes(tone.tobytes())

    spans = [
        {"sentence_index": idx + 1, "start_sec": idx * 2.0, "end_sec": idx * 2.0 + 1.8, "text": s}
        for idx, s in enumerate(sents)
    ]
    rows = [
        {
            "sentence_index": idx + 1,
            "gear": "rush" if idx < 2 else ("stamp" if idx in (2, 6) else "brisk"),
            "words": len(s.split()),
            "wpm": 180.0,
            "native_gear_synth": True,
            "wsola_factor": 1.0,
        }
        for idx, s in enumerate(sents)
    ]
    # Case A: Kokoro engine rejected by P3_gear_tempo
    (p_dir / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "kokoro_onnx",
                "sentence_spans": spans,
                "total_duration_sec": 145.0,
                "speech_end_sec": 142.0,
                "true_rms_voiced_ratio": 0.72,
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "04_audio" / "prosody_report.json").write_text(
        json.dumps(
            {
                "prosody_mode": "dynamic_us_v7",
                "native_gear_synthesis": True,
                "sentences": rows,
            }
        ),
        encoding="utf-8",
    )
    rep_kokoro = evaluate_prosody_gates_on_audio(p_dir, run_asr=False)
    assert rep_kokoro["gates"]["P3_gear_tempo"]["passed"] is False
    assert rep_kokoro["gates"]["P3_gear_tempo"]["engine_ok"] is False

    # Case B: Flat zero-spread acoustic wps/wpm rejected in dynamic mode even with edge_tts
    (p_dir / "04_audio" / "voice_report.json").write_text(
        json.dumps(
            {
                "engine": "edge_tts",
                "sentence_spans": [
                    {"sentence_index": idx + 1, "start_sec": idx * 4.0, "end_sec": idx * 4.0 + len(s.split()) / 2.5, "text": s}
                    for idx, s in enumerate(sents)
                ],
                "total_duration_sec": 145.0,
                "speech_end_sec": 142.0,
                "true_rms_voiced_ratio": 0.72,
            }
        ),
        encoding="utf-8",
    )
    rep_flat = evaluate_prosody_gates_on_audio(p_dir, run_asr=False)
    assert rep_flat["gates"]["P3_gear_tempo"]["passed"] is False
    assert prosody_mod is not None


def test_phase2_thumbnail_sub_195mb_and_community_markdown_sanitizer(tmp_path: Path):
    # High-entropy noisy RGB image that exceeds 2 MB as raw 24-bit PNG must be auto-compressed <= 1.95 MB
    rng = np.random.default_rng(42)
    noisy = rng.integers(0, 256, size=(1920, 1080, 3), dtype=np.uint8)
    img = Image.fromarray(noisy, mode="RGB")
    out_png = tmp_path / "dense_thumb.png"
    _atomic_save_pil_png(img, out_png, max_bytes=SHORTS_THUMB_MAX_BYTES)
    assert out_png.exists()
    assert out_png.stat().st_size <= SHORTS_THUMB_MAX_BYTES

    # Community markdown & (SRCn) stripping + validator
    dirty = "Researchers tested **fifty-six** infants (`12 months`) in [Baltimore](https://example.com) (SRC2)."
    cleaned = _strip_emojis_and_bullets(dirty)
    assert "**" not in cleaned
    assert "`" not in cleaned
    assert "SRC2" not in cleaned
    assert "https://example.com" not in cleaned
    assert "fifty-six infants (12 months) in Baltimore." in cleaned

    md_issues = validate_debate_pinned_comment_line1(
        "My bet: wiring wins — is **silent** panic learned?",
        "My bet: wiring wins — is **silent** panic learned?\n\nBody (SRC2)\nSource: https://doi.org/10.2307/1127388",
    )
    assert any("debate_markdown_residue" in x for x in md_issues)


def test_phase2_explicit_slug_map_and_takeaway_bridge_grammar():
    assert resolve_dossier_for_project("diorama_14_libet_readiness_potential").name == "libet_readiness_potential_free_will"
    assert resolve_dossier_for_project("diorama_20_dutton_aron_capilano_bridge").name == "dutton_aron_capilano_bridge_arousal"
    assert resolve_dossier_for_project("diorama_21_delgado_stimoceiver_bull").name == "delgado_stimoceiver_bull_stop"

    bad_takeaways = [
        "So the next time your brain does not store life in one giant bucket.",
        "So the next time willpower is overrated; designing an out-of-sight environment wins faster.",
        "Every human brain shares healthy movement depends on a silent sensorLoop running faster than thought.",
        "And that is how your brain your brain tags rewards by surprise, not size.",
        "Your own brain still carries you only ever see a tiny spotlight of the world.",
        "That biological lesson explains waiting for calm to act works backward in the brain.",
    ]
    for bad in bad_takeaways:
        assert validate_takeaway_bridge_grammar(bad), f"Expected grammar failure on: {bad}"

    good_takeaways = [
        "So the next time you study late, split heavy notes into short chunks.",
        "Every human brain shares that silent predictive loop beneath conscious movement.",
        "And that is how your brain tags daily rewards by surprise rather than size.",
        "Your own brain still carries this narrow visual spotlight on busy streets.",
        "That biological lesson explains why hiding tempting cues beats raw willpower every night.",
    ]
    for good in good_takeaways:
        assert validate_takeaway_bridge_grammar(good) == [], f"Unexpected grammar issue on: {good}"


def test_phase3_one_short_per_day_1930_est_scheduler(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    assert SLOT_TIMETABLE[4]["time_et"] == "19:30"

    qm = StagingQueueManager(projects_dir=tmp_path / "projects", queue_file=tmp_path / "queue.json")
    mock_projects = [
        {"project_id": f"diorama_{30 + i}_ep", "pillar": "brain_health", "title": f"Ep {i}", "recommended_slot": 4}
        for i in range(5)
    ]
    monkeypatch.setattr(qm, "scan_ready_projects", lambda **kw: list(mock_projects))
    plan = qm.plan_5_slot_schedule(days=5, start_date="2026-11-05")
    items = plan["items"]
    assert len(items) == 5
    dates = [item["date"] for item in items]
    assert len(set(dates)) == 5  # Strictly 1 Short per day!
    assert all(item["slot_id"] == 4 and item["time_et"] == "19:30" for item in items)

    # US prime timetable across 7 days (including Sunday) must schedule exactly 7 Shorts at 19:30 EST
    # and NEVER spill a Short into Sunday's 09:30 EST longform_4k slot!
    eps = [
        {"project_id": f"diorama_{40 + i}_ep", "pillar": "brain_health", "format_profile": "neuro_diorama"}
        for i in range(10)
    ]
    tt = build_us_prime_timetable(eps, start_date="2026-11-04", days=7)
    short_slots = [s for s in tt["slots"] if s["preferred_format"] == "neuro_diorama"]
    lf_slots = [s for s in tt["slots"] if s["preferred_format"] == "longform_4k"]
    assert len(short_slots) == 7
    assert [s["date"] for s in short_slots] == [
        "2026-11-04",
        "2026-11-05",
        "2026-11-06",
        "2026-11-07",
        "2026-11-08",
        "2026-11-09",
        "2026-11-10",
    ]
    assert all(s["slot_code"].endswith("_PRIME") and s["time_et"] == "19:30" and s["tz_abbr"] == "EST" for s in short_slots)
    assert all(s["project_id"] is not None for s in short_slots)
    assert len(lf_slots) == 1
    assert lf_slots[0]["weekday"] == "Sun" and lf_slots[0]["time_et"] == "09:30"
    assert lf_slots[0]["project_id"] is None


def test_prosody_asr_tokens_and_daily_30_specs():
    from pipeline.diorama_batch_orchestrator import DIORAMA_DAILY_30_SPECS
    from pipeline.prosody import _asr_tokens

    assert _asr_tokens("drivers map 25 000 streets") == _asr_tokens("drivers map twenty-five thousand streets")
    assert _asr_tokens("in 2000 dr eleanor maguire") == _asr_tokens("In two thousand, Doctor Eleanor Maguire")
    assert len(DIORAMA_DAILY_30_SPECS) == 30
    assert sorted({int(s["wave"]) for s in DIORAMA_DAILY_30_SPECS}) == [1, 2, 3, 4, 5, 6]
    assert len({s["project_id"] for s in DIORAMA_DAILY_30_SPECS}) == 30
    assert len({s["slug"] for s in DIORAMA_DAILY_30_SPECS}) == 30


def test_reviewer_regressions_provenance_dq6_heal_and_preflight_qa(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import cv2

    import pipeline.diorama_batch_orchestrator as dbo
    import pipeline.flow_diorama_sharded_worker as fw
    from pipeline.porcelain_anchor_pack import sanitize_porcelain_contract_text
    from pipeline.qa_gates import run_preflight_qa
    from pipeline.thumbnail_studio import _has_head_occlusion_in_hook_band, run_thumbnail_qa

    # 1. Stage-1 preflight QA must pass with emma_v7 + dynamic_us_v7 SSOT lock
    s1 = run_preflight_qa(require_live_cdp=False)
    assert s1["passed"] is True, f"Stage 1 preflight QA failed: {s1}"

    # 2. _persist_receipt_snapshot source must preserve reference_image + reference_attached (never strip them!)
    fn_src = inspect.getsource(fw.run_sharded_diorama_flow_generation)
    persist_slice = fn_src.split("def _persist_receipt_snapshot", 1)[1]
    assert '"reference_image": req_ref_rel' in persist_slice
    assert '"reference_attached": ref_att_val' in persist_slice

    # 3. _collect_auto_heal_plan must read DQ6_zero_clip_reuse["unattached_reference_clips"]
    monkeypatch.setattr(dbo, "PROJECTS_DIR", tmp_path)
    p_dir = tmp_path / "diorama_08_test_heal"
    (p_dir / "03_visuals").mkdir(parents=True)
    (p_dir / "05_assembly").mkdir(parents=True)
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"schema_version": 7, "style_profile": "porcelain_cinematic_v7", "clips": []}),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edl.json").write_text(json.dumps({"cuts": []}), encoding="utf-8")
    (p_dir / "05_assembly" / "dynamic_episode_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "gates": {
                    "DQ6_zero_clip_reuse": {
                        "passed": False,
                        "unattached_reference_clips": [4, 17],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    heal = dbo._collect_auto_heal_plan("diorama_08_test_heal")
    assert heal["regenerate_clips"] == [4, 17]

    # 4. TQ8 + _has_head_occlusion_in_hook_band: 1-line (cy=340) & 2-line (cy=460) decapitations fail, seated (cy=540) passes
    def _make_porcelain_frame(head_cy: int, color_shift: int = 0) -> np.ndarray:
        frame = np.full((1920, 1080, 3), (175 + color_shift, 200, 215), dtype=np.uint8)
        cv2.ellipse(frame, (540, head_cy), (55, 68), 0, 0, 360, (238, 240, 242), -1)
        cv2.rectangle(frame, (455, head_cy + 75), (625, head_cy + 280), (80, 135, 185), -1)
        return frame

    assert _has_head_occlusion_in_hook_band(_make_porcelain_frame(340), "porcelain_fullbleed_world") is True
    assert _has_head_occlusion_in_hook_band(_make_porcelain_frame(460), "porcelain_fullbleed_world") is True
    assert _has_head_occlusion_in_hook_band(_make_porcelain_frame(540), "porcelain_fullbleed_world") is False

    # 2-line hook bbox [120, 272, 960, 502] must fail TQ8 when head is at cy=460, and pass when seated at cy=540
    def _mk_var(frame: np.ndarray, bbox: list[int]) -> dict:
        return {
            "clean_bgr": frame,
            "rendered_bgr": frame,
            "grammar": "porcelain_fullbleed_world",
            "text_bbox": bbox,
            "text_contrast_wcag": 12.0,
            "raw_metrics": {"center_salience": 0.45, "sharpness": 120.0, "contrast": 42.0},
            "file_bytes": 450_000,
            "dimensions": [1080, 1920],
        }

    qa_decap = run_thumbnail_qa(
        {
            "A": _mk_var(_make_porcelain_frame(460, 0), [120, 272, 960, 502]),
            "B": _mk_var(_make_porcelain_frame(540, 10), [120, 272, 960, 502]),
            "C": _mk_var(_make_porcelain_frame(540, -10), [120, 272, 960, 502]),
        },
        hook="STRANGE SITUATION",
        title="The Baby Test That Mapped Attachment",
    )
    assert qa_decap["gates"]["TQ8_zero_head_occlusion"]["passed"] is False
    assert qa_decap["gates"]["TQ8_zero_head_occlusion"]["head_occlusion_by_variant"] == {
        "A": True,
        "B": False,
        "C": False,
    }

    # 5. sanitize_porcelain_contract_text idempotence across 5 consecutive passes
    sample = "Experimenter flips a playing card beside a chalkboard, ledger, chart, and textbook."
    once = sanitize_porcelain_contract_text(sample)
    five = once
    for _ in range(4):
        five = sanitize_porcelain_contract_text(five)
    assert five == once
    assert "blank matte blank matte" not in five.lower()
    assert "unmarked paper unmarked paper" not in five.lower()


def test_reviewer_stale_receipt_video_id_mismatch_in_linker_and_community(tmp_path: Path):
    from pipeline.studio.community import CommunityManager
    from pipeline.studio.short_linker import ShortLinkGraph, write_studio_publish_receipt

    projects_root = tmp_path / "projects"
    p_dir = projects_root / "diorama_08_regenerated"
    (p_dir / "00_project_manifest.json").parent.mkdir(parents=True, exist_ok=True)
    (p_dir / "00_project_manifest.json").write_text(
        json.dumps({"project_id": "diorama_08_regenerated", "pillar": "brain_health", "stages": {}}),
        encoding="utf-8",
    )
    pub = p_dir / "06_publish"
    pub.mkdir(parents=True, exist_ok=True)
    (pub / "metadata.json").write_text(
        json.dumps(
            {
                "title": "London Taxi Drivers Grew Bigger Memory Maps",
                "pillar": "brain_health",
                "primary_doi": "10.1073/pnas.070039597",
                "offcenter_creator_bet": "My bet: GPS quietly shrinks our mental map — do you still navigate without turn-by-turn prompts?",
            }
        ),
        encoding="utf-8",
    )
    (pub / "upload_receipt.json").write_text(
        json.dumps({"video_id": "NewPorcVid8", "visibility": "public", "status": "published_public"}),
        encoding="utf-8",
    )
    # Stale receipts left over from retired video ID `4jNxwVMMxQo`
    (pub / "related_video_receipt.json").write_text(
        json.dumps(
            {
                "source_video_id": "4jNxwVMMxQo",
                "target_video_id": "t8Z_Q8oB9MY",
                "verified": True,
                "playlist_verified": True,
                "playlist_title": "Brain Health",
            }
        ),
        encoding="utf-8",
    )
    (pub / "community_receipt.json").write_text(
        json.dumps({"video_id": "4jNxwVMMxQo", "pinned": True, "status": "pinned"}),
        encoding="utf-8",
    )

    graph = ShortLinkGraph(projects_dir=projects_root)
    nodes = graph.discover_nodes()
    assert len(nodes) == 1
    assert nodes[0]["video_id"] == "NewPorcVid8"
    assert nodes[0]["existing_target_video_id"] == ""
    assert nodes[0]["existing_playlist_verified"] is False

    cons_path = write_studio_publish_receipt("diorama_08_regenerated", projects_dir=projects_root)
    cons = json.loads(cons_path.read_text(encoding="utf-8"))
    assert cons["stage_5_complete"] is False
    assert cons["related_video"]["linked"] is False
    assert cons["community_pin"]["pinned"] is False

    cm = CommunityManager(projects_dir=projects_root)
    pin_res = cm.pin_all_public_unpinned(dry_run=True)
    assert len(pin_res["results"]) == 1
    assert pin_res["results"][0]["status"] != "already_pinned"


