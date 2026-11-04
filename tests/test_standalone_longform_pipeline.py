"""
Comprehensive Integration & Edge-Case Tests for:
  - Workstream B: 3-Stage Comment Debate Ignition (`validate_debate_pinned_comment_line1`,
    `_TOPIC_PACKAGES` / `_DIORAMA_NATURAL_PACKAGES`, `CommunityManager` Long-Form support,
    `StudioAnalyticsReporter._parse_video_row_text` multiline parsing)
  - Workstream C: Standalone `16:9` (`1920x1080 @ 24fps`, `-14.0 LUFS`, `longform_us_v7`) Long-Form Pipeline
    (`longform_prompt_builder`, `longform_subtitles`, `longform_audio`, `longform_refs`,
    `longform_flow_worker`, `longform_assembler`, `longform_publish`, `longform_qa`, `news_radar`)
"""

from __future__ import annotations

import json
import math
import wave
from pathlib import Path

import cv2
import numpy as np
import pytest

from pipeline import config
from pipeline.longform_assembler import assemble_longform_episode
from pipeline.longform_audio import synthesize_longform_master_audio
from pipeline.longform_flow_worker import inspect_longform_16x9_clip_cv, run_longform_sharded_flow_generation
from pipeline.longform_prompt_builder import (
    build_flow_shards,
    build_longform_16x9_flow_prompt,
    initialize_longform_project,
    plan_relaxed_cuts_for_sentences,
    resolve_longform_project_dir,
    sanitize_longform_scene_props,
)
from pipeline.longform_publish import prepare_longform_publish_package
from pipeline.longform_qa import run_longform_qa
from pipeline.longform_refs import (
    build_longform_reference_specs,
    inspect_longform_reference_pack,
    purge_longform_quarantine,
    sanitize_longform_16x9_guide_frame,
)
from pipeline.longform_subtitles import (
    build_longform_subtitles_ass,
    chunk_timed_words_for_longform,
    render_subtitle_citation_preview_frame,
)
from pipeline.news_radar import EVERYDAY_PSYCH_NEURO_QUERIES, classify_everyday_domain
from pipeline.studio.community import (
    _DIORAMA_NATURAL_PACKAGES,
    CommunityManager,
    validate_debate_pinned_comment_line1,
)
from pipeline.studio.reporter import StudioAnalyticsReporter


def _build_valid_episode_spec(word_scale: int = 1) -> dict:
    """Builds a valid 7-chapter Long-Form episode spec with flowing <= 22-word sentences and 3+ DOIs."""
    base_chapters = []
    for ch_i in range(1, 8):
        sents = [
            {
                "text": "Every exhausted sleeper stares at the ceiling while the darkened bedroom quietly triggers wide-awake cortical alertness.",
                "gear": "rush" if ch_i == 1 else "explain",
                "citation_id": "cite_perlis_1997" if ch_i == 2 else None,
            },
            {
                "text": "When deep slow-wave sleep begins, fluid channels between brain cells expand by sixty percent to clear metabolic waste.",
                "gear": "explain",
                "citation_id": "cite_xie_2013" if ch_i == 3 else ("cite_fultz_2019" if ch_i == 4 else None),
            },
            {
                "text": (
                    "Could a sleeping pill knock out consciousness for eight hours while quietly starving the brain's nightly fluid pump?"
                    if ch_i == 4
                    else (
                        "Would you choose five hours of natural slow-wave sleep or eight sedated hours on a sleeping pill?"
                        if ch_i == 7
                        else "Natural norepinephrine waves pulse every twenty seconds during non-REM sleep to drive fresh cerebrospinal fluid inward."
                    )
                ),
                "gear": "stamp",
                "beat_break": True,
                "citation_id": "cite_hauglund_2025" if ch_i == 5 else None,
            },
        ]
        if word_scale > 1:
            extra = [
                {
                    "text": "Overnight brain scans reveal that losing just one night of deep rest amplifies emotional amygdala reactivity by sixty percent.",
                    "gear": "explain",
                }
                for _ in range(word_scale - 1)
            ]
            sents = sents[:-1] + extra + [sents[-1]]

        base_chapters.append(
            {
                "chapter_number": ch_i,
                "title": f"Mechanism Stage {ch_i}",
                "headline": f"CHAPTER {ch_i} · MECHANISM {ch_i}",
                "sentences": sents,
                "visual_templates": [
                    {
                        "grammar": "porcelain_living_brain" if ch_i in (3, 5) else "porcelain_fullbleed_world",
                        "brain_mode": "sagittal_coronal_cutaway" if ch_i in (3, 5) else None,
                        "anatomy_label": "GLYMPHATIC CHANNELS" if ch_i == 3 else None,
                        "camera": "orbital_3d_arc_sweep" if ch_i in (3, 5) else "gentle_push_in",
                        "anchor_id": "ref_lf_brain_master" if ch_i in (3, 5) else "ref_lf_env_master",
                        "scene": "Minimalist walnut bedroom with a clothed matte-white porcelain figure resting calmly under warm moonlight",
                    }
                ],
            }
        )

    return {
        "dossier_slug": "unit_sleep_glymphatic",
        "title": "Why 8 Hours on Sleeping Pills Leaves Your Brain Unwashed",
        "pillar": "brain_health",
        "everyday_domain": "sleep",
        "voice_preset": "emma_v7",
        "prosody_mode": "longform_us_v7",
        "primary_doi": "10.1126/science.1241224",
        "offcenter_creator_bet": (
            "My bet: I'd take 5 real hours over pills — sedatives mute the vascular pump that flushes night waste. "
            "Would you choose 5 hours of natural deep sleep or 8 sedated hours?"
        ),
        "three_layer_formula": {
            "everyday_problem": "Pre-dawn insomnia and sleeping-pill reliance",
            "psychology_studies": ["10.1111/j.1365-2869.1997.00179.x", "10.1016/j.cub.2007.08.007"],
            "neuroscience_studies": ["10.1126/science.1241224", "10.1126/science.aax5440", "10.1016/j.cell.2024.11.027"],
        },
        "citation_cards": [
            {
                "citation_id": "cite_perlis_1997",
                "year": "1997",
                "journal": "J. Sleep Research",
                "doi": "10.1111/j.1365-2869.1997.00179.x",
                "authors": "Perlis et al.",
                "finding": "Conditioned bedroom beta cortical arousal in chronic insomnia",
            },
            {
                "citation_id": "cite_xie_2013",
                "year": "2013",
                "journal": "Science",
                "doi": "10.1126/science.1241224",
                "authors": "Xie & Nedergaard",
                "finding": "Interstitial channels expand 60% in sleep to clear beta-amyloid",
            },
            {
                "citation_id": "cite_fultz_2019",
                "year": "2019",
                "journal": "Science",
                "doi": "10.1126/science.aax5440",
                "authors": "Fultz & Lewis",
                "finding": "Coupled 20-second slow waves and CSF fluid pulses in sleeping humans",
            },
            {
                "citation_id": "cite_hauglund_2025",
                "year": "2025",
                "journal": "Cell",
                "doi": "10.1016/j.cell.2024.11.027",
                "authors": "Hauglund & Nedergaard",
                "finding": "Norepinephrine vascular waves drive glymphatic clearance; zolpidem blunts inflow",
            },
        ],
        "thumbnail": {"hook_text": "8 HOURS SEDATED?", "variants": ["A", "B", "C"]},
        "chapters": base_chapters,
    }


# ==============================================================================
# Workstream B: Comment & Debate Paradigm Tests
# ==============================================================================


def test_validate_debate_pinned_comment_line1_boundaries_and_violence_guard():
    good = (
        "My bet: I'd take 5 real hours over pills — sedatives mute the pump. "
        "Would you choose 5 real hours or 8 sedated hours?"
    )
    assert validate_debate_pinned_comment_line1(good, full_comment=good) == []

    # Boundary: creator-bet prefix pushed past first 45 chars must fail
    late_prefix = "An overly verbose academic introduction before My bet: I'd pick option A over B?"
    errs_late = validate_debate_pinned_comment_line1(late_prefix, full_comment=late_prefix)
    assert any("45" in e or "prefix" in e.lower() for e in errs_late)

    # Missing forced-choice '?' must fail
    no_q = "My bet: I'd pick 5 natural hours over 8 sedated hours every single night."
    errs_no_q = validate_debate_pinned_comment_line1(no_q, full_comment=no_q)
    assert any("?" in e or "question" in e.lower() for e in errs_no_q)

    # Banned YouTube comment auto-hold violence words must fail
    violent = "Hot take: sleeping pills kill the night pump — would you ditch them?"
    errs_v = validate_debate_pinned_comment_line1(violent, full_comment=violent)
    assert any("kill" in e.lower() or "banned" in e.lower() for e in errs_v)


def test_all_builtin_debate_packages_pass_line1_validation_and_longform_prepare(tmp_path: Path):
    for slug, pkg in _DIORAMA_NATURAL_PACKAGES.items():
        bet = pkg.get("question", "")
        assert bet, f"Missing question on {slug}"
        line1 = bet.splitlines()[0].strip()
        assert validate_debate_pinned_comment_line1(line1, full_comment=bet) == [], f"Failed on {slug}: {bet}"

    cm_real = CommunityManager()
    for pid in ("psych_01", "psych_02", "psych_03", "psych_05", "psych_06"):
        pkg_res = cm_real.prepare_comment_content(pid)
        line1 = pkg_res["comment_text"].splitlines()[0].strip()
        assert validate_debate_pinned_comment_line1(line1, full_comment=pkg_res["comment_text"]) == [], f"Failed on {pid}: {line1}"

    lf_root = tmp_path / "projects_longform"
    initialize_longform_project("longform_91_comment_check", _build_valid_episode_spec(), projects_longform_dir=lf_root)
    cm = CommunityManager(projects_dir=lf_root)
    prepared = cm.prepare_comment_content("longform_91_comment_check")
    first_ln = prepared["comment_text"].splitlines()[0].strip()
    assert validate_debate_pinned_comment_line1(first_ln, full_comment=prepared["comment_text"]) == []
    assert "10.1126/science.1241224" in prepared["comment_text"]


