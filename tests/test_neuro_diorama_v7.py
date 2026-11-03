"""Schema v7 Full-Bleed Low-Poly Pastel Architecture tests (R63):
- SSOT constant & rule parity (config.py <-> production_constants.md, neuro_diorama_rules.md, AGENTS.md)
- Bundled static condensed extra-black font (`AABCondensed-Black.ttf`) verification
- Positive-only 3-tier face-excluding low-poly depiction rules & T5 Pink-Elephant / dark-void / filler rejection
- Waveform breath/silence trimming & 24.0fps half-open `[f0/fps, f1/fps)` zero-strobe / zero-overlap subtitle math
- Golden `phineas_gage_iron_rod/diorama_v7_lowpoly` prompt-gate & dossier fact trace
- End-to-end 24.0fps dynamic-CV (`CV >= 0.45`) NLE assembly + `split_hstack` 6px divider + 2ch stereo BGM + 100%-cut DQ1-DQ12 QA
"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
import hashlib
import json
import subprocess
import wave
from pathlib import Path

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline import research_dossier as rd
from pipeline.depiction_rules import (
    DIORAMA_V7_CAMERA_DESCRIPTORS,
    DioramaV7PromptComposer,
    LowPolyCutawaySectionRule,
    LowPolyHandsActionRule,
    LowPolyLiteralAnalogyRule,
    LowPolyWorldRule,
    MatteArchitecturalBrainRule,
    validate_lowpoly_v7_scene,
)
from pipeline.diorama_assembler import (
    _frame_boundary_ass_sec,
    assemble_diorama_project,
    ensure_bundled_condensed_font,
)
from pipeline.dynamic_episode_qa import (
    verify_final_mp4_against_contract,
    write_episode_qa_contract,
)
from pipeline.flow_prompt_builder import (
    build_diorama_v7_prompts,
    build_flow_prompts,
    validate_diorama_v7_prompts,
    write_flow_prompts_json,
)
from pipeline.media_integrity import MediaIntegrityValidator
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.video_autopsy import VideoAutopsyEngine
from pipeline.voice_fallback import (
    _compute_true_rms_voiced_ratio,
    _trim_waveform_silences_and_breaths,
)

ROOT = Path(cfg.WORKSPACE_ROOT)
GOLDEN_V7_DIR = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "phineas_gage_iron_rod" / "diorama_v7_lowpoly"


def test_diorama_v7_ssot_constants_and_bundled_font() -> None:
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    rules_md = (ROOT / ".agents" / "rules" / "neuro_diorama_rules.md").read_text(encoding="utf-8")
    agents_md = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")

    required_v7_names = (
        "PROMPT_SCHEMA_VERSION_V7",
        "DIORAMA_V7_STYLE_PROFILE",
        "DEFAULT_DIORAMA_STYLE_PROFILE",
        "DIORAMA_V7_WORLD_STYLE",
        "DIORAMA_V7_SHADER_STYLE",
        "DIORAMA_V7_OPTICS_LOCK",
        "DIORAMA_V7_LUMA_RANGE",
        "DIORAMA_V7_DARK_VOID_RATIO_MAX",
        "DIORAMA_V7_SATURATION_RANGE",
        "DIORAMA_V7_CUTAWAY_MAX_RATIO",
        "DIORAMA_V7_BRAIN_RENDER_MODES",
        "DIORAMA_V7_VISUAL_GRAMMARS",
        "DIORAMA_V7_CAMERA_MOVES",
        "DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO",
        "DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO",
        "DIORAMA_V7_VIDEO_FPS",
        "DIORAMA_V7_VISUAL_PLAYBACK_SPEED",
        "DIORAMA_V7_DURATION_MIN_SEC",
        "SHORTS_HARD_CEILING_FRAMES_V7",
        "DIORAMA_V7_RAPID_CUT_MIN_SEC",
        "DIORAMA_V7_MID_ACT_MAX_CUT_SEC",
        "DIORAMA_V7_LONG_TAKE_MAX_SEC",
        "DIORAMA_V7_CUT_CV_MIN",
        "DIORAMA_V7_SPLIT_MODE",
        "DIORAMA_V7_SPLIT_DIVIDER_PX",
        "DIORAMA_V7_TTS_RATE",
        "DIORAMA_V7_TTS_PITCH",
        "DIORAMA_V7_TTS_VOLUME",
        "DIORAMA_V7_TTS_SPEED",
        "DIORAMA_V7_SENTENCE_WORDS_MAX",
        "DIORAMA_BANNED_WEAK_HOOK_PREFIXES",
        "DIORAMA_V7_WPM_MIN",
        "DIORAMA_V7_WPM_MAX",
        "DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN",
        "DIORAMA_V7_AUDIO_CHANNELS",
        "DIORAMA_V7_BGM_DUCK_DB",
        "FONT_CONDENSED_BLACK_PATH",
        "DIORAMA_V7_SUBTITLE_FONT_NAME",
        "DIORAMA_V7_SUBTITLE_FONT_SIZE",
        "DIORAMA_V7_SUBTITLE_OUTLINE_WIDTH",
        "DIORAMA_V7_SUBTITLE_SHADOW_DEPTH",
        "DIORAMA_V7_SUBTITLE_MARGIN_V",
        "DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE",
        "DIORAMA_V7_CHAPTER_HEADLINE_OUTLINE_WIDTH",
        "DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_V",
        "POSTHOC_SEMANTIC_QA_REPORT_FILENAME",
        "POSTHOC_SEMANTIC_REVIEW_FILENAME",
        "POSTHOC_VIEWER_STRIPS_DIRNAME",
        "POSTHOC_CUTS_PER_VIEWER_SHEET",
        "POSTHOC_MIN_CUT_CLARITY_SCORE",
        "POSTHOC_MIN_EPISODE_MEAN_CLARITY_SCORE",
        "POSTHOC_MIN_SHARPNESS_LAPLACIAN",
        "POSTHOC_MIN_EDGE_DENSITY",
        "POSTHOC_MIN_FG_BG_CONTRAST_DE",
        "POSTHOC_MIN_MOVING_CAM_DIFF",
        "POSTHOC_LOCKED_TRIPOD_MIN_P95_DIFF",
        "POSTHOC_MAX_STEP_HIST_JUMP",
        "POSTHOC_SPLIT_PANE_MIN_DIFF",
        "POSTHOC_BRAIN_HIGHLIGHT_MIN_CHROMA",
        "POSTHOC_ANALOGY_SYNC_TOLERANCE_SEC",
        "POSTHOC_MIN_REVIEW_NOTE_CHARS",
        "POSTHOC_MAX_IDENTICAL_REVIEW_NOTES",
        "KNOWLEDGE_BASE_DIRNAME",
        "KNOWLEDGE_BASE_DIR",
        "KNOWLEDGE_TELEMETRY_DIRNAME",
        "EPISODES_INDEX_FILENAME",
        "CLIP_CLARITY_LEDGER_FILENAME",
        "QA_ANALYTICS_SUMMARY_FILENAME",
        "REUSABLE_PACKS_DIRNAME",
        "EXPERIMENTS_ARCHIVE_DIRNAME",
    )
    for name in required_v7_names:
        assert hasattr(cfg, name), f"Missing {name} in pipeline/config.py"
        assert name in constants_md, f"Missing {name} in .agents/rules/production_constants.md"

    assert "R63" in rules_md
    assert "R63" in agents_md
    assert "R64" in rules_md
    assert "R64" in agents_md
    assert "R66" in rules_md
    assert "R66" in agents_md
    assert cfg.DEFAULT_DIORAMA_STYLE_PROFILE == "porcelain_cinematic_v7"
    assert cfg.DIORAMA_V7_STYLE_PROFILE == "lowpoly_pastel_v7"
    assert set(cfg.DIORAMA_V7_STYLE_PROFILES) == {"porcelain_cinematic_v7", "lowpoly_pastel_v7"}
    assert cfg.DIORAMA_V7_TTS_RATE == "+8%"
    assert cfg.DIORAMA_V7_TTS_PITCH == "+14Hz"
    assert cfg.DIORAMA_V7_TTS_VOLUME == "-10%"
    assert cfg.DIORAMA_V7_TTS_SPEED == 1.08
    assert cfg.DIORAMA_V7_SENTENCE_WORDS_MAX == 18
    assert cfg.DIORAMA_V7_MID_ACT_MAX_CUT_SEC == 4.60
    assert cfg.DIORAMA_V7_VISUAL_PLAYBACK_SPEED == 1.00
    assert cfg.DIORAMA_V7_VIDEO_FPS == 24
    assert cfg.SHORTS_HARD_CEILING_FRAMES_V7 == 4296
    assert cfg.is_diorama_v7_plan({"schema": 7, "profile": "neuro_diorama"}) is True
    assert cfg.is_diorama_v7_plan({"schema": 6, "style_profile": "lowpoly_pastel_v7"}) is True
    assert cfg.is_diorama_v7_plan({"schema": 6, "style_profile": "porcelain_cinematic_v7"}) is True
    assert cfg.is_diorama_v7_plan({"schema": 6, "profile": "neuro_diorama"}) is False

    font_path = ensure_bundled_condensed_font()
    assert font_path.exists()
    assert font_path.stat().st_size >= 100_000


def test_lowpoly_v7_positive_depiction_rules_and_rejections() -> None:
    s_world = LowPolyWorldRule.compose(
        "a sunlit Vermont grey granite railroad cut with pine hills",
        "clothed low-poly rail workers in flat caps drill vertical boreholes",
    )
    s_hands = LowPolyHandsActionRule.compose(
        "rolled canvas sleeves and matte geometric hands",
        "both low-poly hands grip and lift a tapered iron bar",
        "sunlight glints along the iron shaft",
        pov=False,
    )
    s_pov = LowPolyHandsActionRule.compose(
        "tan duster coat sleeves extending from bottom frame",
        "both low-poly gloved hands pull six leather reins",
        "the wooden coach turns smoothly along the cliff road",
        pov=True,
    )
    s_cut = LowPolyCutawaySectionRule.compose(
        "a grey granite bedrock ledge with a vertical borehole",
        "pale dry sand pours down to seal black powder granules",
    )
    s_ana = LowPolyLiteralAnalogyRule.compose(
        "a sunlit green-turf football stadium field with white yard lines",
        "an iron rod arcs cleanly across one quarter of the field",
    )
    s_brain_c = MatteArchitecturalBrainRule.compose(
        "terracotta-coral shading marks four percent of the left prefrontal cortex",
        brain_mode="matte_pastel_cortical_model",
    )
    s_brain_s = MatteArchitecturalBrainRule.compose(
        "severed white-matter cables separate the amygdala from the prefrontal cortex",
        brain_mode="matte_pastel_sagittal_cutaway",
    )

    for g, sc in (
        ("lowpoly_fullbleed_world", s_world),
        ("lowpoly_hands_closeup", s_hands),
        ("lowpoly_pov_hands", s_pov),
        ("lowpoly_cutaway_section", s_cut),
        ("lowpoly_literal_analogy", s_ana),
        ("lowpoly_matte_brain", s_brain_c),
        ("lowpoly_matte_brain", s_brain_s),
    ):
        prompt = DioramaV7PromptComposer.compose_clip_prompt(sc, grammar=g, camera_move="locked_tripod")
        assert validate_lowpoly_v7_scene(prompt, grammar=g) == []
        assert prompt.count(DIORAMA_V7_CAMERA_DESCRIPTORS["locked_tripod"]) == 1

    # Reject T5 Pink-Elephant negative noun lists
    bad_pink = s_world + " Zero eyes, zero nose, zero plaques, zero letters."
    pink_errs = validate_lowpoly_v7_scene(bad_pink, grammar="lowpoly_fullbleed_world")
    assert any("Pink-Elephant" in e for e in pink_errs)

    # Reject legacy dark-void, plinth, bokeh, and bisque-ceramic tokens
    bad_legacy = s_world + " Isolated in a deep midnight-navy studio void on a museum plinth with creamy bokeh."
    leg_errs = validate_lowpoly_v7_scene(bad_legacy, grammar="lowpoly_fullbleed_world")
    assert any("banned legacy" in e for e in leg_errs)

    # Reject camera imbalance (0 locked_tripod, >30% zoom, missing pan_left)
    imbalanced_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "clips": [
            {
                "sentence_index": i + 1,
                "act": (i % 6) + 1,
                "grammar": "lowpoly_fullbleed_world",
                "camera": "gentle_push_in",
                "environment": "a sunlit grey granite railroad cut with pine hills",
                "action": "clothed low-poly workers in caps lift and align iron rails",
            }
            for i in range(20)
        ],
    }
    imb_clips = build_diorama_v7_prompts(imbalanced_plan)
    imb_errs = validate_diorama_v7_prompts(imb_clips)
    assert any("locked_tripod ratio" in e for e in imb_errs)
    assert any("push/pull zoom ratio" in e for e in imb_errs)
    assert any("pan direction imbalance" in e for e in imb_errs)


def test_waveform_breath_trimming_and_zero_strobe_frame_grid_math() -> None:
    sr = 48000
    t_voice = np.arange(int(0.80 * sr), dtype=np.float32) / float(sr)
    burst = (0.35 * np.sin(2.0 * np.pi * 165.0 * t_voice)).astype(np.float32)
    lead_sil = np.zeros(int(0.30 * sr), dtype=np.float32)
    mid_gap = np.zeros(int(0.42 * sr), dtype=np.float32)
    tail_sil = np.zeros(int(0.35 * sr), dtype=np.float32)
    raw = np.concatenate([lead_sil, burst, mid_gap, burst, tail_sil])
    orig_words = [(0.32, 1.08, "First"), (1.55, 2.30, "Second")]

    trimmed, shifted_words = _trim_waveform_silences_and_breaths(raw, sr, word_list=orig_words)
    # 0.80 + 0.80 = 1.60s voiced + ~0.06s kept breath + tiny edge pads -> ~1.72s (down from 2.67s)
    assert 1.62 <= (len(trimmed) / float(sr)) <= 1.80
    assert len(shifted_words) == 2 and shifted_words[1][0] < 1.05
    assert _compute_true_rms_voiced_ratio(trimmed, sr) >= cfg.DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN

    # Prove half-open 24fps ASS centisecond quantization has 0-frame gap and 0-frame overlap across all 4,296 frames
    fps = cfg.DIORAMA_V7_VIDEO_FPS
    for f in range(1, cfg.SHORTS_HARD_CEILING_FRAMES_V7 + 1):
        ts = _frame_boundary_ass_sec(f, fps)
        t_prev_frame = (f - 1) / float(fps)
        t_curr_frame = f / float(fps)
        assert t_prev_frame < ts < t_curr_frame, f"Boundary at frame {f} ({ts}) failed strict separation"


def test_golden_gage_diorama_v7_lowpoly_blueprint_and_contract() -> None:
    script_doc = json.loads((GOLDEN_V7_DIR / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((GOLDEN_V7_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]

    assert cfg.is_diorama_v7_plan(visual_plan) is True
    assert cfg.is_diorama_v7_plan(script_doc) is True

    clips = build_flow_prompts(visual_plan, sentences)
    assert len(clips) == len(visual_plan["clips"]) >= cfg.DIORAMA_TARGET_CUT_MIN
    assert validate_diorama_v7_prompts(clips) == []

    issues = validate_production_diorama_v6(visual_plan, sentences, clips, script_doc=script_doc)
    fact_issues = rd.check_narration_facts("phineas_gage_iron_rod", sentences)
    assert issues == [], f"Unexpected v7 prompt-gate issues: {issues}"
    assert fact_issues == [], f"Unexpected dossier fact issues: {fact_issues}"

    # Verify filler water-tumbler / beam-scale prop is explicitly rejected in Schema v7
    bad_clips = [dict(c) for c in clips]
    bad_clips[3] = dict(bad_clips[3], scene=bad_clips[3]["scene"] + " Beside a clear glass water tumbler and beam scale.")
    filler_issues = validate_production_diorama_v6(visual_plan, sentences, bad_clips, script_doc=script_doc)
    assert any("[filler_ban_v7]" in e for e in filler_issues)


def _make_synthetic_v7_lowpoly_clip(dst: Path, idx: int, ffmpeg_exe: str, green_turf: bool = False) -> None:
    """Renders an 8.0s 720x1280@24.0fps bright pastel moving clip > 1MB (matching Flow 720p native clips)."""
    if green_turf:
        bg = "color=c=#4fa858:size=720x1280:rate=24:duration=8.0"
        box_a, box_b = "#e8f2e6@0.90", "#d98a5f@0.88"
    else:
        palettes = ("#b8c9d9", "#cbd6c4", "#e3d9c6", "#c6d4e1", "#d8cfc2")
        bg = f"color=c={palettes[idx % len(palettes)]}:size=720x1280:rate=24:duration=8.0"
        box_a, box_b = "#6f879e@0.92", "#c97a63@0.90"
    sx = 64 + (idx % 5) * 18
    sy = 72 + (idx % 4) * 20
    w1 = 156 + idx
    h1 = 156 + ((idx * 3) % 48)
    x0 = (idx * 11) % 180
    vf = (
        f"drawgrid=w=80:h=96:t=4:c=#8da1b5@0.65,"
        f"drawgrid=w=160:h=192:t=5:c=#73889c@0.55,"
        "scroll=horizontal=0.012:vertical=0.008,"
        f"drawbox=x='mod({x0}+t*{sx},500)':y='80+mod(t*{sy},360)':w={w1}:h={h1}:color={box_a}:t=fill,"
        f"drawbox=x='500-mod({x0}+t*{sx},480)':y='460+mod(t*{sy // 2},360)':w=150:h=150:color={box_b}:t=fill,"
        "format=yuv420p"
    )
    cmd = [
        ffmpeg_exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", bg,
        "-vf", vf,
        "-r", "24",
        "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-b:v", "2200k", "-maxrate", "2700k", "-bufsize", "3600k",
        "-pix_fmt", "yuv420p", "-an",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180, stdin=subprocess.DEVNULL)


@pytest.mark.slow
def test_end_to_end_diorama_v7_24fps_assembly_split_hstack_stereo_and_100pct_qa(tmp_path: Path) -> None:
    proj_dir = tmp_path / "gage_diorama_v7_e2e"
    (proj_dir / "02_script").mkdir(parents=True)
    (proj_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj_dir / "03_visuals" / "flow_screenshots").mkdir(parents=True)
    (proj_dir / "04_audio").mkdir(parents=True)
    (proj_dir / "05_assembly").mkdir(parents=True)
    (proj_dir / "06_publish").mkdir(parents=True)

    script_doc = json.loads((GOLDEN_V7_DIR / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((GOLDEN_V7_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]

    (proj_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(visual_plan, indent=2), encoding="utf-8")
    clips_meta = build_flow_prompts(visual_plan, sentences)
    write_flow_prompts_json(proj_dir, clips_meta)
    _, contract = write_episode_qa_contract(proj_dir, visual_plan, sentences, clips_meta, script_doc=script_doc)

    green_clip_nums = {
        n
        for lock in contract["analogy_locks"]
        if lock["cv_signature"] == "green_stadium_turf"
        for n in lock["bound_clip_numbers"]
    }

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    n_clips = len(clips_meta)
    clip_paths = [proj_dir / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4" for i in range(1, n_clips + 1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(
            pool.map(
                lambda p: _make_synthetic_v7_lowpoly_clip(p[1], p[0], ff, green_turf=(p[0] in green_clip_nums)),
                enumerate(clip_paths, start=1),
            )
        )

    receipt_clips = [
        {
            "clip_index": i,
            "sha256": hashlib.sha256(cf.read_bytes()).hexdigest(),
            "file_size_bytes": cf.stat().st_size,
            "source_download_filename": f"flow_diorama_v7_clip_{i:02d}.mp4",
        }
        for i, cf in enumerate(clip_paths, start=1)
    ]

    scr_dir = proj_dir / "03_visuals" / "flow_screenshots"
    scr_rng = np.random.default_rng(77)
    for g_idx, ss_name in enumerate(
        (
            "flow_gate_v1_prompt_approved.png",
            "flow_gate_v2_rendering_active.png",
            "flow_gate_v3_canvas_clips_ready.png",
            "flow_gate_v4_export_ready.png",
        ),
        start=1,
    ):
        img = scr_rng.integers(90 + g_idx * 10, 215, size=(360, 640, 3), dtype=np.uint8)
        cv2.imwrite(str(scr_dir / ss_name), img)
    (scr_dir / "visual_qa_report.json").write_text(
        json.dumps(
            {
                "all_passed": True,
                "gate_v1": {"status": "PASS"},
                "gate_v2": {"status": "PASS"},
                "gate_v3": {"status": "PASS"},
                "gate_v4": {"status": "PASS"},
                "gate_v5": {"status": "PASS"},
            }
        ),
        encoding="utf-8",
    )
    (proj_dir / "03_visuals" / "flow_provenance_receipt.json").write_text(
        json.dumps(
            {
                "project_id": proj_dir.name,
                "worker_id": f"subagent-{proj_dir.name}",
                "subagent_1_to_1_bound": True,
                "visual_gates_passed": True,
                "flow_project_url": "https://flow.google.com/project/77a1b2c3-44d5-4e66-8f99-0123456789ab",
                "tab_target_id": "TAB_DIORAMA_V7_01",
                "prompts_submitted_count": n_clips,
                "clips": receipt_clips,
            },
            indent=2,
        ),
        encoding="utf-8",
    )

    # Synthesize continuous voiced lines (~2.85s avg x 56 sentences -> ~162s + 2.2s outro = ~164.2s @ 24fps)
    sr = 48000
    synth_lines: list[np.ndarray] = []
    rng = np.random.default_rng(2026)
    for s_idx, sent in enumerate(sentences):
        dur = 2.75 + 0.05 * (len(sent.split()) - 8)
        n = int(round(dur * sr))
        t = np.arange(n, dtype=np.float32) / float(sr)
        syl_env = 0.58 + 0.42 * np.sin(2.0 * np.pi * 4.4 * t + s_idx)
        carrier = (
            0.55 * np.sin(2.0 * np.pi * 124.0 * t)
            + 0.28 * np.sin(2.0 * np.pi * 248.0 * t)
            + 0.05 * rng.standard_normal(n).astype(np.float32)
        )
        fade = np.minimum(1.0, np.minimum(t / 0.025, (dur - t) / 0.035)).astype(np.float32)
        synth_lines.append((0.44 * carrier * syl_env * fade).astype(np.float32))

    res = assemble_diorama_project(
        proj_dir,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=synth_lines,
    )

    final_mp4 = Path(res["final_mp4"])
    assert final_mp4.exists()
    assert cfg.DIORAMA_V7_DURATION_MIN_SEC <= res["duration_sec"] <= cfg.SHORTS_HARD_CEILING_SEC

    edl = json.loads(Path(res["edl_path"]).read_text(encoding="utf-8"))
    assert edl["schema"] == 7
    assert edl["fps"] == 24
    assert edl["total_frames"] <= cfg.SHORTS_HARD_CEILING_FRAMES_V7
    assert edl["zero_clip_reuse"] is True
    assert edl["max_clip_reuse"] == 1
    assert edl["cut_duration_cv"] >= cfg.DIORAMA_V7_CUT_CV_MIN
    assert edl["rapid_cut_ratio"] >= 0.20
    assert edl["aba_location_returns"] >= 2
    assert edl["split_hstack_cuts"] >= 1

    # Verify 2-channel decorrelated stereo audio master
    with wave.open(str(proj_dir / "04_audio" / "audio_master.wav"), "rb") as wf:
        assert wf.getnchannels() == 2
        assert wf.getframerate() == 48000
        pcm = np.frombuffer(wf.readframes(wf.getnframes()), dtype=np.int16).astype(np.float32).reshape(-1, 2)
    side_ratio = float(np.std(pcm[:, 0] - pcm[:, 1]) / max(1e-6, np.std(pcm[:, 0] + pcm[:, 1])))
    assert side_ratio > 0.008, f"Expected decorrelated 2ch stereo BGM, got side_ratio={side_ratio}"

    # Verify ASS typography: AAB Condensed Black, Shadow=0.0, MarginV=672, ChapterHeadline 276pt, SplitLeft/Right
    ass_txt = Path(res["ass_path"]).read_text(encoding="utf-8")
    assert f"Style: Default,{cfg.DIORAMA_V7_SUBTITLE_FONT_NAME}," in ass_txt
    assert f",{cfg.DIORAMA_V7_SUBTITLE_MARGIN_V},1" in ass_txt
    assert f"Style: ChapterHeadline,{cfg.DIORAMA_V7_SUBTITLE_FONT_NAME},{cfg.DIORAMA_V7_CHAPTER_HEADLINE_FONT_SIZE}," in ass_txt
    assert "SplitLeft" in ass_txt and "SplitRight" in ass_txt

    # Verify split_hstack 6px black vertical divider at x=537..543 on decoded MP4
    split_cut = next(c for c in edl["cuts"] if c["mode"] == "split_hstack")
    cap = cv2.VideoCapture(str(final_mp4))
    assert abs(float(cap.get(cv2.CAP_PROP_FPS)) - 24.0) < 0.15
    mid_f = int(round(0.5 * (float(split_cut["out_start_sec"]) + float(split_cut["out_end_sec"])) * 24.0))
    cap.set(cv2.CAP_PROP_POS_FRAMES, mid_f)
    ok, split_frm = cap.read()
    cap.release()
    assert ok and split_frm is not None
    divider_luma = float(np.mean(split_frm[650:1050, 538:542]))
    left_luma = float(np.mean(split_frm[650:1050, 180:420]))
    right_luma = float(np.mean(split_frm[650:1050, 660:900]))
    assert divider_luma < 24.0 and left_luma > 80.0 and right_luma > 80.0

    probe_rep = MediaIntegrityValidator.validate_video_file(
        final_mp4,
        require_30s_shorts=True,
        check_motion=True,
        check_audio=True,
        strict=True,
    )
    assert probe_rep["passed"] is True, f"MediaIntegrity failed: {probe_rep}"
    assert probe_rep["frame_count"] <= cfg.SHORTS_HARD_CEILING_FRAMES_V7

    autopsy = VideoAutopsyEngine.inspect_project(proj_dir, save_report=True)
    assert autopsy["passed"] is True, f"Autopsy failed: {autopsy['prescriptions']}"
    assert autopsy["defects"] == []

    # Full 100%-cut DQ1-DQ12 contract verification (skipping Whisper ASR only on synthetic sine tone)
    dq_rep = verify_final_mp4_against_contract(proj_dir, run_asr_sync=False)
    assert dq_rep["passed"] is True, f"DQ1-DQ12 failed: {dq_rep}"
    assert dq_rep["score"] == 100.0


def test_v7_typography_word_spacing_and_glyph_heights(tmp_path: Path) -> None:
    from fontTools.ttLib import TTFont
    from pipeline.diorama_assembler import generate_diorama_ass_subtitles

    font_path = ensure_bundled_condensed_font()
    tt = TTFont(str(font_path))
    cmap = tt.getBestCmap() or {}
    hmtx = tt["hmtx"].metrics
    space_adv = hmtx[cmap[0x20]][0]
    h_adv = hmtx[cmap[ord("H")]][0]
    assert space_adv >= 440, f"Space advance width ({space_adv}) must remain uncondensed (>314) so words never fuse"
    assert h_adv / float(space_adv) <= 3.0, f"Letter-to-space ratio ({h_adv}/{space_adv}) too high"

    ass_path = tmp_path / "typo_check.ass"
    generate_diorama_ass_subtitles(
        ass_path,
        events=[(0.0, 2.0, ["Iron", "rod", "blasted"])],
        sentence_spans=[{"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.0, "act_boundary_after": False}],
        visual_plan={
            "schema": 7,
            "profile": "neuro_diorama",
            "style_profile": "lowpoly_pastel_v7",
            "chapter_headlines": [{"sentence_index": 1, "text": "1848 BLAST"}],
        },
        edl={"schema": 7, "fps": 24, "speech_end_sec": 2.0, "total_duration_sec": 3.0, "total_frames": 72, "cuts": []},
    )
    png_path = tmp_path / "typo_frame.png"
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    ass_esc = str(ass_path).replace("\\", "/").replace(":", "\\:")
    fdir_esc = str(font_path.parent).replace("\\", "/").replace(":", "\\:")
    subprocess.run(
        [
            ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=#7a8ea1:s=1080x1920:r=24:d=0.5",
            "-vf", f"subtitles='{ass_esc}':fontsdir='{fdir_esc}'",
            "-frames:v", "1", str(png_path),
        ],
        check=True,
    )
    frm = cv2.imread(str(png_path))
    assert frm is not None
    # Top headline ROI: pure-white glyph height ~144px and crisp >=35px inter-word gap between '1848' and 'BLAST'
    top_white = (frm[80:460, :, 0] > 235) & (frm[80:460, :, 1] > 235) & (frm[80:460, :, 2] > 235)
    ys_top, xs_top = np.where(top_white)
    headline_h = int(ys_top.max() - ys_top.min() + 1)
    assert 130 <= headline_h <= 165, f"Expected ~144px chapter headline height, got {headline_h}px"
    col_counts = top_white.sum(axis=0)
    active_x = np.where(col_counts > 0)[0]
    zero_cols_between = np.where(col_counts[active_x[0] : active_x[-1] + 1] == 0)[0]
    assert len(zero_cols_between) >= 35, f"Expected >=35px clean word gap in '1848 BLAST', got {len(zero_cols_between)}px"

    # Subtitle ROI: vertical white glyph height >= 50px (~52px parity with @신비한_건축사전)
    sub_white = (frm[1100:1320, :, 0] > 235) & (frm[1100:1320, :, 1] > 235) & (frm[1100:1320, :, 2] > 235)
    ys_sub, _ = np.where(sub_white)
    sub_h = int(ys_sub.max() - ys_sub.min() + 1)
    assert 48 <= sub_h <= 70, f"Expected ~52-62px subtitle glyph height, got {sub_h}px"


def test_v7_verb_traps_pastel_grading_and_dossier_batch_sync(tmp_path: Path, monkeypatch) -> None:
    from pipeline import diorama_batch_orchestrator as dbo
    from pipeline.diorama_assembler import _compute_v7_pastel_eq_filter

    base_world = LowPolyWorldRule.compose(
        "a sunlit Vermont grey granite railroad cut with pine hills",
        "clothed low-poly rail workers in flat caps lift iron rails",
    )
    for bad_snippet, label in (
        ("An iron rod rockets upward like a missile.", "verb_trap"),
        ("A front-facing bearded worker stares at camera.", "face_trap"),
        ("Hands hold a graduated glass beaker and pocket compass.", "text_prop"),
        ("The rod lands on the twenty-five yard line beside playing cards.", "numbered_turf_or_cards"),
    ):
        p = DioramaV7PromptComposer.compose_clip_prompt(
            base_world + " " + bad_snippet,
            grammar="lowpoly_fullbleed_world",
            camera_move="locked_tripod",
        )
        errs = validate_lowpoly_v7_scene(p, grammar="lowpoly_fullbleed_world")
        assert errs, f"Expected validate_lowpoly_v7_scene to reject {label}: {bad_snippet}"

    # Verify adaptive pastel saturation grading attenuates oversaturated clips while preserving pastel clips
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    vivid_clip = tmp_path / "vivid.mp4"
    pastel_clip = tmp_path / "pastel.mp4"
    for c_hex, out_p in (("#d9531e", vivid_clip), ("#b8c9d9", pastel_clip)):
        subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", f"color=c={c_hex}:s=320x568:r=24:d=0.5",
                "-pix_fmt", "yuv420p", str(out_p),
            ],
            check=True,
        )
    vivid_eq = _compute_v7_pastel_eq_filter(vivid_clip)
    pastel_eq = _compute_v7_pastel_eq_filter(pastel_clip)
    vivid_sat = float(vivid_eq.split("saturation=")[1].split(":")[0])
    pastel_sat = float(pastel_eq.split("saturation=")[1].split(":")[0])
    assert vivid_sat <= 0.55, f"Expected strong saturation attenuation on vivid clip, got {vivid_eq}"
    assert pastel_sat == 1.0, f"Expected pastel clip saturation=1.0, got {pastel_eq}"

    # Verify diorama_seed_from_dossier defaults to Schema v7 porcelain_cinematic_v7 (and supports explicit lowpoly_pastel_v7) without banned filler props
    seeded_vp = rd.diorama_seed_from_dossier("phineas_gage_iron_rod")
    assert cfg.is_diorama_v7_plan(seeded_vp) is True
    assert cfg.is_porcelain_v7_plan(seeded_vp) is True
    assert seeded_vp["style_profile"] == "porcelain_cinematic_v7"
    assert "motif_prop" not in seeded_vp
    assert "water tumbler" not in json.dumps(seeded_vp).lower()
    seeded_lp = rd.diorama_seed_from_dossier("phineas_gage_iron_rod", style_profile="lowpoly_pastel_v7")
    assert cfg.is_diorama_v7_plan(seeded_lp) is True
    assert cfg.is_porcelain_v7_plan(seeded_lp) is False
    assert seeded_lp["style_profile"] == "lowpoly_pastel_v7"
    seeded_v6 = rd.diorama_seed_from_dossier("phineas_gage_iron_rod", schema_version=6)
    assert cfg.is_diorama_v7_plan(seeded_v6) is False

    # Verify batch orchestrator sync preserves Schema v7 from diorama_v7_lowpoly into isolated tmp projects dir
    import shutil
    from pipeline import storage as st_mod

    fake_projects = tmp_path / "isolated_projects"
    fake_dossier = tmp_path / "isolated_dossier" / "phineas_gage_iron_rod"
    (fake_dossier / "diorama_v7_lowpoly").mkdir(parents=True)
    shutil.copy2(GOLDEN_V7_DIR.parent / "dossier.json", fake_dossier / "dossier.json")
    shutil.copy2(GOLDEN_V7_DIR.parent / "01_sources.json", fake_dossier / "01_sources.json")
    shutil.copy2(GOLDEN_V7_DIR / "script.json", fake_dossier / "diorama_v7_lowpoly" / "script.json")
    shutil.copy2(GOLDEN_V7_DIR / "visual_plan.json", fake_dossier / "diorama_v7_lowpoly" / "visual_plan.json")
    monkeypatch.setattr(dbo, "PROJECTS_DIR", fake_projects)
    monkeypatch.setattr(st_mod, "PROJECTS_DIR", fake_projects)
    monkeypatch.setattr(rd, "dossier_dir", lambda slug, root=None: fake_dossier)
    synced_proj = dbo.sync_project_from_dossier_diorama(
        {"project_id": "gage_v7_sync_test", "slug": "phineas_gage_iron_rod", "pillar": "P5"}
    )
    synced_sc = json.loads((synced_proj / "02_script" / "script.json").read_text(encoding="utf-8"))
    synced_vp = json.loads((synced_proj / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    assert synced_sc["schema_version"] == 7
    assert synced_sc["style_profile"] == "lowpoly_pastel_v7"
    assert cfg.is_diorama_v7_plan(synced_vp) is True


def test_v7_round2_headline_safe_margins_edl_cameras_and_escher_guards(tmp_path: Path) -> None:
    import cv2

    from pipeline.diorama_assembler import build_v7_dynamic_edl, generate_diorama_ass_subtitles
    from pipeline.dynamic_episode_qa import measure_chapter_headline_bbox
    from pipeline.flow_diorama_sharded_worker import detect_escher_dual_edge_closeup

    # 1. SSOT parity for ChapterHeadline horizontal safe-margin constants
    constants_doc = (cfg.WORKSPACE_ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    for cname in (
        "DIORAMA_V7_CHAPTER_HEADLINE_SCALE_X",
        "DIORAMA_V7_CHAPTER_HEADLINE_MARGIN_LR",
        "DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX",
    ):
        assert cname in constants_doc, f"{cname} missing from production_constants.md"
    assert cfg.DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX == 920

    # 2. Rendered ChapterHeadline width <= 920px and >= 75px side margins on 10-char headlines ('1848 BLAST', 'YOUR BRAIN')
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    font_path = ensure_bundled_condensed_font()
    fdir_esc = str(font_path.parent).replace("\\", "/").replace(":", "\\:")
    for idx_h, headline in enumerate(("1848 BLAST", "YOUR BRAIN")):
        ass_h = tmp_path / f"head_{idx_h}.ass"
        png_h = tmp_path / f"head_{idx_h}.png"
        generate_diorama_ass_subtitles(
            ass_h,
            events=[(0.0, 2.0, ["Test", "subtitle", "line."])],
            sentence_spans=[{"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.0, "act_boundary_after": False}],
            visual_plan={
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "chapter_headlines": [{"sentence_index": 1, "text": headline}],
            },
            edl={"schema": 7, "fps": 24, "speech_end_sec": 2.0, "total_duration_sec": 3.0, "total_frames": 72, "cuts": []},
        )
        ass_esc = str(ass_h).replace("\\", "/").replace(":", "\\:")
        subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=#a8b8c8:s=1080x1920:d=0.5:r=24",
                "-vf", f"subtitles='{ass_esc}':fontsdir='{fdir_esc}'",
                "-frames:v", "1", str(png_h),
            ],
            check=True,
        )
        frm_h = cv2.imread(str(png_h))
        assert frm_h is not None
        w_px, lm_px, rm_px = measure_chapter_headline_bbox(frm_h)
        assert 650 <= w_px <= cfg.DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX, (
            f"Headline '{headline}' width {w_px}px exceeded {cfg.DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX}px"
        )
        assert lm_px >= 75 and rm_px >= 75, f"Headline '{headline}' side margins too tight: left={lm_px}, right={rm_px}"

    # 3. Close-up prompt guards: surgical prongs, multi-person disembodied hands, and neck-down + bottom-frame Escher trap
    bad_surg = LowPolyHandsActionRule.compose(
        "dark wool coat cuffs and steady low-poly hands",
        "the physician's low-poly hands lift a silver surgical instrument over a white basin",
        "warm morning light gleams on the rim",
        pov=False,
    )
    assert any(
        "surgical instrument" in e
        for e in validate_lowpoly_v7_scene(
            DioramaV7PromptComposer.compose_clip_prompt(bad_surg, "lowpoly_hands_closeup", "locked_tripod"),
            grammar="lowpoly_hands_closeup",
        )
    )

    bad_multi = LowPolyHandsActionRule.compose(
        "two pairs of dark wool coat sleeves and matte low-poly hands",
        "four steady low-poly hands lower a plain wooden box",
        "the box settles on porch planks",
        pov=False,
    )
    assert any(
        "disembodied-limb" in e
        for e in validate_lowpoly_v7_scene(
            DioramaV7PromptComposer.compose_clip_prompt(bad_multi, "lowpoly_hands_closeup", "locked_tripod"),
            grammar="lowpoly_hands_closeup",
        )
    )

    bad_escher = LowPolyHandsActionRule.compose(
        "single pair of tan coat sleeves extending cleanly from the bottom frame edge",
        "two steady low-poly hands align six brass coins",
        "all six coins rest in two stacks",
        pov=False,
    )
    assert any(
        "Escher" in e
        for e in validate_lowpoly_v7_scene(
            DioramaV7PromptComposer.compose_clip_prompt(bad_escher, "lowpoly_hands_closeup", "locked_tripod"),
            grammar="lowpoly_hands_closeup",
        )
    )
    good_pov = LowPolyHandsActionRule.compose(
        "single pair of tan coat sleeves extending cleanly from the bottom frame edge",
        "two steady low-poly hands align six brass coins",
        "all six coins rest in two stacks",
        pov=True,
    )
    assert (
        validate_lowpoly_v7_scene(
            DioramaV7PromptComposer.compose_clip_prompt(good_pov, "lowpoly_pov_hands", "locked_tripod"),
            grammar="lowpoly_pov_hands",
        )
        == []
    )

    # 4. CV Escher dual-edge & plaque detectors:
    #    - flags matching suit sleeves at top & bottom across tan tabletop gap
    #    - passes single-edge POV and outdoor bright pastel-sky POV
    #    - flags both light-on-dark and dark-on-light plaques while ignoring gravel speckles
    from pipeline.flow_diorama_sharded_worker import _max_horizontal_plaque_glyph_run

    desk_bgr = np.full((640, 360, 3), (145, 180, 210), dtype=np.uint8)  # warm tan wooden desk
    escher_frm = desk_bgr.copy()
    escher_frm[0:95, 50:310] = (85, 115, 70)   # green-suited torso/collar hanging from top border
    escher_frm[445:640, 45:315] = (85, 115, 70)  # matching green-suited sleeves rising from bottom border
    assert detect_escher_dual_edge_closeup(escher_frm, "lowpoly_hands_closeup") is True

    clean_pov_frm = desk_bgr.copy()
    clean_pov_frm[445:640, 45:315] = (85, 115, 70)  # sleeves only from bottom border
    assert detect_escher_dual_edge_closeup(clean_pov_frm, "lowpoly_pov_hands") is False

    outdoor_sky_pov = desk_bgr.copy()
    outdoor_sky_pov[0:105, :] = (212, 195, 175)     # bright pastel blue outdoor sky at top border
    outdoor_sky_pov[460:640, 40:320] = (88, 72, 62)  # dark slate sleeves rising from bottom border
    assert detect_escher_dual_edge_closeup(outdoor_sky_pov, "lowpoly_pov_hands") is False

    dark_plaque = np.full((240, 720, 3), 42, dtype=np.uint8)
    cv2.putText(dark_plaque, "STATION 1848", (140, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (235, 235, 235), 2, cv2.LINE_AA)
    assert _max_horizontal_plaque_glyph_run(dark_plaque) >= 5

    light_plaque = np.full((240, 720, 3), 215, dtype=np.uint8)
    cv2.putText(light_plaque, "CAVENDISH", (160, 130), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (30, 30, 30), 2, cv2.LINE_AA)
    assert _max_horizontal_plaque_glyph_run(light_plaque) >= 5

    rng_gravel = np.random.default_rng(1848)
    gravel = rng_gravel.integers(75, 210, size=(240, 720, 3), dtype=np.uint8)
    gravel = cv2.GaussianBlur(gravel, (3, 3), 0)
    assert _max_horizontal_plaque_glyph_run(gravel) < 5

    # Continuous horizontal wooden tray molding with slight specular grain ripples (no return to background) is not text
    tray_rim = np.full((240, 720, 3), 85, dtype=np.uint8)
    tray_rim[115:126, 80:640] = 180
    for rx in range(110, 610, 14):
        tray_rim[116:125, rx : rx + 9] = 196
    assert _max_horizontal_plaque_glyph_run(tray_rim) < 5

    # 5. build_v7_dynamic_edl populates camera_move on every cut (including outro) and reports camera ratios
    dummy_clips = tmp_path / "dummy_clips"
    dummy_clips.mkdir()
    vp_gold = json.loads((GOLDEN_V7_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sc_gold = json.loads((GOLDEN_V7_DIR / "script.json").read_text(encoding="utf-8"))
    sents_gold = sc_gold["sentences"]
    clip_files: list[Path] = []
    for idx_c in range(1, len(vp_gold["clips"]) + 1):
        cp = dummy_clips / f"clip_{idx_c}.mp4"
        cp.write_bytes(b"0" * 1024)
        clip_files.append(cp)
    fake_spans = [
        {
            "sentence_index": i + 1,
            "start_sec": round(i * 2.8, 3),
            "end_sec": round((i + 1) * 2.8 - 0.08, 3),
            "act_boundary_after": False,
        }
        for i in range(len(sents_gold))
    ]
    speech_end = round(len(sents_gold) * 2.8, 3)
    edl = build_v7_dynamic_edl(
        visual_plan=vp_gold,
        sentence_spans=fake_spans,
        clip_files=clip_files,
        speech_end_sec=speech_end,
        total_duration_sec=round(speech_end + 3.0, 3),
        script_doc=sc_gold,
    )
    assert len(edl["cuts"]) >= cfg.DIORAMA_TARGET_CUT_MIN
    assert all(c.get("camera_move") in cfg.DIORAMA_V7_CAMERA_MOVES for c in edl["cuts"])
    assert edl["locked_camera_ratio"] >= cfg.DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO
    assert edl["zoom_camera_ratio"] <= cfg.DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO
    assert edl["pan_left_cuts"] >= 1 and edl["pan_right_cuts"] >= 1


def test_v7_round3_reviewer_regressions(tmp_path: Path) -> None:
    import cv2

    from pipeline.diorama_assembler import generate_diorama_ass_subtitles
    from pipeline.dynamic_episode_qa import compile_episode_qa_contract, measure_chapter_headline_bbox
    from pipeline.flow_diorama_sharded_worker import detect_transient_top_intrusion_pov

    # 1. Expanded prong tokens (tweezers, tongs, prongs, clamps, pincers, scissors) blocked in v7 scenes
    for prong_word in ("tweezers", "tongs", "prongs", "clamps", "pincers", "scissors"):
        bad_prong = LowPolyHandsActionRule.compose(
            "dark wool coat cuffs and low-poly hands",
            f"steady low-poly hands grip brass {prong_word} over a wooden tray",
            "the wooden block settles cleanly",
            pov=False,
        )
        p_prong = DioramaV7PromptComposer.compose_clip_prompt(bad_prong, "lowpoly_hands_closeup", "locked_tripod")
        errs_prong = validate_lowpoly_v7_scene(p_prong, grammar="lowpoly_hands_closeup", camera_move="locked_tripod")
        assert errs_prong, f"Expected '{prong_word}' to be blocked by validate_lowpoly_v7_scene"

    # 2. lowpoly_hands_closeup + tilt_up rejected (prevents tilting up past collar onto face, Cut #07 bug)
    clean_hands = LowPolyHandsActionRule.compose(
        "dark wool coat cuffs and gloved low-poly hands",
        "steady gloved low-poly hands press a brass stamp onto sealing wax",
        "a crisp wax seal rests on parchment",
        pov=False,
    )
    p_tilt = DioramaV7PromptComposer.compose_clip_prompt(clean_hands, "lowpoly_hands_closeup", "tilt_up")
    errs_tilt = validate_lowpoly_v7_scene(p_tilt, grammar="lowpoly_hands_closeup", camera_move="tilt_up")
    assert any("tilt_up" in e for e in errs_tilt)
    assert validate_diorama_v7_prompts(
        [
            {
                "clip_number": 7,
                "grammar": "lowpoly_hands_closeup",
                "camera_move": "tilt_up",
                "scene": clean_hands,
                "prompt": p_tilt,
            }
        ]
    )

    # 3. PIL glyph-metric ChapterHeadline auto-scaling on pure #FFFFFF white background ("MMMMM MMMM" & "1848 CAVENDISH VT")
    #    plus 84pt mobile-legible SplitLeft / SplitRight styles
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    font_path = ensure_bundled_condensed_font()
    fdir_esc = str(font_path.parent).replace("\\", "/").replace(":", "\\:")
    for idx_w, wide_txt in enumerate(("MMMMM MMMM", "1848 CAVENDISH VT")):
        ass_w = tmp_path / f"white_head_{idx_w}.ass"
        png_w = tmp_path / f"white_head_{idx_w}.png"
        generate_diorama_ass_subtitles(
            ass_w,
            events=[(0.0, 2.0, ["Test", "pure", "white."])],
            sentence_spans=[{"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.0, "act_boundary_after": False}],
            visual_plan={
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "lowpoly_pastel_v7",
                "chapter_headlines": [{"sentence_index": 1, "text": wide_txt}],
            },
            edl={"schema": 7, "fps": 24, "speech_end_sec": 2.0, "total_duration_sec": 3.0, "total_frames": 72, "cuts": []},
        )
        ass_content = ass_w.read_text(encoding="utf-8")
        assert "Style: SplitLeft,AAB Condensed Black,84," in ass_content
        assert "Style: SplitRight,AAB Condensed Black,84," in ass_content
        ass_esc = str(ass_w).replace("\\", "/").replace(":", "\\:")
        subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=white:s=1080x1920:d=0.5:r=24",
                "-vf", f"subtitles='{ass_esc}':fontsdir='{fdir_esc}'",
                "-frames:v", "1", str(png_w),
            ],
            check=True,
        )
        frm_w = cv2.imread(str(png_w))
        assert frm_w is not None
        w_px, lm_px, rm_px = measure_chapter_headline_bbox(frm_w)
        assert 500 <= w_px <= cfg.DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX, (
            f"Wide headline '{wide_txt}' on pure white gave width={w_px}px"
        )
        assert lm_px >= 75 and rm_px >= 75, f"Wide headline '{wide_txt}' margins too narrow: L={lm_px}, R={rm_px}"

    # Pure white frame with NO ChapterHeadline must return w_px == 0 (never falsely match white background)
    blank_white = np.full((1920, 1080, 3), 255, dtype=np.uint8)
    assert measure_chapter_headline_bbox(blank_white)[0] == 0

    # 4. Transient top-border 3rd-arm intrusion on lowpoly_pov_hands vs stationary vertical prop
    def _pov_base() -> np.ndarray:
        f = np.full((640, 360, 3), (185, 205, 220), dtype=np.uint8)
        f[0:150, :] = (230, 215, 195)          # bright pastel sky at top
        f[480:640, 50:310] = (95, 130, 175)    # active POV sleeves/hands at bottom
        return f

    intrude_seq = [_pov_base() for _ in range(5)]
    intrude_seq[2][0:140, 180:330] = (45, 45, 50)  # transient dark 3rd sleeve dropping from top border at mid-clip
    assert detect_transient_top_intrusion_pov(intrude_seq, "lowpoly_pov_hands") is True

    stationary_rod_seq = [_pov_base() for _ in range(5)]
    for sf in stationary_rod_seq:
        sf[0:150, 155:215] = (40, 42, 45)      # stationary vertical iron rod present from start to end
    assert detect_transient_top_intrusion_pov(stationary_rod_seq, "lowpoly_pov_hands") is False

    # 5. Act 2 Sentence 10 ("iron shot beneath his left cheek!") included in cold_open_impact_locks
    sc_gold = json.loads((GOLDEN_V7_DIR / "script.json").read_text(encoding="utf-8"))
    vp_gold = json.loads((GOLDEN_V7_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    clips_gold = build_flow_prompts(vp_gold, sc_gold["sentences"])
    contract = compile_episode_qa_contract(vp_gold, sc_gold["sentences"], clips_gold, script_doc=sc_gold)
    impact_clip_nums = {int(x["clip_number"]) for x in contract["cold_open_impact_locks"]}
    assert {2, 14, 15}.issubset(impact_clip_nums), f"Expected clips 2, 14, 15 in impact locks, got {impact_clip_nums}"


def test_v7_programmatic_anatomy_label_badges_and_qa_geometry(tmp_path: Path) -> None:
    import cv2

    from pipeline.diorama_assembler import generate_diorama_ass_subtitles
    from pipeline.dynamic_episode_qa import _non_subtitle_scene_rois, measure_chapter_headline_bbox
    from pipeline.flow_diorama_sharded_worker import _max_horizontal_plaque_glyph_run

    # 1. SSOT parity for DIORAMA_V7_ANATOMY_LABEL_* constants
    constants_doc = (cfg.WORKSPACE_ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    for cname in (
        "DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE",
        "DIORAMA_V7_ANATOMY_LABEL_OUTLINE_WIDTH",
        "DIORAMA_V7_ANATOMY_LABEL_SCALE_X",
        "DIORAMA_V7_ANATOMY_LABEL_MARGIN_V",
    ):
        assert cname in constants_doc, f"{cname} missing from production_constants.md"

    # 2. Explicit badge formatting, auto-derivation from anatomy_map, ChapterHeadline collision suppression, and False suppression
    ass_a = tmp_path / "anat_check.ass"
    generate_diorama_ass_subtitles(
        ass_a,
        events=[
            (0.0, 2.0, ["Surgery", "severed"]),
            (2.0, 5.0, ["both", "curved", "hippocampi."]),
            (5.0, 8.0, ["Basal", "ganglia", "stayed."]),
            (8.0, 10.5, ["Hidden", "brain", "cut."]),
        ],
        sentence_spans=[
            {"sentence_index": 1, "start_sec": 0.0, "end_sec": 2.0, "act_boundary_after": False},
            {"sentence_index": 2, "start_sec": 2.0, "end_sec": 5.0, "act_boundary_after": False},
            {"sentence_index": 3, "start_sec": 5.0, "end_sec": 8.0, "act_boundary_after": False},
            {"sentence_index": 4, "start_sec": 8.0, "end_sec": 10.5, "act_boundary_after": False},
        ],
        visual_plan={
            "schema": 7,
            "profile": "neuro_diorama",
            "style_profile": "lowpoly_pastel_v7",
            "chapter_headlines": [{"sentence_index": 1, "text": "1953 SURGERY"}],
            "clips": [
                {"grammar": "lowpoly_matte_brain", "brain_scene": "sagittal model showing hippocampus"},
                {
                    "grammar": "lowpoly_matte_brain",
                    "brain_region": "hippocampus",
                    "anatomy_label": "HIPPOCAMPUS\nMEMORY GATEWAY",
                },
                {"grammar": "lowpoly_matte_brain", "brain_scene": "deep subcortical basal ganglia and striatum"},
                {"grammar": "lowpoly_matte_brain", "brain_scene": "cerebellum at base of skull", "anatomy_label": False},
            ],
        },
        edl={
            "schema": 7,
            "fps": 24,
            "speech_end_sec": 10.5,
            "total_duration_sec": 12.7,
            "total_frames": 305,
            "cuts": [
                {"cut_index": 1, "clip_index": 1, "mode": "single", "grammar": "lowpoly_matte_brain", "out_start_sec": 0.0, "out_end_sec": 2.0},
                {"cut_index": 2, "clip_index": 2, "mode": "single", "grammar": "lowpoly_matte_brain", "out_start_sec": 2.0, "out_end_sec": 5.0},
                {"cut_index": 3, "clip_index": 3, "mode": "single", "grammar": "lowpoly_matte_brain", "out_start_sec": 5.0, "out_end_sec": 8.0},
                {"cut_index": 4, "clip_index": 4, "mode": "single", "grammar": "lowpoly_matte_brain", "out_start_sec": 8.0, "out_end_sec": 10.5, "anatomy_label": False},
            ],
        },
    )
    ass_txt = ass_a.read_text(encoding="utf-8")
    assert f"Style: AnatomyLabel,{cfg.DIORAMA_V7_SUBTITLE_FONT_NAME},{cfg.DIORAMA_V7_ANATOMY_LABEL_FONT_SIZE}," in ass_txt
    anat_lines = [ln for ln in ass_txt.splitlines() if ln.startswith("Dialogue:") and ",AnatomyLabel," in ln]
    # Cut 1 overlaps ChapterHeadline (0.0..2.0s) -> suppressed; Cut 4 has anatomy_label=False -> suppressed; Cuts 2 & 3 emitted!
    assert len(anat_lines) == 2, f"Expected exactly 2 non-colliding AnatomyLabel events, got: {anat_lines}"
    assert "HIPPOCAMPUS\\NMEMORY GATEWAY" in anat_lines[0]
    assert "BASAL GANGLIA\\NHABIT ENGINE" in anat_lines[1]

    # 3. FFmpeg render at t=3.5s (Cut 2) verifies BOTH lines render, safe horizontal margins, Y < 23% (441px), and zero DQ9 plaque leak
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    font_path = ensure_bundled_condensed_font()
    fdir_esc = str(font_path.parent).replace("\\", "/").replace(":", "\\:")
    ass_esc = str(ass_a).replace("\\", "/").replace(":", "\\:")
    png_anat = tmp_path / "anat_frame.png"
    subprocess.run(
        [
            ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=#dcd5c7:s=1080x1920:d=5.0:r=24",
            "-ss", "3.5",
            "-vf", f"subtitles='{ass_esc}':fontsdir='{fdir_esc}'",
            "-frames:v", "1", str(png_anat),
        ],
        check=True,
    )
    frm_a = cv2.imread(str(png_anat))
    assert frm_a is not None
    aw_px, alm_px, arm_px = measure_chapter_headline_bbox(frm_a, min_glyph_h_px=24)
    assert 300 <= aw_px <= cfg.DIORAMA_V7_CHAPTER_HEADLINE_MAX_WIDTH_PX
    assert alm_px >= 90 and arm_px >= 90
    # Verify BOTH lines rendered (vertical span >= 115px) AND badge stays strictly above Y=420px (< 23% clean-scene ROI)
    top_white = (frm_a[0:550, :, 0] > 235) & (frm_a[0:550, :, 1] > 235) & (frm_a[0:550, :, 2] > 235)
    ys_badge, _ = np.where(top_white)
    badge_span_h = int(ys_badge.max() - ys_badge.min() + 1)
    assert badge_span_h >= 115, f"Expected 2-line AnatomyLabel vertical span >= 115px, got {badge_span_h}px"
    assert int(ys_badge.max()) < 420, f"AnatomyLabel intruded below Y=420px: max_y={ys_badge.max()}"
    clean_rois = _non_subtitle_scene_rois(frm_a, has_top_overlay=True, is_outro=False)
    assert max((_max_horizontal_plaque_glyph_run(r) for r in clean_rois), default=0) == 0


def test_v7_lateral_brain_leads_and_executable_qa_suite_diorama(tmp_path: Path, monkeypatch) -> None:
    from pipeline import qa_gates as qg

    sag_prompt = MatteArchitecturalBrainRule.compose(
        "curved terracotta-coral inner hippocampal arch dims in the lower-inner temporal core",
        brain_mode="matte_pastel_sagittal_cutaway",
    )
    cort_prompt = MatteArchitecturalBrainRule.compose(
        "solid warm-amber surface polygons brighten across the front-left prefrontal lobe",
        brain_mode="matte_pastel_cortical_model",
    )
    assert "strict flat lateral side-profile view of a single half-brain hemisphere" in sag_prompt
    assert "three-quarter lateral side view of a whole" in cort_prompt

    # Hermetic Schema v7 project for run_intent_content_qa & ExecutableQASuite.run_post_assembly_gates
    fake_projects = tmp_path / "projects"
    p_dir = fake_projects / "diorama_v7_qa_smoke"
    for s_sub in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly", "06_publish"):
        (p_dir / s_sub).mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(qg, "PROJECTS_DIR", fake_projects)

    sc_gold = json.loads((GOLDEN_V7_DIR / "script.json").read_text(encoding="utf-8"))
    vp_gold = json.loads((GOLDEN_V7_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    clips_gold = build_flow_prompts(vp_gold, sc_gold["sentences"])
    (p_dir / "00_project_manifest.json").write_text(
        json.dumps({"project_id": p_dir.name, "profile": "neuro_diorama", "schema_version": 7}),
        encoding="utf-8",
    )
    (p_dir / "02_script" / "script.json").write_text(json.dumps(sc_gold), encoding="utf-8")
    (p_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(vp_gold), encoding="utf-8")
    write_flow_prompts_json(p_dir, clips_gold)
    write_episode_qa_contract(p_dir, vp_gold, sc_gold["sentences"], clips_gold, script_doc=sc_gold)

    # Distinct >80KB thumbnails + R36 metadata + compliant ASS subtitles + quiet -6dBFS MP4
    rng = np.random.default_rng(99)
    for idx_t, t_name in enumerate(("thumbnail_var_A.png", "thumbnail_var_B.png", "thumbnail_var_C.png")):
        img = rng.integers(30 * idx_t, 80 + 50 * idx_t, size=(960, 540, 3), dtype=np.uint8)
        cv2.imwrite(str(p_dir / "06_publish" / t_name), img, [cv2.IMWRITE_PNG_COMPRESSION, 0])
    (p_dir / "06_publish" / "metadata.json").write_text(
        json.dumps(
            {
                "project_id": p_dir.name,
                "profile": "neuro_diorama",
                "video_language": "en-US",
                "title_description_language": "en-US",
                "channel_residence_country": "KR",
            }
        ),
        encoding="utf-8",
    )
    ass_lines = [
        "[V4+ Styles]",
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding",
        "Style: Default,AAB Condensed Black,78,&H00FFFFFF,&H00FFFFFF,&H00000000,&H00000000,-1,0,0,0,100,100,0,0,1,7,0,2,70,70,672,1",
        "[Events]",
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text",
    ] + [
        f"Dialogue: 0,0:00:{i:02d}.00,0:00:{i:02d}.90,Default,,0,0,0,,Line {i} steady test"
        for i in range(12)
    ]
    (p_dir / "04_audio" / "subtitles.ass").write_text("\n".join(ass_lines) + "\n", encoding="utf-8")

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    subprocess.run(
        [
            ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
            "-f", "lavfi", "-i", "color=c=#c8d4e0:s=360x640:r=24:d=1.0",
            "-f", "lavfi", "-i", "sine=frequency=220:duration=1.0:sample_rate=48000",
            "-af", "volume=0.25",
            "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "128k",
            str(final_mp4),
        ],
        check=True,
    )
    mp4_sha = hashlib.sha256(final_mp4.read_bytes()).hexdigest()
    (p_dir / "05_assembly" / "dynamic_episode_qa_report.json").write_text(
        json.dumps({"passed": True, "final_mp4_sha256": mp4_sha}),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / cfg.POSTHOC_SEMANTIC_QA_REPORT_FILENAME).write_text(
        json.dumps({"passed": True, "final_mp4_sha256": mp4_sha, "flagged_cut_indices": []}),
        encoding="utf-8",
    )

    rep_ok = qg.run_intent_content_qa(project_id=p_dir.name)
    assert rep_ok["passed"] is True, f"Expected Stage 4 pass on Schema v7 project, got: {rep_ok}"

    # Corrupting posthoc SHA-256 must block post-assembly gates
    (p_dir / "05_assembly" / cfg.POSTHOC_SEMANTIC_QA_REPORT_FILENAME).write_text(
        json.dumps({"passed": True, "final_mp4_sha256": "0" * 64, "flagged_cut_indices": []}),
        encoding="utf-8",
    )
    rep_stale = qg.ExecutableQASuite.run_post_assembly_gates(p_dir)
    assert rep_stale["passed"] is False
    assert "stale_posthoc_semantic_qa_report_mp4_sha_mismatch" in rep_stale["issues"]


def test_v7_brain_reference_neutralizer_birch_sanitization_and_chroma_window(tmp_path: Path) -> None:
    import pytest
    from pipeline.diorama_assembler import _select_v7_source_window
    from pipeline.flow_diorama_sharded_worker import (
        _clip_needs_neutral_brain_ref,
        _ref_stage_key,
        neutralize_v7_brain_reference_tint,
    )

    # 1. MatteArchitecturalBrainRule must eliminate 'birch' tree-species ambiguity and anchor sagittal interior face
    sag_out = MatteArchitecturalBrainRule.compose(
        "on the light-birch table, inner hippocampal arch facets brighten in calm sky-blue",
        brain_mode="matte_pastel_sagittal_cutaway",
    )
    cort_out = MatteArchitecturalBrainRule.compose(
        "on the pale-birch stand, tucked lower-right cerebellum facets glow in warm amber-gold",
        brain_mode="matte_pastel_cortical_model",
    )
    assert "birch" not in sag_out.lower()
    assert "birch" not in cort_out.lower()
    assert "pale-wood" in sag_out.lower() and "pale-wood" in cort_out.lower()
    assert "flat cut-open medial interior face" in sag_out

    # 2. Brain reference neutralizer removes pre-baked Gage coral & slate-blue patches while keeping prefrontal separate
    ref_dir = cfg.WORKSPACE_ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "lowpoly_v7_refs"
    cort_raw = cv2.imread(str(ref_dir / "v7_ref_02_cortical_brain.png"))
    sag_raw = cv2.imread(str(ref_dir / "v7_ref_03_sagittal_brain.png"))
    assert cort_raw is not None and sag_raw is not None

    cort_clean = neutralize_v7_brain_reference_tint(cort_raw)
    sag_clean = neutralize_v7_brain_reference_tint(sag_raw)
    h2, w2 = cort_clean.shape[:2]
    lab_cort_raw = cv2.cvtColor(cort_raw[int(h2 * 0.38) : int(h2 * 0.51), int(w2 * 0.16) : int(w2 * 0.38)], cv2.COLOR_BGR2LAB).astype(np.float32)
    lab_cort = cv2.cvtColor(cort_clean[int(h2 * 0.38) : int(h2 * 0.51), int(w2 * 0.16) : int(w2 * 0.38)], cv2.COLOR_BGR2LAB).astype(np.float32)
    raw_pink_exc = (lab_cort_raw[:, :, 1] - 128.0) - 0.23 * np.maximum(0.0, lab_cort_raw[:, :, 2] - 128.0)
    clean_pink_exc = (lab_cort[:, :, 1] - 128.0) - 0.23 * np.maximum(0.0, lab_cort[:, :, 2] - 128.0)
    assert float(np.percentile(raw_pink_exc, 98)) >= 14.0
    assert float(np.percentile(clean_pink_exc, 99)) <= 5.5, "Prefrontal coral tint must be neutralized to warm-ivory"

    h3, w3 = sag_clean.shape[:2]
    lab_sag_raw = cv2.cvtColor(sag_raw[int(h3 * 0.32) : int(h3 * 0.53), int(w3 * 0.26) : int(w3 * 0.62)], cv2.COLOR_BGR2LAB)
    lab_sag = cv2.cvtColor(sag_clean[int(h3 * 0.32) : int(h3 * 0.53), int(w3 * 0.26) : int(w3 * 0.62)], cv2.COLOR_BGR2LAB)
    assert float(np.percentile(lab_sag_raw[:, :, 2][lab_sag_raw[:, :, 0] < 215], 5)) <= 125.0
    assert float(np.percentile(lab_sag[:, :, 2][lab_sag[:, :, 0] < 215], 5)) >= 134.0, "Medial slate-blue tint must be neutralized to warm-ivory"

    assert (ref_dir / "v7_ref_02_cortical_brain_neutral.png").exists()
    assert (ref_dir / "v7_ref_03_sagittal_brain_neutral.png").exists()

    pfc_spec = {
        "grammar": "lowpoly_matte_brain",
        "brain_region": "prefrontal cortex",
        "anatomy_label": "PREFRONTAL CORTEX",
        "reference_image": "BCI_Shorts_Channel/reference_style_anchors/lowpoly_v7_refs/v7_ref_02_cortical_brain.png",
    }
    hip_spec = {
        "grammar": "lowpoly_matte_brain",
        "brain_region": "hippocampus",
        "anatomy_label": "HIPPOCAMPUS",
        "reference_image": "BCI_Shorts_Channel/reference_style_anchors/lowpoly_v7_refs/v7_ref_03_sagittal_brain.png",
    }
    assert _clip_needs_neutral_brain_ref(pfc_spec) is False
    assert _clip_needs_neutral_brain_ref(hip_spec) is True
    assert _ref_stage_key(pfc_spec) != _ref_stage_key(hip_spec)

    # 3. _select_v7_source_window honors source_start_sec alias AND rescues unlit brain pre-roll via LAB chroma salience
    brain_mp4 = tmp_path / "brain_delayed_glow.mp4"
    writer = cv2.VideoWriter(str(brain_mp4), cv2.VideoWriter_fourcc(*"mp4v"), 24.0, (180, 320))
    for fi in range(144):  # 6.0s @ 24fps
        frm = np.full((320, 180, 3), (205, 224, 236), dtype=np.uint8)  # warm-ivory BGR
        cv2.ellipse(frm, (90, 150), (58, 46), 0, 0, 360, (188, 214, 232), -1)
        # Subtle jitter everywhere so grayscale motion alone does not strongly separate pre-roll vs active glow
        sx = (fi % 4) - 1
        cv2.circle(frm, (90 + sx, 150), 8, (176, 202, 222), -1)
        if fi >= 54:  # >= 2.25s: localized terracotta-coral inner hippocampal arch illuminates
            cv2.ellipse(frm, (92, 162), (24, 14), 0, 0, 180, (108, 128, 226), -1)
        writer.write(frm)
    writer.release()

    alias_s, alias_span = _select_v7_source_window(
        brain_mp4,
        clip_dur=6.0,
        out_dur=2.0,
        spec={"grammar": "lowpoly_matte_brain", "source_start_sec": 2.5},
    )
    assert alias_s == pytest.approx(2.5, abs=0.05)
    assert alias_span == pytest.approx(2.0, abs=0.05)

    auto_s, auto_span = _select_v7_source_window(
        brain_mp4,
        clip_dur=6.0,
        out_dur=2.0,
        spec={"grammar": "lowpoly_matte_brain"},
    )
    assert auto_s >= 2.0, f"Expected brain chroma salience rescue past [0..2.25s] unlit ivory pre-roll, got {auto_s}"
    assert auto_span == pytest.approx(2.0, abs=0.05)


def test_patient_hm_hippocampus_v7_blueprint_and_anatomical_localization() -> None:
    from pipeline.anatomy_map import resolve_region
    from pipeline.flow_diorama_sharded_worker import _clip_needs_neutral_brain_ref

    hm_dir = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "patient_hm_hippocampus" / "diorama_v7_lowpoly"
    script_doc = json.loads((hm_dir / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((hm_dir / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]

    assert cfg.is_diorama_v7_plan(visual_plan) is True
    assert len(visual_plan["clips"]) == 63

    clips = build_flow_prompts(visual_plan, sentences)
    assert validate_diorama_v7_prompts(clips) == []
    # Published pre-R57-H2 blueprint: grandfathered (opt-out) for every other gate; the new cold-open gate must flag it.
    legacy_plan = {**visual_plan, "require_cold_open_v7": False}
    assert validate_production_diorama_v6(legacy_plan, sentences, clips, script_doc=script_doc) == []
    strict_issues = validate_production_diorama_v6(visual_plan, sentences, clips, script_doc=script_doc)
    assert strict_issues and all(i.startswith("[cold_open_v7]") for i in strict_issues)
    assert rd.check_narration_facts("patient_hm_hippocampus", sentences) == []

    split_clip_indices = {
        int(sc["left_clip_index"]) for sc in visual_plan.get("split_comparisons", [])
    } | {
        int(sc["right_clip_index"]) for sc in visual_plan.get("split_comparisons", [])
    }

    brain_specs = [
        (idx + 1, spec, clips[idx])
        for idx, spec in enumerate(visual_plan["clips"])
        if spec.get("grammar") == "lowpoly_matte_brain"
    ]
    assert len(brain_specs) == 11
    covered_regions: set[str] = set()
    for clip_num, spec, rendered in brain_specs:
        canon = resolve_region(str(spec.get("brain_region") or ""))
        assert canon is not None, f"Clip {clip_num} missing canonical brain_region: {spec.get('brain_region')}"
        covered_regions.add(canon)
        assert "birch" not in str(rendered.get("scene") or "").lower()
        ref_img = str(spec.get("reference_image") or "")
        assert ref_img.endswith(".png") and (ROOT / ref_img).exists()
        if canon != "prefrontal cortex":
            assert "_neutral.png" in ref_img
            assert _clip_needs_neutral_brain_ref(spec) is True
        if clip_num not in split_clip_indices:
            label = str(spec.get("anatomy_label") or "").strip()
            assert "\n" in label and len(label) >= 10, f"Single-pane brain clip {clip_num} missing 2-line anatomy_label"

    assert {"temporal lobe", "prefrontal cortex", "hippocampus", "basal ganglia", "cerebellum"}.issubset(covered_regions)


def _mp_manifest_record_worker(args: tuple[str, int]) -> int:
    from pipeline.storage import ProjectStorage

    p_dir = Path(args[0])
    worker_id = int(args[1])
    ok_count = 0
    for idx in range(4):
        rel = f"concurrent_worker_{worker_id}_{idx}.json"
        fp = p_dir / "05_assembly" / rel
        if ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", rel, fp):
            ok_count += 1
    return ok_count


def test_project_storage_standalone_manifest_sync_preserves_verify_integrity(tmp_path: Path) -> None:
    import multiprocessing as mp
    from pipeline.storage import ProjectStorage

    projects_root = tmp_path / "projects"
    p_dir = projects_root / "diorama_manifest_sync_case"
    p_dir.mkdir(parents=True)

    # Edge case 1: Missing manifest -> False
    assert ProjectStorage.sync_existing_manifest_from_disk(p_dir) is False
    assert ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "x.json", p_dir / "missing.json") is False
    assert ProjectStorage.prune_manifest_stage_prefix(p_dir, "05_assembly", "posthoc_viewer_strips/sheet_", set()) == 0

    # Edge case 2: Stub manifest without 'stages' -> untouched, returns False
    (p_dir / "00_project_manifest.json").write_text(json.dumps({"project_id": p_dir.name, "status": "DRAFT"}), encoding="utf-8")
    assert ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED") is False
    assert json.loads((p_dir / "00_project_manifest.json").read_text(encoding="utf-8")) == {"project_id": p_dir.name, "status": "DRAFT"}

    # Edge case 3: Tracked ProjectStorage manifest -> remediated clip + new QA report syncs cleanly, while post-sync corruption still fails verify
    (p_dir / "00_project_manifest.json").unlink()
    storage = ProjectStorage(p_dir.name, title="Manifest Sync Test", pillar="brain_history", projects_dir=projects_root)
    clip_p = storage.get_stage_dir("03_visuals") / "flow_native_clips" / "clip_30.mp4"
    clip_p.parent.mkdir(parents=True, exist_ok=True)
    clip_p.write_bytes(b"old-clip-bytes")
    storage.record_artifact("03_visuals", "flow_native_clips/clip_30.mp4", clip_p)

    # Remediate clip on disk (size & sha change) -> before sync verify fails, after sync verify passes
    clip_p.write_bytes(b"remediated-neutral-brain-clip-bytes")
    assert storage.verify_integrity()["all_intact"] is False

    assert ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED") is True
    qa_rep = storage.get_stage_dir("05_assembly") / "posthoc_semantic_qa_report.json"
    qa_rep.write_text('{"passed": true}\n', encoding="utf-8")
    assert ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "posthoc_semantic_qa_report.json", qa_rep) is True

    intact_rep = storage.verify_integrity()
    assert intact_rep["all_intact"] is True
    assert intact_rep["verified_artifacts"] == 2

    # Edge case 4: Stale viewer sheet pruning keeps verify_integrity intact when viewer sheet count shrinks
    strips_dir = storage.get_stage_dir("05_assembly") / "posthoc_viewer_strips"
    strips_dir.mkdir(parents=True, exist_ok=True)
    sh1 = strips_dir / "sheet_01.jpg"
    sh99 = strips_dir / "sheet_99.jpg"
    sh1.write_bytes(b"sheet-01")
    sh99.write_bytes(b"stale-sheet-99")
    ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "posthoc_viewer_strips/sheet_01.jpg", sh1)
    ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "posthoc_viewer_strips/sheet_99.jpg", sh99)
    sh99.unlink()
    assert storage.verify_integrity()["all_intact"] is False
    pruned = ProjectStorage.prune_manifest_stage_prefix(
        p_dir,
        "05_assembly",
        "posthoc_viewer_strips/sheet_",
        {"posthoc_viewer_strips/sheet_01.jpg"},
    )
    assert pruned == 1
    assert storage.verify_integrity()["all_intact"] is True

    # Edge case 5: Multi-process concurrent manifest updates must suffer zero lost updates (24/24 preserved)
    asm_dir = storage.get_stage_dir("05_assembly")
    for wid in range(6):
        for idx in range(4):
            (asm_dir / f"concurrent_worker_{wid}_{idx}.json").write_text(f'{{"w": {wid}, "i": {idx}}}\n', encoding="utf-8")
    ctx = mp.get_context("fork" if "fork" in mp.get_all_start_methods() else "spawn")
    with ctx.Pool(processes=6) as pool:
        results = pool.map(_mp_manifest_record_worker, [(str(p_dir), wid) for wid in range(6)])
    assert sum(results) == 24
    mp_rep = storage.verify_integrity()
    assert mp_rep["all_intact"] is True
    assert mp_rep["verified_artifacts"] == 3 + 24

    # Post-sync corruption must still be caught by verify_integrity
    qa_rep.write_text('{"passed": false, "corrupted": 1}\n', encoding="utf-8")
    broken_rep = storage.verify_integrity()
    assert broken_rep["all_intact"] is False


def test_v7_peripheral_tint_neutralizer_and_brain_localization_cv_gate() -> None:
    from pipeline.flow_diorama_sharded_worker import (
        _clip_needs_neutral_brain_ref,
        neutralize_v7_brain_reference_tint,
    )
    from pipeline.posthoc_semantic_qa import (
        _concat_clean_roi_360,
        _detect_nonfrontal_brain_localization_defect,
    )

    ref_dir = cfg.WORKSPACE_ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "lowpoly_v7_refs"
    cort_neutral = cv2.imread(str(ref_dir / "v7_ref_02_cortical_brain_neutral.png"))
    cort_raw = cv2.imread(str(ref_dir / "v7_ref_02_cortical_brain.png"))
    sag_raw = cv2.imread(str(ref_dir / "v7_ref_03_sagittal_brain.png"))
    assert cort_neutral is not None and cort_raw is not None and sag_raw is not None

    # 1. Peripheral occipital coral patch (x=0.84, outside legacy x<=0.78 ROI) must be neutralized completely
    occ_tinted = cort_neutral.copy()
    h, w = occ_tinted.shape[:2]
    cv2.circle(occ_tinted, (int(w * 0.84), int(h * 0.44)), int(w * 0.055), (125, 138, 224), -1)
    occ_clean = neutralize_v7_brain_reference_tint(occ_tinted)
    lab_occ = cv2.cvtColor(
        occ_clean[int(h * 0.37) : int(h * 0.51), int(w * 0.77) : int(w * 0.91)],
        cv2.COLOR_BGR2LAB,
    ).astype(np.float32)
    occ_pink = (lab_occ[:, :, 1] - 128.0) - 0.23 * np.maximum(0.0, lab_occ[:, :, 2] - 128.0)
    assert float(np.percentile(occ_pink, 99)) <= 5.5, "Peripheral occipital coral patch must be neutralized"

    # 2. Sagittal neutralizer must NOT tint upper daylight window mullions (y < 0.28)
    sag_clean = neutralize_v7_brain_reference_tint(sag_raw)
    hs, ws = sag_clean.shape[:2]
    upper_diff = float(np.max(np.abs(sag_clean[: int(hs * 0.26), :].astype(np.int16) - sag_raw[: int(hs * 0.26), :].astype(np.int16))))
    assert upper_diff == 0.0, f"Upper architectural daylight zone must remain untouched, got max diff {upper_diff}"

    # 3. Sagittal reference paired with prefrontal cortex must still neutralize Gage's anterior cingulate slate-blue patch
    pfc_sag_spec = {
        "grammar": "lowpoly_matte_brain",
        "brain_region": "prefrontal cortex",
        "anatomy_label": "PREFRONTAL CORTEX",
        "reference_image": "BCI_Shorts_Channel/reference_style_anchors/lowpoly_v7_refs/v7_ref_03_sagittal_brain.png",
    }
    assert _clip_needs_neutral_brain_ref(pfc_sag_spec) is True

    # 4. R64 brain localization CV gate passes true prefrontal / clean posterior cuts and catches misplaced frontal bleed
    c_pfc = _concat_clean_roi_360(cort_raw, has_top_overlay=True, is_outro=False)
    c_acc = _concat_clean_roi_360(sag_raw, has_top_overlay=True, is_outro=False)
    assert _detect_nonfrontal_brain_localization_defect(c_pfc, "prefrontal cortex", "single") is None
    assert _detect_nonfrontal_brain_localization_defect(c_pfc, "cerebellum", "split_hstack") is None
    err_cer = _detect_nonfrontal_brain_localization_defect(c_pfc, "cerebellum", "single")
    err_hip = _detect_nonfrontal_brain_localization_defect(c_pfc, "hippocampus", "single")
    err_bg = _detect_nonfrontal_brain_localization_defect(c_acc, "basal ganglia", "single")
    assert err_cer is not None and "unintended_prefrontal_coral_bleed" in err_cer
    assert err_hip is not None and "unintended_prefrontal_coral_bleed" in err_hip
    assert err_bg is not None and "unintended_anterior_cingulate_slate_bleed" in err_bg

    # Anterior sky-blue highlight on a posterior 'cerebellum' cut must fail, whereas posterior sky-blue passes
    post_ok = _concat_clean_roi_360(cort_neutral, has_top_overlay=True, is_outro=False)
    ant_bad = post_ok.copy()
    ch, cw = post_ok.shape[:2]
    cv2.circle(post_ok, (int(cw * 0.72), int(ch * 0.56)), 18, (230, 195, 120), -1)
    cv2.circle(ant_bad, (int(cw * 0.20), int(ch * 0.30)), 18, (230, 195, 120), -1)
    assert _detect_nonfrontal_brain_localization_defect(post_ok, "cerebellum", "single") is None
    err_ant_sky = _detect_nonfrontal_brain_localization_defect(ant_bad, "cerebellum", "single")
    assert err_ant_sky is not None and "misplaced_anterior_highlight_for_posterior_region" in err_ant_sky


def test_v7_andrew_multilingual_silk_clean_voice_ssot_and_retention_rules(tmp_path: Path) -> None:
    from pipeline.diorama_assembler import generate_diorama_audio_master
    from pipeline.plain_language import analyze_script, find_duplicate_analogy_idioms, to_expressive_tts_text
    from pipeline.voice_fallback import (
        STORYTELLER_VOCAL_FILTER,
        _decode_mp3_storyteller_pcm,
        synthesize_continuous_diorama_track,
    )

    assert cfg.DIORAMA_TTS_VOICE == "en-US-AndrewMultilingualNeural"
    assert cfg.DIORAMA_V7_TTS_RATE == "+8%"
    assert cfg.DIORAMA_V7_TTS_PITCH == "+14Hz"
    assert cfg.DIORAMA_V7_TTS_VOLUME == "-10%"
    assert cfg.DIORAMA_V7_TTS_SPEED == 1.08
    assert cfg.DIORAMA_V7_VIDEO_FPS == 24
    assert cfg.DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN == 0.80
    assert 0.24 <= cfg.DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC <= 0.34
    assert 0.12 <= cfg.DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC <= 0.18
    assert 0.12 <= cfg.DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC <= 0.20
    assert 0.28 <= cfg.DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC <= 0.40

    ssot_docs = (
        ROOT / "pipeline" / "config.py",
        ROOT / "pipeline" / "diorama_assembler.py",
        ROOT / "pipeline" / "diorama_batch_orchestrator.py",
        ROOT / "pipeline" / "voice_fallback.py",
        ROOT / ".agents" / "rules" / "production_constants.md",
        ROOT / ".agents" / "rules" / "neuro_diorama_rules.md",
        ROOT / ".agents" / "rules" / "audio_assembly_rules.md",
        ROOT / ".agents" / "AGENTS.md",
        ROOT / ".agents" / "profiles" / "yt-editor" / "SOUL.md",
        ROOT / ".agents" / "skills" / "bci-video-assembly" / "SKILL.md",
        ROOT / ".agents" / "skills" / "bci-video-pipeline" / "SKILL.md",
    )
    for doc_path in ssot_docs:
        txt = doc_path.read_text(encoding="utf-8")
        assert "en-US-RogerNeural" not in txt, f"Stale RogerNeural reference in {doc_path}"
        assert "en-US-BrianMultilingualNeural" not in txt, f"Stale BrianMultilingualNeural reference in {doc_path}"
        assert "en-US-AndrewMultilingualNeural" in txt, f"Missing AndrewMultilingualNeural in {doc_path}"

    # 1. Silk Clean vocal filter upsamples via 48kHz soxr, cuts 6.2kHz breath/sibilance linearly, and avoids nonlinear deesser
    import inspect

    assert "3400" not in STORYTELLER_VOCAL_FILTER
    assert "deesser" not in STORYTELLER_VOCAL_FILTER
    # Q-2 (2026-10-31): light -1.5 dB 6.2kHz cut, no 10kHz lowpass (HF was attenuated three times -> muffled voice)
    assert "equalizer=f=6200:t=q:w=0.9:g=-1.5" in STORYTELLER_VOCAL_FILTER
    assert "lowpass" not in STORYTELLER_VOCAL_FILTER
    assert "ratio=1.25" in STORYTELLER_VOCAL_FILTER
    assert "resampler=soxr" in inspect.getsource(_decode_mp3_storyteller_pcm)

    # 1b. R57-C proper-noun phonetics & glossed neuroscience jargon
    expr = to_expressive_tts_text("Patient H.M. — Henry Molaison — met Doctor Scoville and Broca's patient Leborgne.")
    assert "Patient H M" in expr
    assert "Mo-lay-zon" in expr
    assert "Sko-vil" in expr
    assert "Bro-kuz" in expr
    assert "Luh-born" in expr
    glossed_rep = analyze_script(
        [
            "Memory consolidation locks today's moments into permanent long-term storage.",
            "Each synapse acts as a tiny chemical bridge between two brain cells.",
        ]
    )
    assert set(glossed_rep["glossed_jargon_terms"]) >= {"consolidation", "synapse"}
    assert glossed_rep["unglossed_jargon_terms"] == []
    assert find_duplicate_analogy_idioms(["Faster than a blink, it fired.", "Faster than a blink, he jumped."]) != []

    # 2. Peak-safe MP3 decoding preserves high crest-factor transients without hard clipping
    sr = 48000
    t = np.arange(sr, dtype=np.float32) / float(sr)
    synth_speech = (0.08 * np.sin(2.0 * np.pi * 145.0 * t)).astype(np.float32)
    synth_speech[sr // 3 : sr // 3 + 240] = 0.72 * np.sin(2.0 * np.pi * 290.0 * t[:240])
    wav_in = tmp_path / "transient.wav"
    mp3_in = tmp_path / "transient.mp3"
    with wave.open(str(wav_in), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes((np.clip(synth_speech, -0.99, 0.99) * 32767.0).astype(np.int16).tobytes())
    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(wav_in), "-b:a", "128k", str(mp3_in)],
        check=True,
        capture_output=True,
        timeout=30,
        stdin=subprocess.DEVNULL,
    )
    decoded = _decode_mp3_storyteller_pcm(mp3_in.read_bytes(), sr)
    assert 0.20 < float(np.max(np.abs(decoded))) <= 0.935
    assert int(np.sum(np.abs(decoded) >= 0.945)) == 0

    # 3. Natural conversational breath (< 0.28s) stays untouched; long pause (>= 0.28s) keeps ~0.140s with zero room-tone dip
    t_b = np.arange(int(0.50 * sr), dtype=np.float32) / float(sr)
    voiced = (0.30 * np.sin(2.0 * np.pi * 155.0 * t_b)).astype(np.float32)
    short_breath = np.full(int(0.20 * sr), 0.002, dtype=np.float32)
    long_breath = np.full(int(0.60 * sr), 0.002, dtype=np.float32)
    pad_edge = np.zeros(int(0.15 * sr), dtype=np.float32)

    pcm_short = np.concatenate([pad_edge, voiced, short_breath, voiced, pad_edge])
    out_short, _ = _trim_waveform_silences_and_breaths(
        pcm_short,
        sr=sr,
        internal_silence_thresh_sec=cfg.DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
        internal_keep_sec=cfg.DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC,
    )
    # 0.03 lead + 0.50 + 0.20 + 0.50 + 0.05 tail = 1.28s (short 0.20s breath preserved intact)
    assert 1.25 <= len(out_short) / float(sr) <= 1.31

    # Include Whisper word boundaries protruding 20ms into the trimmed silence gap to verify monotonic non-overlap
    pcm_long = np.concatenate([pad_edge, voiced, long_breath, voiced, pad_edge])
    out_long, shifted_w = _trim_waveform_silences_and_breaths(
        pcm_long,
        sr=sr,
        word_list=[(0.15, 0.67, "Alpha"), (1.23, 1.75, "Omega")],
        internal_silence_thresh_sec=cfg.DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
        internal_keep_sec=cfg.DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC,
    )
    # 0.03 lead + 0.50 + 0.140 kept (compensated across 12ms overlap-add) + 0.50 + 0.05 tail ~= 1.220s
    assert 1.20 <= len(out_long) / float(sr) <= 1.24
    # Constant-amplitude overlap-add crossfade keeps room tone ~0.002 across the internal splice (zero dip to 0.0)
    mid_breath_slice = out_long[int(0.55 * sr) : int(0.65 * sr)]
    assert float(np.min(mid_breath_slice)) > 0.0015
    assert shifted_w[0][0] < shifted_w[0][1] <= shifted_w[1][0] < shifted_w[1][1]

    # 4. Boundary/empty waveform inputs never crash
    for edge_arr in (
        np.zeros(0, dtype=np.float32),
        np.zeros(int(0.05 * sr), dtype=np.float32),
        np.zeros(int(0.50 * sr), dtype=np.float32),
    ):
        res_arr, res_w = _trim_waveform_silences_and_breaths(edge_arr, sr=sr, word_list=None)
        assert len(res_arr) == len(edge_arr)
        assert res_w == []

    # 5. Schema v7 boundary pause auto-fit keeps atempo_applied == 1.0 at both 440w and 504w limits
    #    (legacy uniform 1.08x pause-fit contract; pinned since the channel default is now dynamic_rush_v7, whose
    #    gear tempos/gaps are covered by tests/test_prosody_engine.py)
    def _build_acts(n_sents: int) -> list[dict[str, object]]:
        per_act = [n_sents // 6 + (1 if i < (n_sents % 6) else 0) for i in range(6)]
        acts_out = []
        cur = 0
        for a_idx, cnt in enumerate(per_act, 1):
            s_list = []
            for _ in range(cnt):
                cur += 1
                s_list.append(f"Sentence {cur} tests smooth conversational breathing across acts.")
            acts_out.append({"act": a_idx, "sentences": s_list})
        return acts_out

    acts_504 = _build_acts(56)
    sents_504 = [s for a in acts_504 for s in a["sentences"]]  # type: ignore[union-attr]
    n_504 = int(3.068 * sr)
    lines_504 = [(0.20 * np.sin(2.0 * np.pi * 160.0 * (np.arange(n_504, dtype=np.float32) / sr))) for _ in sents_504]
    res_504 = synthesize_continuous_diorama_track(
        project_dir=tmp_path / "fit_504w",
        sentences=sents_504,
        align_whisper=False,
        pre_synthesized_lines=lines_504,
        script_doc={"schema": 7, "style_profile": "lowpoly_pastel_v7", "acts": acts_504},
        prosody_mode="uniform_108x",
    )
    assert res_504["atempo_applied"] == 1.0
    assert cfg.DIORAMA_V7_DURATION_MIN_SEC <= res_504["total_duration_sec"] <= cfg.SHORTS_HARD_CEILING_SEC

    acts_440 = _build_acts(48)
    sents_440 = [s for a in acts_440 for s in a["sentences"]]  # type: ignore[union-attr]
    n_440 = int(2.68 * sr)
    lines_440 = [(0.20 * np.sin(2.0 * np.pi * 160.0 * (np.arange(n_440, dtype=np.float32) / sr))) for _ in sents_440]
    res_440 = synthesize_continuous_diorama_track(
        project_dir=tmp_path / "fit_440w",
        sentences=sents_440,
        align_whisper=False,
        pre_synthesized_lines=lines_440,
        script_doc={"schema": 7, "style_profile": "lowpoly_pastel_v7", "acts": acts_440},
        prosody_mode="uniform_108x",
    )
    assert res_440["atempo_applied"] == 1.0
    assert res_440["pause_sec"] < 0.24
    assert cfg.DIORAMA_V7_DURATION_MIN_SEC <= res_440["total_duration_sec"] <= 143.0

    # 6. Schema v7 2ch audio master uses constant scalar linear gain (zero sliding-window AGC pumping)
    from pipeline.diorama_assembler import _synthesize_stereo_orchestral_bgm

    dur_lin = 16.0
    n_lin = int(dur_lin * sr)
    t_lin = np.arange(n_lin, dtype=np.float32) / float(sr)
    env_lin = np.where(((t_lin // 4.0).astype(int) % 2) == 0, 0.12, 0.26).astype(np.float32)
    voice_lin = (env_lin * np.sin(2.0 * np.pi * 165.0 * t_lin)).astype(np.float32)
    dummy_edl = {
        "schema": 7,
        "style_profile": "lowpoly_pastel_v7",
        "fps": 24,
        "total_duration_sec": dur_lin,
        "speech_end_sec": 14.0,
        "cuts": [{"cut_index": 1, "act": 1, "start_sec": 0.0, "end_sec": dur_lin, "duration_sec": dur_lin}],
    }
    master_wav = generate_diorama_audio_master(
        wav_path=tmp_path / "master_v7.wav",
        voice_pcm=voice_lin,
        sr=sr,
        speech_end_sec=14.0,
        edl=dummy_edl,
    )
    with wave.open(str(master_wav), "rb") as mwf:
        assert mwf.getnchannels() == 2
        assert mwf.getframerate() == sr
        m_st = np.frombuffer(mwf.readframes(mwf.getnframes()), dtype=np.int16).astype(np.float32).reshape(-1, 2) / 32767.0
    assert 0.08 < float(np.max(np.abs(m_st))) <= 0.86
    raw_bgm = _synthesize_stereo_orchestral_bgm(n_lin, sr, 14.0, dummy_edl)
    raw_mono = 0.5 * (2.0 * voice_lin + raw_bgm[:, 0] + raw_bgm[:, 1])
    out_mono = 0.5 * (m_st[:, 0] + m_st[:, 1])
    win_gains_db = []
    for w_start in (1.0, 5.0, 9.0):
        i0, i1 = int(w_start * sr), int((w_start + 2.0) * sr)
        r_in = float(np.sqrt(np.mean(raw_mono[i0:i1] ** 2)))
        r_out = float(np.sqrt(np.mean(out_mono[i0:i1] ** 2)))
        win_gains_db.append(20.0 * np.log10(r_out / r_in))
    assert (max(win_gains_db) - min(win_gains_db)) < 0.08


def test_youtube_natural_script_guardrails_and_r35_editorial_comments() -> None:
    """Verifies R57-C YouTube Natural Script spoken guardrails & R35 conversational comment packages."""
    from pipeline.plain_language import find_ai_cliches_and_seminar_isms
    from pipeline.studio.community import CommunityManager, _parse_citation_author_year_journal

    # 1. AI-essay clichés and academic slide-seminar transitions are flagged, while literal 'unpacks' passes
    bad_ai = find_ai_cliches_and_seminar_isms("Furthermore, let's delve into this pivotal neural tapestry.")
    assert set(bad_ai["ai_cliches"]) >= {"furthermore", "delve into", "pivotal", "tapestry"}
    bad_sem = find_ai_cliches_and_seminar_isms("Moving on to Broca (1861), this paper looks at speech.")
    assert set(bad_sem["seminar_isms"]) >= {"moving on to", "this paper looks at"}
    clean_bag = find_ai_cliches_and_seminar_isms("One hand packs a bag while the other unpacks.")
    assert clean_bag == {"ai_cliches": [], "seminar_isms": []}

    # 2. Single-string 'citation' parsing never drops the author into 'According to (1998)'
    parsed = _parse_citation_author_year_journal(
        {
            "citation": "V. Ramachandran (1998). The perception of phantom limbs. The D. O. Hebb lecture. Brain.",
            "year": 1998,
        }
    )
    assert "Ramachandran" in parsed and "1998" in parsed and "Brain" in parsed

    # 3. Every active Neuro-Diorama project generates a clean, natural, zero-cliché R35 comment with DOI + '?'
    cm = CommunityManager()
    for pid in (
        "gage_diorama_v7_lowpoly",
        "diorama_01_patient_hm_hippocampus",
        "diorama_02_ramachandran_phantom_mirror",
        "diorama_03_alien_hand_syndrome",
        "diorama_04_milgram_obedience_switch",
        "diorama_05_hippocampal_memory_prosthesis",
        "diorama_06_clive_wearing_seven_second_mind",
        "diorama_07_invisible_gorilla_attention",
        "diorama_08_maguire_london_taxi_hippocampus",
        "diorama_09_broca_patient_tan_speech_loss",
        "diorama_10_olds_milner_pleasure_center",
        "diorama_11_blindsight_subcortical_vision",
    ):
        pkg = cm.prepare_comment_content(pid)
        txt = pkg["comment_text"]
        assert "According to (" not in txt, f"Broken citation in {pid}: {txt}"
        assert "https://doi.org/10." in txt, f"Missing DOI link in {pid}: {txt}"
        assert txt.splitlines()[0].strip().endswith("?"), f"Viewer debate question '?' must be on Line 1 above mobile fold in {pid}: {txt}"
        ns = find_ai_cliches_and_seminar_isms(txt)
        assert ns["ai_cliches"] == [] and ns["seminar_isms"] == [], (pid, ns)




