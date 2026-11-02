"""Schema v6 Neuro-Diorama 3-Minute Long-Short tests (R56-R61):
- SSOT constant & rule parity (config.py <-> production_constants.md & neuro_diorama_rules.md)
- R56 Zero-Flesh Ghost-Lab & Pedestal Satin-Frosted Crystal Partial Specimen validator
- R57 6-Act US English script & 100% [Number] -> [Immediate Everyday Analogy] pairing
- R60 2-Clause US English Paradox Title builder/validator
- R61 Golden `phineas_gage_iron_rod/diorama_v6` prompt-gate & dossier fact trace
- R58/R59 End-to-end 3-minute (`<= 179.0s` / `5,370 frames`) Cross-Cut NLE Assembly + MediaIntegrity + VideoAutopsyEngine PASS
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from pathlib import Path

import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline import research_dossier as rd
from pipeline.depiction_rules import (
    ArchitecturalBrainMaquetteRule,
    CrystalSpecimenRule,
    DioramaCutawayRule,
    KineticTracePropRule,
    validate_zero_flesh_and_crystal_specimen,
)
from pipeline.diorama_assembler import assemble_diorama_project
from pipeline.flow_prompt_builder import (
    build_flow_prompts,
    is_diorama_v6_plan,
    is_v5_plan,
    write_flow_prompts_json,
)
from pipeline.media_integrity import MediaIntegrityValidator
from pipeline.plain_language import validate_number_analogy_pairing
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.publish import build_diorama_paradox_title, validate_diorama_paradox_title
from pipeline.video_autopsy import VideoAutopsyEngine

ROOT = Path(cfg.WORKSPACE_ROOT)
GOLDEN_V6_DIR = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "phineas_gage_iron_rod" / "diorama_v6_dynamic"


def test_diorama_v6_constants_and_rules_ssot_parity() -> None:
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    rules_md = (ROOT / ".agents" / "rules" / "neuro_diorama_rules.md").read_text(encoding="utf-8")
    agents_md = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")

    required_names = (
        "DEFAULT_PRODUCTION_PROFILE",
        "PROMPT_SCHEMA_VERSION_V6",
        "SHORTS_HARD_CEILING_SEC",
        "SHORTS_HARD_CEILING_FRAMES",
        "DIORAMA_DURATION_MIN_SEC",
        "DIORAMA_DURATION_TARGET_SEC",
        "DIORAMA_DURATION_MAX_SEC",
        "DIORAMA_CLIP_COUNT_MIN",
        "DIORAMA_CLIP_COUNT_DEFAULT",
        "DIORAMA_CLIP_COUNT_MAX",
        "DIORAMA_TARGET_CUT_MIN",
        "DIORAMA_TARGET_CUT_MAX",
        "DIORAMA_WORD_COUNT_MIN",
        "DIORAMA_WORD_COUNT_MAX",
        "DIORAMA_BANNED_SLOGAN_OPENERS",
        "DIORAMA_MIN_CUT_DURATION_SEC",
        "DIORAMA_VISUAL_PLAYBACK_SPEED",
        "DIORAMA_ENTRY_SPEED_RAMP",
        "DIORAMA_ENTRY_RAMP_START_SPEED",
        "DIORAMA_ENTRY_RAMP_MAIN_SPEED",
        "DIORAMA_TTS_ENGINE",
        "DIORAMA_TTS_VOICE",
        "DIORAMA_TTS_RATE",
        "DIORAMA_TTS_PITCH",
        "DIORAMA_MIN_CONVERSATIONAL_QUESTIONS",
        "DIORAMA_TTS_SPEED",
        "DIORAMA_ACT_BOUNDARY_PAUSE_SEC",
        "DIORAMA_CRYSTAL_SPECIMEN_MAX_RATIO",
        "DIORAMA_BACKDROP_STYLE",
        "DIORAMA_LIGHTING_STYLE",
        "DIORAMA_BRAIN_RENDER_MODES",
        "DIORAMA_SUBTITLE_MARGIN_V",
        "DIORAMA_BGM_BPM",
        "DIORAMA_BGM_DUCK_DB",
        "DIORAMA_TARGET_LUFS",
        "TITLE_MAX_CHARS_DIORAMA",
    )
    for name in required_names:
        assert hasattr(cfg, name), f"Missing {name} in pipeline/config.py"
        assert name in constants_md, f"Missing {name} in .agents/rules/production_constants.md"

    for rule_id in ("R56", "R57", "R58", "R59", "R60", "R61", "R62"):
        assert rule_id in rules_md, f"Missing {rule_id} in neuro_diorama_rules.md"
        assert rule_id in agents_md, f"Missing {rule_id} in AGENTS.md"

    assert cfg.SHORTS_HARD_CEILING_SEC == 179.0
    assert cfg.SHORTS_HARD_CEILING_FRAMES == 5370


def test_zero_flesh_and_crystal_specimen_depiction_rules() -> None:
    clean_cutaway = DioramaCutawayRule.compose(
        "an 1848 granite railroad cut with timber derricks and wooden rail carts",
        "a wooden crane boom swings slowly above split granite blocks",
    )
    assert validate_zero_flesh_and_crystal_specimen(clean_cutaway, "arch_cutaway_diorama") == []

    clean_automata = KineticTracePropRule.compose(
        "vintage brass toggle switches on an oak laboratory desk",
        "three metal switches snap downward one by one by themselves",
        "amber indicator lamps glow softly across the panel",
    )
    assert validate_zero_flesh_and_crystal_specimen(clean_automata, "kinetic_trace_automata") == []

    # Human, mannequin, disembodied flesh hand, animal, and text must all be blocked
    bad_mannequin = "A matte-white porcelain mannequin sits at the wooden desk beside a dog and a signboard."
    errs_m = validate_zero_flesh_and_crystal_specimen(bad_mannequin, "arch_cutaway_diorama")
    assert any("[zero_flesh]" in e for e in errs_m)

    bad_hand = "A bare hand reaches across the oak table to press the brass switch."
    errs_h = validate_zero_flesh_and_crystal_specimen(bad_hand, "kinetic_trace_automata")
    assert any("[zero_flesh]" in e for e in errs_h)

    # Approved matte bisque-ceramic architectural scale figure (incl. R56-M expressive human motion) & 2-mode dark-void 3D brain pass
    ceramic_cutaway = DioramaCutawayRule.compose(
        "an 1848 granite railroad cut with timber derricks",
        "a small featureless matte-white bisque-ceramic architectural scale figure with a featureless smooth ovoid ceramic head grips an iron tamping bar with both hands, climbs the wooden stairs on steady legs, and turns its smooth head toward the lantern",
    )
    assert validate_zero_flesh_and_crystal_specimen(ceramic_cutaway, "arch_cutaway_diorama") == []

    cortical_brain = ArchitecturalBrainMaquetteRule.compose(
        "Localized soft cyan-blue subsurface glow illuminates the prefrontal cortex brightest along the recessed sulcal grooves",
        brain_mode="matte_white_cortical_sulcal_glow",
    )
    assert validate_zero_flesh_and_crystal_specimen(cortical_brain, "arch_brain_maquette") == []

    xray_brain = ArchitecturalBrainMaquetteRule.compose(
        "Bilateral curved hippocampal hubs glow in smooth volumetric cyan-blue luminescence while brainstem pathways glow soft crimson-red",
        brain_mode="translucent_smoked_glass_subcortical_xray",
    )
    assert "semi-translucent frosted smoked-glass" in xray_brain
    assert validate_zero_flesh_and_crystal_specimen(xray_brain, "arch_brain_maquette") == []

    # Approved pedestal satin-frosted optical crystal head bust & hand sculpture pass
    good_bust = CrystalSpecimenRule.compose(
        "human head bust",
        "a dark-oak and brushed-brass museum plinth",
        "a tapered iron rod glides upward beneath the left cheek facet while muted crimson-red luminance dims the left prefrontal cortex",
    )
    assert validate_zero_flesh_and_crystal_specimen(good_bust, "frosted_crystal_specimen") == []

    good_hand_crystal = CrystalSpecimenRule.compose(
        "hand sculpture",
        "a brushed-brass laboratory pedestal",
        "a soft velvet brush glides across the crystal finger facets while soft cyan-blue luminance traces internal nerve channels",
    )
    assert validate_zero_flesh_and_crystal_specimen(good_hand_crystal, "frosted_crystal_specimen") == []

    # Floating unmounted crystal or clear glass without satin-frosted optical crystal fails
    floating_crystal = "A satin-frosted borosilicate optical crystal human head bust floats in midair."
    errs_float = validate_zero_flesh_and_crystal_specimen(floating_crystal, "frosted_crystal_specimen")
    assert any("[crystal]" in e for e in errs_float)


def test_number_analogy_pairing_and_paradox_title() -> None:
    paired_lines = [
        "The solid iron shaft weighed thirteen pounds.",
        "Lifting it felt heavier than holding a bowling ball.",
        "The iron severed eleven percent of white matter cables.",
        "Losing those cables was like cutting a wagon brake line.",
    ]
    assert validate_number_analogy_pairing(paired_lines) == []

    unpaired_lines = [
        "The electrode array recorded forty-eight channels across the cortex.",
        "Researchers published the paper the following spring.",
    ]
    unpaired_errs = validate_number_analogy_pairing(unpaired_lines)
    assert len(unpaired_errs) == 1
    assert "[analogy]" in unpaired_errs[0]

    title = build_diorama_paradox_title(
        "A 13-Pound Iron Rod Shot Through His Skull",
        "Yet He Drove Six-Horse Mountain Stagecoaches",
    )
    assert validate_diorama_paradox_title(title) == []
    assert validate_diorama_paradox_title("한국어 제목 테스트, 영어 아님") != []
    assert validate_diorama_paradox_title("Single Clause Title Without Pivot Separator") != []


def test_golden_gage_diorama_v6_prompt_gate_and_write_prompts() -> None:
    script_doc = json.loads((GOLDEN_V6_DIR / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((GOLDEN_V6_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]

    assert is_diorama_v6_plan(visual_plan) is True
    assert is_v5_plan(visual_plan) is False

    clips = build_flow_prompts(visual_plan, sentences)
    assert len(clips) == len(visual_plan["clips"])
    assert len(clips) >= len(sentences) + 1
    out_prompts = write_flow_prompts_json(GOLDEN_V6_DIR, clips)
    assert out_prompts.exists()
    saved = json.loads(out_prompts.read_text(encoding="utf-8"))
    assert saved["schema_version"] == 6
    assert saved["profile"] == "neuro_diorama"

    issues = validate_production_diorama_v6(visual_plan, sentences, clips, script_doc=script_doc)
    fact_issues = rd.check_narration_facts("phineas_gage_iron_rod", sentences)
    assert issues == [], f"Unexpected v6 prompt-gate issues: {issues}"
    assert fact_issues == [], f"Unexpected dossier fact-trace issues: {fact_issues}"

    # Verify opening channel slogan is strictly rejected by prompt-gate
    bad_sents = ["University brain science, made simple."] + sentences[1:]
    bad_issues = validate_production_diorama_v6(visual_plan, bad_sents, clips, script_doc=script_doc)
    assert any("banned channel-slogan opener" in e for e in bad_issues)


def _make_synthetic_flow_clip(dst: Path, idx: int, ffmpeg_exe: str) -> None:
    """Renders an 8s 1080x1920@30fps moving test clip > 1MB with unique visual geometry & optical flow."""
    hue = (idx * 37) % 360
    speed_x = 90 + (idx % 5) * 28
    speed_y = 110 + (idx % 4) * 32
    vf = (
        f"hue=h={hue}:s=1.2,"
        "scroll=horizontal=0.012:vertical=0.008,"
        f"drawbox=x='mod(t*{speed_x},820)':y='60+mod(t*{speed_y},420)':w=260:h=260:color=white@0.85:t=fill,"
        f"drawbox=x='820-mod(t*{speed_x},780)':y='500+mod(t*{speed_y // 2},600)':w=160:h=160:color=orange@0.80:t=fill,"
        "format=yuv420p"
    )
    cmd = [
        ffmpeg_exe, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "lavfi", "-i", "testsrc2=size=1080x1920:rate=30:duration=8.2",
        "-vf", vf,
        "-c:v", "libx264", "-threads", "2", "-preset", "ultrafast", "-b:v", "1800k", "-maxrate", "2200k", "-bufsize", "3000k",
        "-pix_fmt", "yuv420p", "-an",
        str(dst),
    ]
    subprocess.run(cmd, check=True, capture_output=True, timeout=180, stdin=subprocess.DEVNULL)


@pytest.mark.slow
def test_end_to_end_diorama_v6_assembly_and_autopsy(tmp_path: Path) -> None:
    proj_dir = tmp_path / "gage_diorama_v6_e2e"
    (proj_dir / "02_script").mkdir(parents=True)
    (proj_dir / "03_visuals" / "flow_native_clips").mkdir(parents=True)
    (proj_dir / "03_visuals" / "flow_screenshots").mkdir(parents=True)
    (proj_dir / "04_audio").mkdir(parents=True)
    (proj_dir / "05_assembly").mkdir(parents=True)
    (proj_dir / "06_publish").mkdir(parents=True)

    script_doc = json.loads((GOLDEN_V6_DIR / "script.json").read_text(encoding="utf-8"))
    visual_plan = json.loads((GOLDEN_V6_DIR / "visual_plan.json").read_text(encoding="utf-8"))
    sentences = script_doc["sentences"]

    (proj_dir / "02_script" / "script.json").write_text(json.dumps(script_doc, indent=2), encoding="utf-8")
    (proj_dir / "03_visuals" / "visual_plan.json").write_text(json.dumps(visual_plan, indent=2), encoding="utf-8")
    clips_meta = build_flow_prompts(visual_plan, sentences)
    write_flow_prompts_json(proj_dir, clips_meta)

    from concurrent.futures import ThreadPoolExecutor

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    n_clips = len(clips_meta)
    clip_paths = [proj_dir / "03_visuals" / "flow_native_clips" / f"clip_{i}.mp4" for i in range(1, n_clips + 1)]
    with ThreadPoolExecutor(max_workers=4) as pool:
        list(pool.map(lambda p: _make_synthetic_flow_clip(p[1], p[0], ff), enumerate(clip_paths, start=1)))

    receipt_clips = []
    for i, cf in enumerate(clip_paths, start=1):
        sha = hashlib.sha256(cf.read_bytes()).hexdigest()
        receipt_clips.append(
            {
                "clip_index": i,
                "sha256": sha,
                "file_size_bytes": cf.stat().st_size,
                "source_download_filename": f"flow_diorama_clip_{i:02d}.mp4",
            }
        )

    # Create valid V1-V5 screenshot placeholders + provenance receipt for VideoAutopsyEngine Guard 1
    import cv2

    scr_dir = proj_dir / "03_visuals" / "flow_screenshots"
    scr_rng = np.random.default_rng(42)
    req_screenshots = (
        "flow_gate_v1_prompt_approved.png",
        "flow_gate_v2_rendering_active.png",
        "flow_gate_v3_canvas_clips_ready.png",
        "flow_gate_v4_export_ready.png",
    )
    for g_idx, ss_name in enumerate(req_screenshots, start=1):
        img = scr_rng.integers(30 + g_idx * 15, 220, size=(360, 640, 3), dtype=np.uint8)
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
    receipt = {
        "project_id": proj_dir.name,
        "worker_id": f"subagent-{proj_dir.name}",
        "subagent_1_to_1_bound": True,
        "visual_gates_passed": True,
        "flow_project_url": "https://flow.google.com/project/88f2a901-77bc-4e11-9a22-ab12cd34ef56",
        "tab_target_id": "TAB_DIORAMA_V6_01",
        "prompts_submitted_count": n_clips,
        "clips": receipt_clips,
    }
    (proj_dir / "03_visuals" / "flow_provenance_receipt.json").write_text(json.dumps(receipt, indent=2), encoding="utf-8")

    # Deterministic synthetic baritone speech bursts (~3.0s each x 56 sentences -> auto-fitted into ~176.5s)
    sr = 48000
    synth_lines: list[np.ndarray] = []
    rng = np.random.default_rng(1848)
    for s_idx, sent in enumerate(sentences):
        dur = 3.20 + 0.06 * (len(sent.split()) - 7)
        n = int(round(dur * sr))
        t = np.arange(n, dtype=np.float32) / float(sr)
        syl_env = 0.55 + 0.45 * np.sin(2.0 * np.pi * 4.2 * t + s_idx)
        carrier = (
            0.55 * np.sin(2.0 * np.pi * 118.0 * t)
            + 0.28 * np.sin(2.0 * np.pi * 236.0 * t)
            + 0.06 * rng.standard_normal(n).astype(np.float32)
        )
        fade = np.minimum(1.0, np.minimum(t / 0.03, (dur - t) / 0.04)).astype(np.float32)
        synth_lines.append((0.42 * carrier * syl_env * fade).astype(np.float32))

    res = assemble_diorama_project(
        proj_dir,
        force_rebuild=True,
        align_whisper=False,
        pre_synthesized_lines=synth_lines,
    )

    final_mp4 = Path(res["final_mp4"])
    assert final_mp4.exists()
    assert cfg.DIORAMA_DURATION_MIN_SEC <= res["duration_sec"] <= cfg.SHORTS_HARD_CEILING_SEC
    assert cfg.DIORAMA_TARGET_CUT_MIN <= res["cut_count"] <= 108

    edl = json.loads(Path(res["edl_path"]).read_text(encoding="utf-8"))
    assert edl["total_frames"] <= cfg.SHORTS_HARD_CEILING_FRAMES
    assert edl["zero_clip_reuse"] is True
    assert edl["max_clip_reuse"] == 1
    assert edl["split_screen_cuts"] >= 1
    assert edl["cuts"][-1]["outro_sky_card"] is True

    ass_txt = Path(res["ass_path"]).read_text(encoding="utf-8")
    assert f",{cfg.DIORAMA_SUBTITLE_MARGIN_V},1" in ass_txt
    assert "00D7FF" not in ass_txt.upper()
    assert "20 12" not in ass_txt and "2012" in ass_txt
    assert "OutroTitle" in ass_txt
    assert "SplitTop" in ass_txt

    probe_rep = MediaIntegrityValidator.validate_video_file(
        final_mp4,
        require_30s_shorts=True,
        check_motion=True,
        check_audio=True,
        strict=True,
    )
    assert probe_rep["passed"] is True
    assert probe_rep["frame_count"] <= cfg.SHORTS_HARD_CEILING_FRAMES
    assert abs(probe_rep["frame_count"] - edl["total_frames"]) <= 1

    autopsy = VideoAutopsyEngine.inspect_project(proj_dir, save_report=True)
    assert autopsy["passed"] is True, f"Autopsy failed: {autopsy['prescriptions']}"
    assert autopsy["autopsy_score"] >= 90.0
    assert autopsy["defects"] == []


def test_dynamic_3d_camera_moves_and_frontloaded_leads() -> None:
    from pipeline.depiction_rules import DYNAMIC_3D_CAMERA_LEADS
    from pipeline.flow_prompt_builder import build_diorama_v6_prompts

    expected_dynamic = {
        "dynamic_dolly_rush_in",
        "orbital_3d_arc_sweep",
        "crane_swoop_dive",
        "low_angle_chase_track",
        "vertical_rocket_ascent",
        "fpv_trench_passthrough",
        "pullback_parallax_reveal",
    }
    assert expected_dynamic.issubset(set(cfg.DIORAMA_CAMERA_MOVES))
    assert expected_dynamic == set(DYNAMIC_3D_CAMERA_LEADS.keys())

    moves_list = sorted(expected_dynamic)
    specs = [
        {
            "sentence_index": i + 1,
            "act": 1,
            "grammar": "arch_cutaway_diorama",
            "camera": moves_list[i % len(moves_list)],
            "environment": "a miniature granite railroad cut with timber derricks and iron rails",
            "kinetic_action": "a polished iron rod slides smoothly into a narrow borehole",
            "lighting": "crisp directional silver rim lighting",
        }
        for i in range(21)
    ]
    rendered = build_diorama_v6_prompts(
        {"clips": specs, "aspect": "9:16"},
        ["In eighteen forty-eight, an iron rod pierced a skull."] * 21,
    )
    for i, item in enumerate(rendered):
        move = moves_list[i % len(moves_list)]
        prompt = item["prompt"]
        assert DYNAMIC_3D_CAMERA_LEADS[move] in prompt
        assert "rushing swiftly" not in prompt.lower()
        assert "gliding briskly" not in prompt.lower()
        assert "rapid vertical" not in prompt.lower()
        assert "9:16" not in prompt
        assert "museum plinth" not in prompt.lower()
        assert "40-degree isometric" not in prompt.lower()