def test_reporter_multiline_video_row_comment_parsing_and_zero_preserved():
    multiline_row = (
        "Why Your Brain Wakes at 3 AM\n"
        "Public\n"
        "Nov 3, 2026\n"
        "Published\n"
        "1,842\n"
        "9\n"
        "96.4%"
    )
    parsed = StudioAnalyticsReporter._parse_video_row_text(multiline_row)
    assert parsed["views"] == 1842
    assert parsed["comments"] == 9

    zero_row = "Fresh Upload Title\nPublic\nNov 4, 2026\nPublished\n215\n0\n98.0%"
    parsed_zero = StudioAnalyticsReporter._parse_video_row_text(zero_row)
    assert parsed_zero["views"] == 215
    assert parsed_zero["comments"] == 0


# ==============================================================================
# Workstream C: Standalone 16:9 (1920x1080) Long-Form Pipeline Tests
# ==============================================================================


def test_longform_constants_and_strict_shorts_isolation(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    # Verify Long-Form 1080p + relaxed items #1, #2, #4
    assert (config.LONGFORM_VIDEO_WIDTH, config.LONGFORM_VIDEO_HEIGHT) == (1920, 1080)
    assert config.LONGFORM_VIDEO_FPS == 24
    assert config.LONGFORM_PROSODY_MODE == "longform_us_v7"
    assert config.LONGFORM_PROSODY_GEAR_RATES == {"rush": "+4%", "explain": "+0%", "brisk": "+0%", "stamp": "-2%"}
    assert config.LONGFORM_INTER_SENTENCE_PAUSE_SEC == pytest.approx(0.25)
    assert config.LONGFORM_BEAT_PAUSE_SEC == pytest.approx(0.45)
    assert config.LONGFORM_CHAPTER_PAUSE_SEC == pytest.approx(0.92)
    assert config.LONGFORM_MAX_SENTENCE_WORDS == 22
    assert (config.LONGFORM_MIN_CUT_SEC, config.LONGFORM_AVG_CUT_TARGET_SEC, config.LONGFORM_MAX_CUT_SEC) == (3.2, 5.0, 7.0)

    # Verify Shorts constants are 100% untouched
    assert (config.VIDEO_WIDTH, config.VIDEO_HEIGHT) == (1080, 1920)
    assert config.DIORAMA_V7_US_PROSODY_MODE == "dynamic_us_v7"
    assert config.DIORAMA_US_SENTENCE_WORDS_MAX == 13

    shorts_dir = tmp_path / "projects"
    lf_dir = tmp_path / "projects_longform"
    shorts_dir.mkdir()
    monkeypatch.setattr(config, "PROJECTS_DIR", str(shorts_dir))
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))

    resolved = resolve_longform_project_dir("longform_01_iso", create=True)
    assert resolved == lf_dir / "longform_01_iso"
    assert (resolved / "02_script").is_dir()
    assert list(shorts_dir.iterdir()) == []


def test_scene_prop_sanitizer_and_relaxed_cut_planner_edge_cases():
    dirty = (
        "A sleeper glances at glowing red numbers on a digital alarm clock at 3:00 AM "
        "beside a prescription bottle with label, a wall calendar, and a scoreboard plaque."
    )
    cleaned = sanitize_longform_scene_props(dirty)
    low = cleaned.lower()
    for banned in ("alarm clock", "3:00", "3 am", "prescription bottle with label", "calendar", "scoreboard", "plaque"):
        assert banned not in low

    prompt = build_longform_16x9_flow_prompt({"grammar": "porcelain_living_brain", "scene": dirty, "camera": "orbital_3d_arc_sweep"})
    assert "16:9 horizontal widescreen" in prompt
    assert "alarm clock" not in prompt.lower()

    # Edge cases in plan_relaxed_cuts_for_sentences:
    # - short pair (1.9s + 2.1s -> 4.0s)
    # - normal hold (5.2s)
    # - ultra-long sentence (11.4s -> multi-angle split)
    # - trailing < 3.2s orphan (1.5s -> rebalanced cleanly into [3.2, 7.0])
    sents = [
        {"sentence_index": 1, "chapter": 1, "est_duration_sec": 1.9},
        {"sentence_index": 2, "chapter": 1, "est_duration_sec": 2.1},
        {"sentence_index": 3, "chapter": 1, "est_duration_sec": 5.2},
        {"sentence_index": 4, "chapter": 1, "est_duration_sec": 11.4},
        {"sentence_index": 5, "chapter": 1, "est_duration_sec": 1.5},
    ]
    clips = plan_relaxed_cuts_for_sentences(sents, {})
    assert len(clips) >= 4
    for idx, c in enumerate(clips):
        dur = c["target_duration_sec"]
        assert 3.2 <= dur <= 7.0, f"Clip {c['clip_number']} duration {dur} out of [3.2, 7.0]"
        if idx > 0:
            assert c["start_sec"] == pytest.approx(clips[idx - 1]["end_sec"], abs=0.01)
    assert clips[-1]["end_sec"] == pytest.approx(sum(s["est_duration_sec"] for s in sents), abs=0.05)

    shards = build_flow_shards(clips * 5, max_per_shard=14)
    assert all(sh["clip_count"] <= 14 for sh in shards)


def test_subtitles_chunking_citation_card_clearance_and_preview_frame(tmp_path: Path):
    assert chunk_timed_words_for_longform([]) == []
    single = chunk_timed_words_for_longform([{"word": "Sleep.", "start": 0.0, "end": 0.6}])
    assert len(single) == 1 and single[0]["text"] == "Sleep."

    # 20-word flowing documentary sentence + long hyphenated compound
    words_20 = (
        "During natural slow-wave sleep, norepinephrine-driven arterial pulsations push "
        "fresh cerebrospinal fluid through expanded perivascular channels across the human cortex."
    ).split()
    timed = [{"word": w, "start": i * 0.32, "end": (i + 1) * 0.32} for i, w in enumerate(words_20)]
    bursts = chunk_timed_words_for_longform(timed)
    assert bursts
    for b in bursts:
        assert b["word_count"] <= 5
        assert b["char_count"] <= 32

    lf_root = tmp_path / "projects_longform"
    initialize_longform_project("longform_92_subs", _build_valid_episode_spec(), projects_longform_dir=lf_root)
    p_dir = lf_root / "longform_92_subs"
    s_doc = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    vp_doc = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))

    # Synthesize deterministic word timings across sentences so citation cards activate
    t_cur = 0.0
    s_timings = []
    for s in s_doc["sentences"]:
        toks = s["text"].split()
        w_list = [{"word": tok, "start": t_cur + k * 0.30, "end": t_cur + (k + 1) * 0.30} for k, tok in enumerate(toks)]
        s_end = t_cur + len(toks) * 0.30
        s_timings.append(
            {
                "sentence_index": s["sentence_index"],
                "chapter": s["chapter"],
                "text": s["text"],
                "citation_id": s.get("citation_id"),
                "start_sec": round(t_cur, 3),
                "end_sec": round(s_end, 3),
                "words": w_list,
            }
        )
        t_cur = s_end + 0.45

    ass_rep = build_longform_subtitles_ass(
        p_dir,
        sentence_timings=s_timings,
        total_duration_sec=t_cur + 3.0,
        script_doc=s_doc,
        visual_plan=vp_doc,
    )
    assert ass_rep["play_res"] == [1920, 1080]
    assert ass_rep["citation_card_count"] == 4
    assert ass_rep["min_vertical_clearance_px"] >= 50

    prev_rep = render_subtitle_citation_preview_frame(p_dir)
    assert Path(prev_rep["preview_png"]).exists()
    assert prev_rep["resolution"] == [1920, 1080]
    assert prev_rep["card_roi_active_ratio"] > 0.01
    assert prev_rep["subtitle_roi_active_ratio"] > 0.005
    assert prev_rep["clearance_gap_band_dirty_ratio"] == 0.0
    assert prev_rep["non_overlapping_verified"] is True


def test_longform_relaxed_audio_kokoro_synthesis_and_natural_pauses(tmp_path: Path):
    lf_root = tmp_path / "projects_longform"
    # Compact 2-chapter spec for fast offline Kokoro synthesis check
    spec = _build_valid_episode_spec()
    spec["chapters"] = spec["chapters"][:2]
    spec["chapters"][0]["sentences"] = spec["chapters"][0]["sentences"][:2]
    spec["chapters"][1]["sentences"] = spec["chapters"][1]["sentences"][:2]
    initialize_longform_project("longform_93_audio", spec, projects_longform_dir=lf_root)
    p_dir = lf_root / "longform_93_audio"

    rep = synthesize_longform_master_audio(p_dir, voice_preset="emma_v7", engine="kokoro")
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    assert wav_path.exists() and wav_path.stat().st_size > 100_000
    assert ass_path.exists()
    assert rep["prosody_mode"] == "longform_us_v7"
    assert rep["max_wsola_stretch_delta"] == 0.0
    assert abs(rep["integrated_lufs"] - (-14.0)) <= 1.2
    assert rep["true_peak_dbtp"] <= -1.2

    wt_doc = json.loads((p_dir / "04_audio" / "word_timestamps.json").read_text(encoding="utf-8"))
    timings = wt_doc["sentences"]
    # Sentence 1 (rush in Ch 1) -> ~0.22s pause; Sentence 2 (end of Ch 1) -> ~0.92s chapter pause
    assert timings[0]["pause_after_sec"] == pytest.approx(config.LONGFORM_RUSH_PAUSE_SEC, abs=0.02)
    assert timings[1]["pause_after_sec"] == pytest.approx(config.LONGFORM_CHAPTER_PAUSE_SEC, abs=0.02)

    with wave.open(str(wav_path), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getframerate() == 48000


def test_track_a_guide_sanitizer_quarantine_purge_and_16x9_clip_cv_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    q_root = tmp_path / "quarantine_lf"
    monkeypatch.setattr(config, "LONGFORM_QUARANTINE_ROOT", str(q_root))
    import pipeline.longform_refs as lf_refs

    monkeypatch.setattr(lf_refs, "LONGFORM_QUARANTINE_ROOT", str(q_root))

    src = np.full((720, 1280, 3), (120, 150, 190), dtype=np.uint8)
    cv2.rectangle(src, (200, 140), (600, 560), (210, 215, 220), -1)
    guide_png = q_root / "unit_slug" / "guide_01.png"
    g_rep = sanitize_longform_16x9_guide_frame(src, guide_png)
    assert guide_png.exists()
    assert len(g_rep["source_dhash_64"]) == 16
    guide_im = cv2.imread(str(guide_png))
    assert (guide_im.shape[1], guide_im.shape[0]) == (1920, 1080)

    p_rep = purge_longform_quarantine("unit_slug")
    assert p_rep["purged"] is True
    assert not guide_png.exists()

    # CV clip gate: reject 9:16 vertical clip, pass clean moving 16:9 clip
    vert_mp4 = tmp_path / "bad_9x16.mp4"
    vw = cv2.VideoWriter(str(vert_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (360, 640))
    for i in range(84):
        frm = np.full((640, 360, 3), 215, dtype=np.uint8)
        cv2.circle(frm, (180, 120 + i * 4), 40, (90, 120, 150), -1)
        vw.write(frm)
    vw.release()
    assert inspect_longform_16x9_clip_cv(vert_mp4)["passed"] is False

    land_mp4 = tmp_path / "good_16x9.mp4"
    lw = cv2.VideoWriter(str(land_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (640, 360))
    for i in range(88):
        frm = np.full((360, 640, 3), (222, 226, 230), dtype=np.uint8)
        cv2.circle(frm, (120 + i * 4, 180), 48, (180, 140, 75), -1)
        lw.write(frm)
    lw.release()
    good_cv = inspect_longform_16x9_clip_cv(land_mp4, min_duration_sec=3.2)
    assert good_cv["passed"] is True, f"Unexpected CV failure: {good_cv}"


def test_end_to_end_1080p_assembly_split_hstack_publish_and_lfq1_to_lfq12(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    shorts_dir = tmp_path / "projects"
    lf_root = tmp_path / "projects_longform"
    shorts_dir.mkdir()
    monkeypatch.setattr(config, "PROJECTS_DIR", str(shorts_dir))
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_root))

    # Build full 8.6-min word-scale spec so LFQ2 duration (480..900s) passes cleanly
    spec = _build_valid_episode_spec(word_scale=9)
    init_rep = initialize_longform_project("longform_94_e2e", spec, projects_longform_dir=lf_root)
    p_dir = lf_root / "longform_94_e2e"
    assert 480.0 <= init_rep["estimated_duration_sec"] <= 900.0

    # Dry-run sharded flow worker check
    import asyncio

    dry_receipt = asyncio.run(run_longform_sharded_flow_generation(p_dir, tabs=5, dry_run=True))
    assert dry_receipt["tabs_capped"] == 3
    assert dry_receipt["dry_run"] is True

    # Trim clips to 3 representative cuts (including split_hstack + living_brain) for fast 1080p assembly verification
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)

    sec_mp4 = clips_dir / "secondary_right.mp4"
    clip_files = [clips_dir / f"clip_{i:03d}.mp4" for i in range(1, 6)]
    for idx_m, out_m in enumerate([*clip_files, sec_mp4]):
        wr = cv2.VideoWriter(str(out_m), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (640, 360))
        for f_i in range(96):  # 4.0s @ 24fps
            frm = np.full((360, 640, 3), (218 - idx_m * 6, 224, 230), dtype=np.uint8)
            cv2.rectangle(frm, (80 + f_i * 3, 90), (220 + f_i * 3, 260), (70, 130, 195), -1)
            wr.write(frm)
        wr.release()

    vp_doc["clips"] = [
        {
            **vp_doc["clips"][0],
            "index": 1,
            "clip_number": 1,
            "chapter": 1,
            "chapter_break": True,
            "target_duration_sec": 4.8,
            "grammar": "porcelain_fullbleed_world",
        },
        {
            **vp_doc["clips"][1],
            "index": 2,
            "clip_number": 2,
            "chapter": 2,
            "chapter_break": True,
            "target_duration_sec": 5.0,
            "grammar": "porcelain_living_brain",
            "split_mode": "split_hstack",
            "secondary_clip_path": "03_visuals/flow_native_clips/secondary_right.mp4",
            "split_left_label": "NATURAL SLEEP",
            "split_right_label": "SEDATED SLEEP",
        },
        {
            **vp_doc["clips"][2],
            "index": 3,
            "clip_number": 3,
            "chapter": 3,
            "chapter_break": True,
            "target_duration_sec": 4.9,
            "grammar": "porcelain_living_brain",
        },
        {
            **vp_doc["clips"][3],
            "index": 4,
            "clip_number": 4,
            "chapter": 4,
            "chapter_break": True,
            "target_duration_sec": 4.9,
            "grammar": "porcelain_fullbleed_world",
        },
        {
            **vp_doc["clips"][4],
            "index": 5,
            "clip_number": 5,
            "chapter": 5,
            "chapter_break": True,
            "target_duration_sec": 4.9,
            "grammar": "porcelain_living_brain",
        },
    ]
    vp_doc["flow_shards"] = build_flow_shards(vp_doc["clips"])
    vp_path.write_text(json.dumps(vp_doc, indent=2) + "\n", encoding="utf-8")

    # Stage 24.5s stereo 48kHz WAV + prosody_report.json + subtitles.ass
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    sr = 48000
    t_arr = np.linspace(0.0, 24.5, int(sr * 24.5), endpoint=False, dtype=np.float32)
    tone = (0.22 * np.sin(2.0 * math.pi * 196.0 * t_arr) * 32767.0).astype(np.int16)
    stereo = np.column_stack([tone, tone])
    with wave.open(str(wav_path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(stereo.tobytes())

    (p_dir / "04_audio" / "prosody_report.json").write_text(
        json.dumps(
            {
                "prosody_mode": "longform_us_v7",
                "duration_sec": 24.5,
                "effective_wpm": 145.2,
                "integrated_lufs": -14.0,
                "true_peak_dbtp": -1.6,
                "max_wsola_stretch_delta": 0.0,
            }
        ),
        encoding="utf-8",
    )

    s_doc = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    s_timings = []
    for k, cid in enumerate(["cite_perlis_1997", "cite_xie_2013", "cite_fultz_2019", "cite_hauglund_2025"]):
        t0 = k * 5.6
        s_timings.append(
            {
                "sentence_index": k + 1,
                "chapter": min(k + 1, 5),
                "text": "Fluid channels expand sixty percent during natural deep sleep.",
                "citation_id": cid,
                "start_sec": t0,
                "end_sec": t0 + 2.8,
                "words": [
                    {"word": w, "start": t0 + wi * 0.28, "end": t0 + (wi + 1) * 0.28}
                    for wi, w in enumerate("Fluid channels expand sixty percent during natural deep sleep.".split())
                ],
            }
        )
    build_longform_subtitles_ass(p_dir, sentence_timings=s_timings, total_duration_sec=24.5, script_doc=s_doc, visual_plan=vp_doc)

    # Stage 4 synthetic 1920x1080 architectural/brain reference PNGs + provenance for Q1-Q10
    specs_payload = build_longform_reference_specs(p_dir)
    from pipeline.reference_image_qa import register_reference_image

    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    rng = np.random.default_rng(42)
    for idx_sp, sp in enumerate(specs_payload["all_specs"]):
        y_g = np.linspace(115, 228, 1080, dtype=np.float32)[:, None]
        x_g = np.linspace(-28 if idx_sp % 2 == 0 else 28, 28 if idx_sp % 2 == 0 else -28, 1920, dtype=np.float32)[None, :]
        grain = rng.normal(0.0, 6.5, size=(1080, 1920)).astype(np.float32)
        base = np.clip(y_g + x_g + grain, 75, 238).astype(np.uint8)
        canvas = np.stack(
            [
                np.clip(base + 4, 70, 242).astype(np.uint8),
                base,
                np.clip(base - 4, 65, 238).astype(np.uint8),
            ],
            axis=2,
        )
        # Architectural paneling across surround + foreground (avoiding bottom 10% text-artifact band)
        for g_x in range(80 + idx_sp * 22, 1860, 76):
            cv2.line(canvas, (g_x, 120), (g_x, 860), (88, 96, 106), 2)
        for g_y in range(130, 860, 110):
            cv2.line(canvas, (60, g_y), (1860, g_y), (96, 104, 112), 2)
        # Distinct structural block per anchor so pairwise dHash >= 14 while preserving studio histogram cohesion
        bx = 360 + idx_sp * 310
        cv2.rectangle(canvas, (bx, 220), (bx + 320, 780), (78, 86, 96), -1)
        # Matte-white porcelain silhouette in center
        cv2.circle(canvas, (960, 420), 155, (232, 234, 236), -1)
        if sp["setting"] == "brain_studio":
            # Enclosed cyan-blue (BGR ~235,190,40) + crimson-red (BGR ~55,45,215) subsurface brain pathways
            cv2.circle(canvas, (930, 410), 68, (235, 195, 45), -1)
            cv2.circle(canvas, (1010, 440), 48, (55, 45, 215), -1)
        dst_png = ref_dir / sp["filename"]
        cv2.imwrite(str(dst_png), canvas)
        register_reference_image(p_dir, sp["filename"], "flow_image_generation")

    ref_qa = inspect_longform_reference_pack(p_dir, specs_payload=specs_payload)
    assert ref_qa["cv_pre_generation_ready"] is True, f"Ref QA failed: {ref_qa['blocking_reasons']}"

    asm_rep = assemble_longform_episode(p_dir, hook_text="8 HOURS SEDATED?")
    assert asm_rep["passed"] is True
    assert asm_rep["resolution"] == [1920, 1080]
    assert asm_rep["fps"] == 24
    assert asm_rep["subtitles_burned_in"] is True

    pub_rep = prepare_longform_publish_package(p_dir, hook_text="8 HOURS SEDATED?")
    assert pub_rep["upload_cc_srt"] is False
    assert pub_rep["pinned_comment_valid"] is True
    assert "00:00 " in pub_rep["description"]
    for var in ("A", "B", "C"):
        assert pub_rep["thumbnail_sizes_bytes"][var] <= config.LONGFORM_THUMB_MAX_BYTES

    qa_rep = run_longform_qa(p_dir, require_audio=True, require_refs=True, require_final_mp4=True)
    assert qa_rep["passed"] is True, f"LFQ issues: {qa_rep['issues']}"

    # Negative edge cases on LFQ1 (> 22 words & 1st-person pronoun) and LFQ5 (inside Shorts dir)
    bad_script = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    bad_script["sentences"][0]["text"] = (
        "I think this deliberately overlong twenty five word documentary sentence violates both the first person "
        "narrator rule and the twenty two word maximum ceiling."
    )
    (p_dir / "02_script" / "script.json").write_text(json.dumps(bad_script), encoding="utf-8")
    qa_bad = run_longform_qa(p_dir)
    assert qa_bad["passed"] is False
    assert qa_bad["gates"]["LFQ1_sentence_and_pronoun_lock"]["passed"] is False

    bad_shorts_proj = shorts_dir / "illegal_lf_in_shorts"
    initialize_longform_project(str(bad_shorts_proj), spec)
    qa_iso = run_longform_qa(bad_shorts_proj)
    assert qa_iso["gates"]["LFQ5_aspect_and_isolation_lock"]["passed"] is False


def test_news_radar_five_everyday_domains():
    assert set(EVERYDAY_PSYCH_NEURO_QUERIES.keys()) == {"sleep", "habits", "memory", "anxiety", "relationships"}
    assert classify_everyday_domain("Slow-wave sleep cerebrospinal fluid glymphatic clearance in humans") == "sleep"
    assert classify_everyday_domain("Dorsal striatum habit formation and procrastination self-control") == "habits"
    assert classify_everyday_domain("Hippocampal memory consolidation and retrieval spacing") == "memory"
    assert classify_everyday_domain("Intolerance of uncertainty and amygdala anxiety reactivity") == "anxiety"
    assert classify_everyday_domain("Social rejection pain and caregiver attachment co-regulation") == "relationships"
    assert classify_everyday_domain("Intracortical Brain-Computer Interface speech neuroprosthesis") == "bci_clinical"


def test_live_longform_sharded_flow_worker_non_dry_run(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import asyncio

    lf_dir = tmp_path / "projects_longform"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)
    monkeypatch.setattr("pipeline.longform_flow_worker.LONGFORM_SHARD_MAX_CLIPS", 2)

    spec = _build_valid_episode_spec(word_scale=1)
    init_res = initialize_longform_project("lf_live_flow_test", spec, projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])

    # Trim to 3 pending clips across 2 shards (shard_max=2) so non-dry-run exercises multi-shard concurrency
    prompts_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
    p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
    p_doc["clips"] = p_doc["clips"][:3]
    p_doc["shards"] = build_flow_shards(p_doc["clips"], max_per_shard=2)
    prompts_path.write_text(json.dumps(p_doc, indent=2), encoding="utf-8")

    class _DummyCDPClient:
        def __init__(self, ws_url: str):
            self.ws_url = ws_url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def send(self, method: str, params: dict | None = None):
            return {}

    tab_counter = {"n": 0}
    configured_tabs: list[str] = []

    async def _fake_alloc_tab(cdp_port: int = 9222):
        tab_counter["n"] += 1
        tid = f"tab_{tab_counter['n']}"
        return {"tab_id": tid, "ws_url": f"ws://127.0.0.1:{cdp_port}/devtools/page/{tid}"}

    async def _fake_cfg_16x9(client, *, engine_mode: str = "zero-credit", credit_exhausted_event=None):
        configured_tabs.append(client.ws_url)
        return {"aspect": "16:9", "duration": "8s", "flow_model": "veo_3_1_lite_low_priority"}

    def _write_valid_16x9_mp4(dst: Path, seed_shift: int) -> None:
        dst.parent.mkdir(parents=True, exist_ok=True)
        fourcc = cv2.VideoWriter_fourcc(*"mp4v")
        vw = cv2.VideoWriter(str(dst), fourcc, 24.0, (1920, 1080))
        for fi in range(168):  # 7.0s @ 24fps (>= target_duration_sec)
            frm = np.full((1080, 1920, 3), 210, dtype=np.uint8)
            cx = 260 + seed_shift * 90 + fi * 12
            cv2.circle(frm, (cx % 1760, 520), 140, (235, 185, 50), -1)
            cv2.rectangle(frm, (180, 220), (1740, 860), (95, 105, 115), 3)
            vw.write(frm)
        vw.release()

    async def _fake_gen_clip_16x9(*, client, clip_num: int, out_mp4: Path, **kwargs):
        _write_valid_16x9_mp4(out_mp4, seed_shift=clip_num)
        return {"ok": True, "clip_number": clip_num, "aspect": "16:9"}

    monkeypatch.setattr("pipeline.flow_live_single_worker.allocate_dedicated_flow_project_tab", _fake_alloc_tab)
    monkeypatch.setattr("pipeline.studio.whale_session.DirectCDPClient", _DummyCDPClient)
    monkeypatch.setattr("pipeline.longform_flow_worker._configure_longform_video_16x9_tab", _fake_cfg_16x9)
    monkeypatch.setattr("pipeline.longform_flow_worker._generate_single_longform_16x9_clip_in_tab", _fake_gen_clip_16x9)

    receipt = asyncio.run(
        run_longform_sharded_flow_generation(
            p_dir,
            tabs=2,
            engine_mode="zero-credit",
            dry_run=False,
        )
    )
    assert receipt["passed"] is True
    assert receipt["completed_clips"] == [1, 2, 3]
    assert receipt["failed_clips"] == []
    assert receipt["aspect"] == "16:9"
    assert len(configured_tabs) == 2
    assert (p_dir / "03_visuals" / "flow_generation_receipt.json").exists()


def test_longform_audio_preserves_reference_anchor_bindings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lf_dir = tmp_path / "projects_longform"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)

    spec = _build_valid_episode_spec(word_scale=1)
    init_res = initialize_longform_project("lf_anchor_survival_test", spec, projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])

    # Stage synthetic reference PNGs and bind them BEFORE running synthesize_longform_master_audio
    specs_payload = build_longform_reference_specs(p_dir)
    from pipeline.longform_refs import _bind_longform_anchors_to_plan

    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    for sp in specs_payload["all_specs"]:
        cv2.imwrite(str(ref_dir / sp["filename"]), np.full((1080, 1920, 3), 215, dtype=np.uint8))
    _bind_longform_anchors_to_plan(p_dir, specs_payload)

    vp_before = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    assert sum(1 for c in vp_before["clips"] if c.get("reference_image")) > 0

    def _fast_synth_line(text: str, *, sr: int = 48000, **kwargs) -> np.ndarray:
        t = np.linspace(0.0, 2.2, int(sr * 2.2), endpoint=False, dtype=np.float32)
        return (0.18 * np.sin(2.0 * math.pi * 190.0 * t)).astype(np.float32)

    monkeypatch.setattr("pipeline.longform_audio.synthesize_line", _fast_synth_line)
    synthesize_longform_master_audio(p_dir, voice_preset="emma_v7", engine="kokoro-onnx", force=True)

    vp_after = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    fp_after = json.loads((p_dir / "03_visuals" / "flow_longform_prompts.json").read_text(encoding="utf-8"))
    vp_bound = [c for c in vp_after["clips"] if c.get("reference_image")]
    fp_bound = [c for c in fp_after["clips"] if c.get("reference_image")]
    assert len(vp_bound) > 0
    assert len(vp_bound) == len(fp_bound)


def test_debate_pinned_comment_validation_and_dossier_nested_bet(tmp_path: Path):
    from pipeline.studio.community import _ensure_creator_bet_line1, validate_pinned_comment_bet

    # 1. Alias parity + >240 char Line 1 rejection + missing DOI rejection on multi-line full_comment
    overlong_line1 = (
        "My bet: slow-wave fluid clearance matters far more than total sedated hours — "
        + ("extra clinical debate padding words " * 6)
        + "which sleep pattern would you trust tonight?"
    )
    assert len(overlong_line1) > config.PINNED_COMMENT_LINE1_MAX_CHARS
    issues_len = validate_pinned_comment_bet(
        overlong_line1,
        full_comment=overlong_line1 + "\nhttps://doi.org/10.1126/science.1241224",
    )
    assert any("240" in msg for msg in issues_len)

    issues_no_doi = validate_debate_pinned_comment_line1(
        "My bet: natural sleep beats sedated hours — which side would you pick?",
        full_comment="My bet: natural sleep beats sedated hours — which side would you pick?\nNo link here.",
    )
    assert any("doi.org" in msg.lower() for msg in issues_no_doi)

    # 2. _ensure_creator_bet_line1 clamps >45-char bets, strips raw ** markdown, and clamps >240-char Line 1
    line1_clamped = _ensure_creator_bet_line1(
        "My bet: deep slow-wave cerebrospinal fluid washing matters far more than eight hours — "
        "**What if** " + ("a surprisingly long textbook neurological explanation " * 5) + "or is there another choice?"
    )
    assert "**" not in line1_clamped
    assert len(line1_clamped) <= config.PINNED_COMMENT_LINE1_MAX_CHARS
    assert validate_debate_pinned_comment_line1(line1_clamped) == []

    # 3. Nested dossier debate_ignition.offcenter_creator_bet extraction + fail-closed staging
    dossiers_root = tmp_path / "research_dossiers"
    slug_dir = dossiers_root / "nested_bet_case"
    slug_dir.mkdir(parents=True)
    (slug_dir / "dossier.json").write_text(
        json.dumps(
            {
                "slug": "nested_bet_case",
                "topic": "Glymphatic Sleep Debate",
                "primary_doi": "10.1126/science.1241224",
                "debate_ignition": {
                    "offcenter_creator_bet": "My bet: 5 deep hours beat 8 sedated",
                    "forced_choice_question": "Which sleep trade-off would you choose tonight?",
                },
            }
        ),
        encoding="utf-8",
    )
    (slug_dir / "01_sources.json").write_text(
        json.dumps({"primary": {"authors": "Xie et al.", "year": 2013, "journal": "Science", "doi": "10.1126/science.1241224"}}),
        encoding="utf-8",
    )
    proj_root = tmp_path / "projects"
    p_dir = proj_root / "proj_nested_bet"
    (p_dir / "02_script").mkdir(parents=True)
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"dossier_slug": "nested_bet_case", "doi": "10.1126/science.1241224"}),
        encoding="utf-8",
    )

    cm = CommunityManager(projects_dir=proj_root, dossiers_root=dossiers_root)
    pkg = cm.prepare_comment_content("proj_nested_bet")
    assert pkg["line1_valid"] is True
    assert pkg["validation_issues"] == []
    assert pkg["comment_text"].startswith("My bet: 5 deep hours beat 8 sedated")
    staged = cm.stage_prepared_comment("proj_nested_bet")
    assert isinstance(staged, dict)
    assert (p_dir / "06_publish" / "prepared_comment.json").exists()


def test_longform_subtitle_zero_frame_handoff_and_lfq8_truncation_gate(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    lf_dir = tmp_path / "projects_longform"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)

    spec = _build_valid_episode_spec(word_scale=1)
    init_res = initialize_longform_project("lf_sub_handoff_test", spec, projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])
    s_doc = json.loads((p_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
    vp_doc = json.loads((p_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))

    # Construct a 12-word sentence with a 0.25s internal comma gap between word 5 and word 6
    words_txt = "When deep slow-wave sleep begins, fluid channels expand sixty percent overnight.".split()
    w_objs = []
    cur = 0.20
    for idx_w, w in enumerate(words_txt):
        if idx_w == 5:
            cur += 0.25  # intra-sentence comma breath (< 0.55s) -> must bridge to 0-frame handoff!
        w_objs.append({"word": w, "start": round(cur, 3), "end": round(cur + 0.28, 3)})
        cur += 0.30

    timings = [
        {
            "sentence_index": 1,
            "chapter": 1,
            "text": " ".join(words_txt),
            "citation_id": "cite_xie_2013",
            "start_sec": w_objs[0]["start"],
            "end_sec": w_objs[-1]["end"],
            "words": w_objs,
        }
    ]
    res = build_longform_subtitles_ass(p_dir, sentence_timings=timings, total_duration_sec=10.0, script_doc=s_doc, visual_plan=vp_doc)
    ass_lines = Path(res["ass_path"]).read_text(encoding="utf-8").splitlines()
    def_events = [ln.split(",", 9) for ln in ass_lines if ln.startswith("Dialogue:") and ln.split(",", 9)[3].strip() == "Default"]
    assert len(def_events) >= 2
    for i in range(len(def_events) - 1):
        assert def_events[i][2] == def_events[i + 1][1], f"Mid-sentence subtitle blink gap: {def_events[i][2]} -> {def_events[i + 1][1]}"

    # Inject an ellipsis-truncated DocCitationBody line and verify LFQ8 rejects it
    ass_path = Path(res["ass_path"])
    ass_txt = ass_path.read_text(encoding="utf-8")
    ass_path.write_text(
        ass_txt + "\nDialogue: 2,0:00:01.00,0:00:05.00,DocCitationBody,,0,0,0,,{\\an7\\pos(114,789)}Xie et al. — Fluid channels expand in…\n",
        encoding="utf-8",
    )
    qa_rep = run_longform_qa(p_dir)
    assert qa_rep["gates"]["LFQ8_subtitle_and_citation_non_overlap"]["passed"] is False
    assert any("ellipsis" in msg for msg in qa_rep["gates"]["LFQ8_subtitle_and_citation_non_overlap"]["issues"])


def test_cli_longform_flags_and_publish_timestamp_rollover(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    import sys
    from pipeline import cli

    captured = {}
    monkeypatch.setattr(cli, "cmd_longform_refs", lambda args: captured.setdefault("refs", args))
    monkeypatch.setattr(cli, "cmd_longform_qa", lambda args: captured.setdefault("qa", args))

    monkeypatch.setattr(sys, "argv", ["main.py", "longform-refs", "--project", "lf_p1", "--backend", "flow"])
    cli.main()
    assert captured["refs"].backend == "flow"

    monkeypatch.setattr(sys, "argv", ["main.py", "longform-qa", "--project", "lf_p1", "--require-mp4"])
    cli.main()
    assert captured["qa"].require_final_mp4 is True

    # Verify ss == 60 rollover (145 words / 2.42 = 59.917s -> rounds % 60 to 60 -> must format as 01:00, never 00:60)
    lf_dir = tmp_path / "projects_longform"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)
    spec = _build_valid_episode_spec(word_scale=1)
    init_res = initialize_longform_project("lf_rollover_test", spec, projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])

    s_path = p_dir / "02_script" / "script.json"
    s_doc = json.loads(s_path.read_text(encoding="utf-8"))
    s_doc["chapters"][0]["word_count"] = 145
    for ch in s_doc["chapters"]:
        ch.pop("youtube_timestamp", None)
    s_path.write_text(json.dumps(s_doc, indent=2), encoding="utf-8")

    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ref_dir / "ref_lf_brain_master.png"), np.full((1080, 1920, 3), 210, dtype=np.uint8))

    pub = prepare_longform_publish_package(p_dir, hook_text="8 HOURS SEDATED?")
    assert "00:60" not in pub["description"]
    assert "01:00 " in pub["description"]


def test_fail_closed_16x9_reference_chip_attachment_and_provenance_receipt(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    import asyncio
    from pipeline import flow_diorama_sharded_worker, flow_ingredients
    from pipeline.longform_flow_worker import (
        _generate_single_longform_16x9_clip_in_tab,
        parse_longform_clip_spec,
        run_longform_sharded_flow_generation,
    )

    assert parse_longform_clip_spec("1-2") == [1, 2]
    assert parse_longform_clip_spec("1, 3-5, 8") == [1, 3, 4, 5, 8]
    assert parse_longform_clip_spec("") is None

    ref_png = tmp_path / "ref_sleep_cast_sleeper.png"
    cv2.imwrite(str(ref_png), np.full((1080, 1920, 3), 215, dtype=np.uint8))

    class _FakeFlowClient:
        def __init__(self, *, has_warning: bool = False, agent_pressed: bool = True):
            self.has_warning = has_warning
            self.agent_pressed = agent_pressed
            self.sent: list[tuple[str, dict]] = []
            self.prompt_cleared = False

        async def send(self, method: str, params: dict | None = None):
            self.sent.append((method, params or {}))
            if method == "Input.insertText":
                self.prompt_cleared = False
            return {}

        async def eval(self, expr: str, **kwargs):
            s = str(expr)
            if "agent-mode-chip" in s and "hadChip" in s:
                was = self.agent_pressed
                self.agent_pressed = False
                return {"hadChip": was, "x": 120, "y": 980}
            if "agent-mode-chip" in s:
                return self.agent_pressed
            if "prompt-warning-button" in s or "has_warning_btn" in s or "exhausted" in s:
                return {"has_warning_btn": self.has_warning, "exhausted": self.has_warning}
            if "settings-trigger-button" in s and "localStorage" in s:
                return {
                    "summary": "Video · 720p · 8s\ncrop_16_9\nx1",
                    "ls": {
                        "mode": "VIDEO_REFERENCES",
                        "aspectRatio": "LANDSCAPE",
                        "videoModelFamilyId": "veo_3_1_lite_low_priority",
                    },
                }
            if "flow-video-tile" in s and "srcs" in s:
                return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}
            if "flow-video-tile" in s and "hasNewSrc" in s:
                return {"ready": 1, "rendering": 0, "hasNewSrc": True, "topKey": "https://flow.example/v1.mp4", "hadErr": False}
            if "ProseMirror" in s and "delete" in s:
                return True
            if "ProseMirror" in s and "length" in s and "InputEvent" not in s:
                return 0
            if "Start generation" in s:
                return {"action": "listener_invoked", "x": 600, "y": 980}
            return True

    # Case 1: attach fails (count_chips stays 0) -> MUST fail closed, never insert prompt or submit unanchored
    c1 = _FakeFlowClient(has_warning=False, agent_pressed=True)
    cleared_calls = {"n": 0}

    async def _no_chips(_c):
        return 0

    async def _fail_upload(_c, _p):
        return False

    async def _fail_attach(_c, _name, wait_sec=16.0):
        return False

    async def _track_clear(_c, max_rounds=8):
        cleared_calls["n"] += 1
        return 0

    async def _ok_select_model(_c, model=""):
        return True

    async def _ok_fam(_c):
        return "veo_3_1_lite_low_priority"

    monkeypatch.setattr(flow_ingredients, "count_chips", _no_chips)
    monkeypatch.setattr(flow_ingredients, "upload_file_to_flow", _fail_upload)
    monkeypatch.setattr(flow_ingredients, "attach_uploaded_by_name", _fail_attach)
    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _track_clear)
    monkeypatch.setattr(flow_ingredients, "select_flow_video_model", _ok_select_model)
    monkeypatch.setattr(flow_ingredients, "read_active_flow_model_family", _ok_fam)

    res_fail_attach = asyncio.run(
        _generate_single_longform_16x9_clip_in_tab(
            client=c1,
            clip_num=1,
            prompt_text="Generate a 16:9 horizontal widescreen documentary video clip.",
            out_mp4=tmp_path / "clip_001.mp4",
            start_ref=ref_png,
            uploaded_cache=set(),
            seen_video_urls=set(),
            flow_dl_dir=tmp_path / "dl",
            seen_global_shas=set(),
            engine_mode="zero-credit",
        )
    )
    assert res_fail_attach["ok"] is False
    assert res_fail_attach["reason"] == "ref_attach_or_0cred_lock_failed"
    assert c1.agent_pressed is False
    assert not any(m == "Input.insertText" for m, _ in c1.sent)

    # Case 2: attach succeeds (chips=1) but has_warning_btn stays True -> MUST fail closed WITHOUT clearing chip!
    c2 = _FakeFlowClient(has_warning=True, agent_pressed=True)
    chip_state = {"chips": 0}

    async def _dyn_chips(_c):
        return chip_state["chips"]

    async def _ok_upload(_c, _p):
        return True

    async def _ok_attach(_c, _name, wait_sec=16.0):
        chip_state["chips"] = 1
        return True

    async def _clear_sets_zero(_c, max_rounds=8):
        cleared_calls["n"] += 1
        chip_state["chips"] = 0
        return 0

    monkeypatch.setattr(flow_ingredients, "count_chips", _dyn_chips)
    monkeypatch.setattr(flow_ingredients, "upload_file_to_flow", _ok_upload)
    monkeypatch.setattr(flow_ingredients, "attach_uploaded_by_name", _ok_attach)
    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _clear_sets_zero)

    cleared_calls["n"] = 0
    res_warn = asyncio.run(
        _generate_single_longform_16x9_clip_in_tab(
            client=c2,
            clip_num=2,
            prompt_text="Generate a 16:9 horizontal widescreen documentary video clip.",
            out_mp4=tmp_path / "clip_002.mp4",
            start_ref=ref_png,
            uploaded_cache=set(),
            seen_video_urls=set(),
            flow_dl_dir=tmp_path / "dl",
            seen_global_shas=set(),
            engine_mode="zero-credit",
        )
    )
    assert res_warn["ok"] is False
    assert res_warn["reason"] == "ref_attach_or_0cred_lock_failed"
    # Chip was NEVER dropped via clear_prompt_ingredients after attachment
    assert chip_state["chips"] == 1
    assert cleared_calls["n"] == 0
    assert not any(m == "Input.insertText" for m, _ in c2.sent)

    # Case 3: Happy path records reference_image & reference_attached=True in flow_provenance_receipt.json
    c3 = _FakeFlowClient(has_warning=False, agent_pressed=True)
    chip_state["chips"] = 0

    async def _fake_dl(*, dst_mp4: Path, **kwargs):
        dst_mp4.parent.mkdir(parents=True, exist_ok=True)
        vw = cv2.VideoWriter(str(dst_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (1280, 720))
        rad = 90 if "001" in dst_mp4.name else 75
        for fi in range(192):
            frm = np.full((720, 1280, 3), 218, dtype=np.uint8)
            cv2.circle(frm, (150 + fi * 4, 360), rad, (230, 180, 50), -1)
            vw.write(frm)
        vw.release()
        return {"sha256": f"sha_{dst_mp4.name}", "source_download_filename": f"flow_direct_{dst_mp4.name}"}

    monkeypatch.setattr(flow_diorama_sharded_worker, "_download_newest_ready_tile", _fake_dl)
    out_ok = tmp_path / "clip_001_ok.mp4"
    res_ok = asyncio.run(
        _generate_single_longform_16x9_clip_in_tab(
            client=c3,
            clip_num=1,
            prompt_text="Generate a 16:9 horizontal widescreen documentary video clip.",
            out_mp4=out_ok,
            start_ref=ref_png,
            uploaded_cache=set(),
            seen_video_urls=set(),
            flow_dl_dir=tmp_path / "dl",
            seen_global_shas=set(),
            engine_mode="zero-credit",
        )
    )
    assert res_ok["ok"] is True
    assert res_ok["reference_image"] == "ref_sleep_cast_sleeper.png"
    assert res_ok["reference_attached"] is True
    assert res_ok["zero_credit_verified"] is True

    # Verify run_longform_sharded_flow_generation writes flow_provenance_receipt.json with reference_image & reference_attached
    lf_dir = tmp_path / "projects_longform"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)
    init_res = initialize_longform_project("lf_prov_test", _build_valid_episode_spec(word_scale=1), projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])
    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    cv2.imwrite(str(ref_dir / "ref_sleep_cast_sleeper.png"), np.full((1080, 1920, 3), 215, dtype=np.uint8))

    fp_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
    fp_doc = json.loads(fp_path.read_text(encoding="utf-8"))
    fp_doc["clips"] = fp_doc["clips"][:2]
    fp_doc["clips"][0]["reference_image"] = "03_visuals/reference_images/ref_sleep_cast_sleeper.png"
    fp_doc["clips"][1]["reference_image"] = None
    fp_path.write_text(json.dumps(fp_doc, indent=2), encoding="utf-8")

    class _NoopCM:
        def __init__(self, ws_url: str):
            self.ws_url = ws_url

        async def __aenter__(self):
            return c3

        async def __aexit__(self, *a):
            return False

    async def _alloc(cdp_port: int = 9222):
        return {
            "tab_id": "tab_prov_01",
            "ws_url": f"ws://127.0.0.1:{cdp_port}/devtools/page/tab_prov_01",
            "project_url": "https://flow.google.com/project/11111111-2222-3333-4444-555555555555",
        }

    async def _gen_stub(*, clip_num: int, out_mp4: Path, start_ref: Path | None, **kw):
        await _fake_dl(dst_mp4=out_mp4)
        return {
            "ok": True,
            "clip_number": clip_num,
            "flow_model": config.FLOW_ZERO_CREDIT_MODEL,
            "credit_tier": "zero_credit_fallback",
            "zero_credit_verified": True,
            "reference_image": start_ref.name if start_ref is not None else None,
            "reference_attached": bool(start_ref is not None),
            "source_download_filename": f"flow_direct_{out_mp4.name}",
        }

    monkeypatch.setattr("pipeline.flow_live_single_worker.allocate_dedicated_flow_project_tab", _alloc)
    monkeypatch.setattr("pipeline.studio.whale_session.DirectCDPClient", _NoopCM)
    monkeypatch.setattr("pipeline.longform_flow_worker._configure_longform_video_16x9_tab", lambda *a, **kw: asyncio.sleep(0))
    monkeypatch.setattr("pipeline.longform_flow_worker._generate_single_longform_16x9_clip_in_tab", _gen_stub)

    rcpt = asyncio.run(
        run_longform_sharded_flow_generation(p_dir, only_clips="1-2", engine_mode="zero-credit", dry_run=False)
    )
    assert rcpt["passed"] is True
    assert rcpt["zero_credit_verified"] is True
    prov = json.loads((p_dir / "03_visuals" / "flow_provenance_receipt.json").read_text(encoding="utf-8"))
    assert prov["zero_credit_verified"] is True
    assert prov["clips"][0]["reference_image"] == "ref_sleep_cast_sleeper.png"
    assert prov["clips"][0]["reference_attached"] is True
    assert prov["clips"][1]["reference_image"] is None
    assert prov["clips"][1]["reference_attached"] is False


def test_hands_closeup_sanitizer_brain_corr_and_strict_provenance_gates(tmp_path: Path, monkeypatch):
    """Verifies tablet/city-brand sanitization, hands-only macro prompt, brain correlation CV gate, and strict provenance QA."""
    import asyncio
    import shutil
    import numpy as np
    from pipeline import config, flow_ingredients
    from pipeline.longform_flow_worker import (
        _generate_single_longform_16x9_clip_in_tab,
        inspect_longform_16x9_clip_cv,
        run_longform_sharded_flow_generation,
    )
    from pipeline.longform_prompt_builder import (
        build_longform_16x9_flow_prompt,
        initialize_longform_project,
        sanitize_longform_scene_props,
    )
    from pipeline.longform_qa import run_longform_qa

    # 1. Sanitizer & hands-closeup prompt must eliminate 'white tablet' (iPad), 'Boston-style', and 'craniums'
    s_tab = sanitize_longform_scene_props("Hands placing a small unmarked white tablet beside water in a Boston-style sleep bay")
    assert "white tablet" not in s_tab.lower()
    assert "boston-style" not in s_tab.lower()
    assert "sleep capsule" in s_tab.lower()
    assert "university research" in s_tab.lower()

    hands_prompt = build_longform_16x9_flow_prompt(
        {
            "grammar": "porcelain_hands_closeup",
            "camera": "macro_rack_focus",
            "scene": "Articulated porcelain fingers placing a small unmarked white tablet beside a glass of water",
        }
    )
    assert "craniums" not in hands_prompt.lower()
    assert "zero disembodied heads, skulls, busts, or electronic screen devices" in hands_prompt.lower()
    assert "sleep capsule" in hands_prompt.lower()

    # 2. Brain histogram correlation CV gate rejects unanchored cartoon brain against colored 3D brain anchor
    ref_brain = tmp_path / "ref_brain.png"
    ref_img = np.full((360, 640, 3), (235, 235, 235), dtype=np.uint8)
    cv2.circle(ref_img, (320, 180), 130, (235, 190, 40), -1)  # cyan-blue BGR
    cv2.imwrite(str(ref_brain), ref_img)

    good_brain_mp4 = tmp_path / "good_brain.mp4"
    vw_good = cv2.VideoWriter(str(good_brain_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (1280, 720))
    for fi in range(192):
        frm = np.full((720, 1280, 3), (235, 235, 235), dtype=np.uint8)
        cv2.circle(frm, (180 + fi * 4, 360), 220, (235, 190, 40), -1)
        vw_good.write(frm)
    vw_good.release()

    bad_brain_mp4 = tmp_path / "bad_brain.mp4"
    vw_bad = cv2.VideoWriter(str(bad_brain_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (1280, 720))
    for fi in range(192):
        frm = np.full((720, 1280, 3), (20, 20, 25), dtype=np.uint8)
        cv2.circle(frm, (180 + fi * 4, 360), 220, (180, 30, 210), -1)  # neon magenta on dark void
        vw_bad.write(frm)
    vw_bad.release()

    cv_good = inspect_longform_16x9_clip_cv(
        good_brain_mp4, min_duration_sec=3.2, grammar="porcelain_living_brain", reference_path=ref_brain
    )
    assert cv_good["passed"] is True
    assert cv_good["max_ref_hist_corr"] >= 0.50

    cv_bad = inspect_longform_16x9_clip_cv(
        bad_brain_mp4, min_duration_sec=3.2, grammar="porcelain_living_brain", reference_path=ref_brain
    )
    assert cv_bad["passed"] is False
    assert any(g.startswith("unanchored_brain_hallucination_") for g in cv_bad["failed_gates"])

    # 3. Fail-closed stale chip residue & unbound portrait lock check
    class _PortraitOrBadChipClient:
        def __init__(self, *, aspect: str = "LANDSCAPE", chip_uploading: bool = False):
            self.aspect = aspect
            self.chip_uploading = chip_uploading
            self.sent: list[tuple[str, dict]] = []

        async def send(self, method: str, params: dict | None = None):
            self.sent.append((method, params or {}))
            return {}

        async def eval(self, expr: str, **kwargs):
            s = str(expr)
            if "agent-mode-chip" in s:
                return {"hadChip": False, "x": 0, "y": 0} if "hadChip" in s else False
            if 'button[aria-label="Ingredient"]' in s:
                return not self.chip_uploading
            if "prompt-warning-button" in s or "has_warning_btn" in s or "exhausted" in s:
                return {"has_warning_btn": False, "exhausted": False}
            if "settings-trigger-button" in s and "localStorage" in s:
                return {
                    "summary": "Video · 720p · 8s\nx1",
                    "ls": {
                        "mode": "VIDEO_REFERENCES",
                        "aspectRatio": self.aspect,
                        "videoModelFamilyId": "veo_3_1_lite_low_priority",
                    },
                }
            if "flow-video-tile" in s and "srcs" in s:
                return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}
            return True

    async def _stuck_chip(_c):
        return 1

    async def _noop_clear(_c, max_rounds=8):
        return 1

    async def _ok_model(_c, model=""):
        return True

    async def _ok_fam(_c):
        return "veo_3_1_lite_low_priority"

    monkeypatch.setattr(flow_ingredients, "count_chips", _stuck_chip)
    monkeypatch.setattr(flow_ingredients, "clear_prompt_ingredients", _noop_clear)
    monkeypatch.setattr(flow_ingredients, "select_flow_video_model", _ok_model)
    monkeypatch.setattr(flow_ingredients, "read_active_flow_model_family", _ok_fam)

    res_stale = asyncio.run(
        _generate_single_longform_16x9_clip_in_tab(
            client=_PortraitOrBadChipClient(),
            clip_num=3,
            prompt_text="Generate a 16:9 horizontal widescreen documentary video clip.",
            out_mp4=tmp_path / "clip_003.mp4",
            start_ref=None,
            uploaded_cache=set(),
            seen_video_urls=set(),
            flow_dl_dir=tmp_path / "dl",
            seen_global_shas=set(),
            engine_mode="zero-credit",
        )
    )
    assert res_stale["ok"] is False
    assert res_stale["reason"] == "stale_chip_clear_failed"

    async def _zero_chips(_c):
        return 0

    monkeypatch.setattr(flow_ingredients, "count_chips", _zero_chips)
    res_port = asyncio.run(
        _generate_single_longform_16x9_clip_in_tab(
            client=_PortraitOrBadChipClient(aspect="PORTRAIT"),
            clip_num=4,
            prompt_text="Generate a 16:9 horizontal widescreen documentary video clip.",
            out_mp4=tmp_path / "clip_004.mp4",
            start_ref=None,
            uploaded_cache=set(),
            seen_video_urls=set(),
            flow_dl_dir=tmp_path / "dl",
            seen_global_shas=set(),
            engine_mode="zero-credit",
        )
    )
    assert res_port["ok"] is False
    assert res_port["reason"] == "landscape_16x9_lock_failed"

    # 4. Unverified pre-existing MP4 on disk gets reference_attached=False (not fabricated True) and fails LFQ12
    lf_dir = tmp_path / "projects_lf_strict"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)
    init_res = initialize_longform_project("lf_strict_prov", _build_valid_episode_spec(word_scale=1), projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])
    ref_dir = p_dir / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(ref_brain, ref_dir / "ref_brain.png")

    fp_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
    fp_doc = json.loads(fp_path.read_text(encoding="utf-8"))
    fp_doc["clips"] = fp_doc["clips"][:1]
    fp_doc["clips"][0]["grammar"] = "porcelain_living_brain"
    fp_doc["clips"][0]["reference_image"] = "03_visuals/reference_images/ref_brain.png"
    fp_path.write_text(json.dumps(fp_doc, indent=2), encoding="utf-8")

    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clips_dir.mkdir(parents=True, exist_ok=True)
    shutil.copy2(good_brain_mp4, clips_dir / "clip_001.mp4")

    asyncio.run(run_longform_sharded_flow_generation(p_dir, only_clips="1", engine_mode="zero-credit", dry_run=False))
    prov_unver = json.loads((p_dir / "03_visuals" / "flow_provenance_receipt.json").read_text(encoding="utf-8"))
    assert prov_unver["clips"][0]["reference_attached"] is False

    qa_rep = run_longform_qa(p_dir, require_audio=False, require_refs=False, require_final_mp4=False, save_report=False)
    assert qa_rep["gates"]["LFQ12_final_mp4_stream_lock"]["passed"] is False
    assert any("failed provenance anchor check" in iss for iss in qa_rep["issues"])


def test_yunet_face_gate_rejects_sculpted_porcelain_faces_and_exempts_brain_clips(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verifies real YuNet face detection rejects sculpted matte-white doll faces in non-brain 16:9 clips while exempting 3D brain clips."""
    import pipeline.longform_flow_worker as lf_worker
    from pipeline.source_reenactment import detect_human_faces_yunet

    # 1. Prompt builder explicitly locks smooth featureless blank oval matte-white heads (zero eyes, zero nose, zero mouth)
    world_prompt = build_longform_16x9_flow_prompt(
        {
            "grammar": "porcelain_fullbleed_world",
            "camera": "slow_lateral_slider",
            "scene": "At a sunlit morning kitchen table, the clothed matte-white porcelain sleeper tips a ceramic coffee mug",
        }
    )
    low_p = world_prompt.lower()
    assert "smooth featureless blank oval matte-white heads" in low_p
    assert "zero eyes, zero nose, zero mouth" in low_p
    assert "translucent frosted-glass craniums" not in low_p

    def _draw_sculpted_matte_white_face(frm: np.ndarray, x_shift: int = 0) -> None:
        # Neutral matte-white/grey sculpted doll features (human skin ratio == 0.0, caught purely by YuNet)
        cx = 320 + x_shift
        cv2.ellipse(frm, (cx, 180), (75, 98), 0, 0, 360, (226, 226, 228), -1)
        cv2.ellipse(frm, (cx, 95), (78, 38), 0, 180, 360, (70, 70, 72), -1)
        cv2.ellipse(frm, (cx - 28, 152), (18, 5), 0, 180, 360, (65, 65, 68), 3)
        cv2.ellipse(frm, (cx + 28, 152), (18, 5), 0, 180, 360, (65, 65, 68), 3)
        cv2.circle(frm, (cx - 28, 168), 9, (245, 245, 245), -1)
        cv2.circle(frm, (cx + 28, 168), 9, (245, 245, 245), -1)
        cv2.circle(frm, (cx - 28, 168), 5, (38, 38, 40), -1)
        cv2.circle(frm, (cx + 28, 168), 5, (38, 38, 40), -1)
        cv2.line(frm, (cx, 168), (cx - 4, 202), (145, 145, 148), 3)
        cv2.circle(frm, (cx - 7, 205), 3, (105, 105, 108), -1)
        cv2.circle(frm, (cx + 7, 205), 3, (105, 105, 108), -1)
        cv2.ellipse(frm, (cx, 232), (22, 8), 0, 0, 180, (115, 115, 120), 4)

    # 2. Real unmocked detect_human_faces_yunet catches sculpted matte-white doll face even on a single mid-clip frame
    doll_mp4 = tmp_path / "sculpted_porcelain_doll_16x9.mp4"
    vw = cv2.VideoWriter(str(doll_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (640, 360))
    fc = 96
    mid_idx = fc // 2
    for fi in range(fc):
        frm = np.full((360, 640, 3), (218, 222, 226), dtype=np.uint8)
        cv2.rectangle(frm, (60 + fi * 3, 250), (190 + fi * 3, 330), (140, 150, 160), -1)
        if fi == mid_idx:
            _draw_sculpted_matte_white_face(frm, x_shift=0)
            assert len(detect_human_faces_yunet(frm)) > 0
        else:
            # Smooth featureless blank oval porcelain head on all other frames
            cv2.ellipse(frm, (320, 180), (70, 94), 0, 0, 360, (234, 235, 236), -1)
        vw.write(frm)
    vw.release()

    rep_world = inspect_longform_16x9_clip_cv(doll_mp4, min_duration_sec=3.2, grammar="porcelain_fullbleed_world")
    assert rep_world["passed"] is False
    assert rep_world["max_human_skin_ratio"] == 0.0
    assert rep_world["max_yunet_faces"] >= 1
    assert any("yunet" in g for g in rep_world["failed_gates"])

    rep_hands = inspect_longform_16x9_clip_cv(doll_mp4, min_duration_sec=3.2, grammar="porcelain_hands_closeup")
    assert rep_hands["passed"] is False
    assert rep_hands["max_yunet_faces"] >= 1

    # 3. 3D brain clips (porcelain_living_brain) are exempt from YuNet face rejection
    rep_brain = inspect_longform_16x9_clip_cv(doll_mp4, min_duration_sec=3.2, grammar="porcelain_living_brain")
    assert rep_brain["passed"] is True
    assert rep_brain["max_yunet_faces"] == 0

    # 4. Clean smooth blank oval porcelain clip passes with max_yunet_faces == 0
    clean_mp4 = tmp_path / "clean_blank_oval_16x9.mp4"
    vw_c = cv2.VideoWriter(str(clean_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (640, 360))
    for fi in range(fc):
        frm = np.full((360, 640, 3), (218, 222, 226), dtype=np.uint8)
        cv2.ellipse(frm, (220 + fi * 2, 180), (68, 92), 0, 0, 360, (236, 236, 238), -1)
        vw_c.write(frm)
    vw_c.release()
    rep_clean = inspect_longform_16x9_clip_cv(clean_mp4, min_duration_sec=3.2, grammar="porcelain_fullbleed_world")
    assert rep_clean["passed"] is True
    assert rep_clean["max_yunet_faces"] == 0

    # 5. Direct monkeypatch check confirming inspect_longform_16x9_clip_cv invokes detect_human_faces_yunet(frame_bgr)
    calls = {"n": 0}

    def _stub_yunet(frame_bgr: np.ndarray):
        calls["n"] += 1
        return [(100, 80, 90, 120, 0.88)]

    monkeypatch.setattr(lf_worker, "detect_human_faces_yunet", _stub_yunet)
    rep_stub = inspect_longform_16x9_clip_cv(clean_mp4, min_duration_sec=3.2, grammar="porcelain_fullbleed_world")
    assert calls["n"] == 5
    assert rep_stub["passed"] is False
    assert "human_skin_or_face_leak_yunet_1" in rep_stub["failed_gates"]


def test_longform_yunet_retry_reinforcement_and_worker_recovery(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    """Verifies YuNet retry prompt reinforcement respects hands-only vs world grammars and recovers cleanly in worker retries."""
    import asyncio
    import pipeline.longform_flow_worker as lf_worker

    # 1. Both porcelain_hands_closeup and porcelain_pov_hands lock hands/forearms with zero disembodied heads
    for g_hands in ("porcelain_hands_closeup", "porcelain_pov_hands"):
        hp = build_longform_16x9_flow_prompt(
            {
                "grammar": g_hands,
                "camera": "macro_rack_focus",
                "scene": "Articulated porcelain hands rest beside an unlabeled frosted amber glass vial",
            }
        )
        assert "zero disembodied heads" in hp.lower()
        assert "clothed articulated matte-white porcelain figures" not in hp.lower()

        retried_hp = lf_worker._reinforce_longform_yunet_retry_prompt(
            hp,
            grammar=g_hands,
            cv_reason="human_skin_or_face_leak_yunet_1",
        )
        assert "zero heads, zero busts, zero faces" in retried_hp.lower()
        assert "head surface" not in retried_hp.lower()
        assert "brow ridges" not in retried_hp.lower()
        assert "eye sockets" not in retried_hp.lower()

    # 2. World grammar reinforces smooth blank egg-shaped matte-white head without anatomical sculpt tokens
    wp = build_longform_16x9_flow_prompt(
        {
            "grammar": "porcelain_fullbleed_world",
            "camera": "locked_tripod",
            "scene": "A porcelain sleeper sits at a sunlit wooden kitchen table",
        }
    )
    retried_wp = lf_worker._reinforce_longform_yunet_retry_prompt(
        wp,
        grammar="porcelain_fullbleed_world",
        cv_reason="human_skin_or_face_leak_yunet_2",
    )
    assert "100% smooth featureless blank egg-shaped matte-white porcelain" in retried_wp.lower()
    assert "zero eyes, zero nose, zero mouth" in retried_wp.lower()
    assert "brow ridges" not in retried_wp.lower()

    # 3. End-to-end worker retry loop: attempt 1 fails YuNet CV gate, attempt 2 receives grammar-safe retry prompt and passes
    lf_dir = tmp_path / "projects_lf_yunet_retry"
    monkeypatch.setattr(config, "LONGFORM_PROJECTS_DIR", str(lf_dir))
    monkeypatch.setattr("pipeline.longform_prompt_builder.LONGFORM_PROJECTS_DIR", lf_dir)
    init_res = initialize_longform_project("lf_yunet_retry_ep", _build_valid_episode_spec(word_scale=1), projects_longform_dir=lf_dir)
    p_dir = Path(init_res["project_dir"])

    prompts_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
    p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
    p_doc["clips"] = p_doc["clips"][:2]
    p_doc["clips"][0]["clip_number"] = 1
    p_doc["clips"][0]["grammar"] = "porcelain_hands_closeup"
    p_doc["clips"][0]["prompt"] = build_longform_16x9_flow_prompt(
        {"grammar": "porcelain_hands_closeup", "camera": "macro_rack_focus", "scene": "Porcelain hands hold a glass cup"}
    )
    p_doc["clips"][1]["clip_number"] = 2
    p_doc["clips"][1]["grammar"] = "porcelain_fullbleed_world"
    p_doc["clips"][1]["prompt"] = build_longform_16x9_flow_prompt(
        {"grammar": "porcelain_fullbleed_world", "camera": "locked_tripod", "scene": "Porcelain sleeper sits at table"}
    )
    p_doc["shards"] = build_flow_shards(p_doc["clips"], max_per_shard=14)
    prompts_path.write_text(json.dumps(p_doc, indent=2), encoding="utf-8")

    class _DummyCDPClient:
        def __init__(self, ws_url: str):
            self.ws_url = ws_url

        async def __aenter__(self):
            return self

        async def __aexit__(self, exc_type, exc, tb):
            return False

        async def send(self, method: str, params: dict | None = None):
            return {}

    async def _fake_alloc_tab(cdp_port: int = 9222):
        return {"tab_id": "t_retry", "ws_url": f"ws://127.0.0.1:{cdp_port}/devtools/page/t_retry"}

    async def _fake_cfg_16x9(client, *, engine_mode: str = "zero-credit", credit_exhausted_event=None):
        return {"aspect": "16:9", "duration": "8s", "flow_model": "veo_3_1_lite_low_priority"}

    seen_prompts: dict[int, list[str]] = {1: [], 2: []}

    def _draw_sculpted_doll(frm: np.ndarray) -> None:
        cx = 320
        cv2.ellipse(frm, (cx, 180), (75, 98), 0, 0, 360, (226, 226, 228), -1)
        cv2.ellipse(frm, (cx, 95), (78, 38), 0, 180, 360, (70, 70, 72), -1)
        cv2.ellipse(frm, (cx - 28, 152), (18, 5), 0, 180, 360, (65, 65, 68), 3)
        cv2.ellipse(frm, (cx + 28, 152), (18, 5), 0, 180, 360, (65, 65, 68), 3)
        cv2.circle(frm, (cx - 28, 168), 9, (245, 245, 245), -1)
        cv2.circle(frm, (cx + 28, 168), 9, (245, 245, 245), -1)
        cv2.circle(frm, (cx - 28, 168), 5, (38, 38, 40), -1)
        cv2.circle(frm, (cx + 28, 168), 5, (38, 38, 40), -1)
        cv2.line(frm, (cx, 168), (cx - 4, 202), (145, 145, 148), 3)
        cv2.circle(frm, (cx - 7, 205), 3, (105, 105, 108), -1)
        cv2.circle(frm, (cx + 7, 205), 3, (105, 105, 108), -1)
        cv2.ellipse(frm, (cx, 232), (22, 8), 0, 0, 180, (115, 115, 120), 4)

    async def _fake_gen_clip_retry(*, client, clip_num: int, prompt_text: str, out_mp4: Path, **kwargs):
        seen_prompts[clip_num].append(prompt_text)
        attempt_idx = len(seen_prompts[clip_num])
        out_mp4.parent.mkdir(parents=True, exist_ok=True)
        vw = cv2.VideoWriter(str(out_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (640, 360))
        for fi in range(168):
            frm = np.full((360, 640, 3), (220, 224, 228), dtype=np.uint8)
            cv2.rectangle(frm, (40 + fi * 2 + clip_num * 25, 260), (150 + fi * 2 + clip_num * 25, 330), (130, 145, 160), -1)
            if attempt_idx == 1:
                _draw_sculpted_doll(frm)
            else:
                cv2.ellipse(frm, (260 + fi, 180), (65, 88), 0, 0, 360, (236, 236, 238), -1)
            vw.write(frm)
        vw.release()
        return {"ok": True, "clip_number": clip_num, "aspect": "16:9"}

    monkeypatch.setattr("pipeline.flow_live_single_worker.allocate_dedicated_flow_project_tab", _fake_alloc_tab)
    monkeypatch.setattr("pipeline.studio.whale_session.DirectCDPClient", _DummyCDPClient)
    monkeypatch.setattr("pipeline.longform_flow_worker._configure_longform_video_16x9_tab", _fake_cfg_16x9)
    monkeypatch.setattr("pipeline.longform_flow_worker._generate_single_longform_16x9_clip_in_tab", _fake_gen_clip_retry)

    receipt = asyncio.run(
        run_longform_sharded_flow_generation(
            p_dir,
            tabs=1,
            engine_mode="zero-credit",
            dry_run=False,
        )
    )
    assert receipt["passed"] is True
    assert receipt["completed_clips"] == [1, 2]
    assert len(seen_prompts[1]) == 2
    assert len(seen_prompts[2]) == 2
    assert "zero heads, zero busts, zero faces" in seen_prompts[1][1].lower()
    assert "head surface" not in seen_prompts[1][1].lower()
    assert "100% smooth featureless blank egg-shaped matte-white porcelain" in seen_prompts[2][1].lower()





