"""
Master Parity & Implementation Tests (`Track 3` + Bible/Docs Parity):
  - P0-1: Audio & lip-sync negative guard + Ep #13 prompt-gate + prompt diet strip safety
  - P0-2: Selective color backdrop clause & Act 1-6 lighting arc helpers (without context-split bloat)
  - P1-4: hero_low_angle (~40% fill, zero 'dolly') & resolve_alternating_camera_move
  - P1-6: Intra-cut 4x3 (64x36) 1-frame luma flicker detector + planned fast move exemption
  - Tier A-1: CLI --summary flag & `main.py qa-summary` <= 2000B digest
  - Tier S-3: Coarse 1536x1536 (4x3) & fine <=384x384 VLM triage sheets
  - Track 2 Parity: `scripts/verify_assets_bible.py --check`, docs, golden sheet, 99 canonical slots,
    4 Ep #31 originals, 15 sheets, 4 fonts, 2 BGMs, and 6 KB JSON registries.
"""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import sys

import numpy as np
from PIL import Image
import pytest

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent


# ---------------------------------------------------------------------------
# P0-1: Audio & Lip-Sync Negative Guard
# ---------------------------------------------------------------------------


def test_p0_1_audio_and_lipsync_negative_guard_and_diet_parity() -> None:
    from pipeline.config import EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    from pipeline.depiction_rules import (
        BANNED_FLOW_CAMERA_HARDWARE_RE,
        FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD,
        ExpressiveV8PromptComposer,
    )

    guard_low = FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD.lower()
    assert "no voiceover, no narration, no background music, no lip movement." in guard_low
    assert "camera lens" in guard_low

    prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        scene_body=(
            "A clothed 2.5D matte cream-white vinyl character raises charcoal-black 2D ink eyebrows "
            "and slides an espresso cup across the oak desk"
        ),
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
        transition_out="cut",
        context_split=True,
    )
    assert prompt.endswith(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD)
    prompt_core = prompt.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    assert prompt_core.endswith("Silent voice track.")
    lo, hi = EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    assert lo <= len(prompt_core.split()) <= hi
    assert not BANNED_FLOW_CAMERA_HARDWARE_RE.search(prompt_core)


def test_p0_1_ep13_prompt_gate_passes_cleanly() -> None:
    ep13_dir = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "projects" / "v8_ep13_snack_reward_rewiring"
    if not ep13_dir.exists():
        pytest.skip("Ep #13 project directory not present on disk")
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "main.py", "prompt-gate", "--dir", str(ep13_dir)],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"Ep #13 prompt-gate failed:\n{proc.stdout}\n{proc.stderr}"
    data = json.loads(proc.stdout)
    assert data.get("passed") is True
    assert data.get("issues") == []
    assert data.get("warnings") == []


# ---------------------------------------------------------------------------
# P0-2 & P1-4: Selective Color, Act Lighting Arc, Hero Low-Angle & Alternation
# ---------------------------------------------------------------------------


def test_p0_2_selective_color_and_act_lighting_arc() -> None:
    from pipeline.config import EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    from pipeline.depiction_rules import (
        BANNED_FLOW_CAMERA_HARDWARE_RE,
        FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD,
        SELECTIVE_COLOR_BACKDROP_CLAUSE,
        ExpressiveV8PromptComposer,
        ExpressiveVinylWorldRule,
        SceneDepictionRule,
        resolve_act_lighting_hint,
    )
    from pipeline.reference_pack import populate_expressive_v8_reference_contract

    expected_clause = "warm muted low-saturation architectural backdrop isolating the vivid full-color hero prop"
    assert SELECTIVE_COLOR_BACKDROP_CLAUSE == expected_clause
    assert SceneDepictionRule.selective_color_backdrop_clause(is_brain=False) == expected_clause
    assert SceneDepictionRule.selective_color_backdrop_clause(is_brain=True) == ""

    composed_world = ExpressiveVinylWorldRule.compose(
        environment="a warm wooden kitchen counter",
        action="the vinyl figure reaches toward a bright red mug",
        lighting=resolve_act_lighting_hint(1),
    )
    assert expected_clause in composed_world

    # Act lighting hints map Acts 1, 2, 3-5, 6 distinctly
    l1 = resolve_act_lighting_hint(1)
    l2 = resolve_act_lighting_hint(2)
    l3 = resolve_act_lighting_hint(3)
    l4 = resolve_act_lighting_hint(4)
    l5 = resolve_act_lighting_hint(5)
    l6 = resolve_act_lighting_hint(6)
    assert "daylight" in l1.lower()
    assert "clinical" in l2.lower()
    assert l3 == l4 == l5 and "rim lighting" in l3.lower()
    assert "golden-hour" in l6.lower()
    assert resolve_act_lighting_hint("hook") == l1
    assert resolve_act_lighting_hint("lab_experiment") == l2
    assert resolve_act_lighting_hint("mechanism") == l3
    assert resolve_act_lighting_hint("resolution") == l6

    # Verify non-brain 2.5D keyframe prompt builder injects selective color & act lighting
    plan = {
        "style_profile": "expressive_25d_v8",
        "schema_version": 8,
        "daisy_chain_keyframes": True,
        "real_environment": "a minimalist study desk",
        "clips": [
            {
                "clip_number": 1,
                "grammar": "expressive_vinyl_world",
                "act_index": 1,
                "environment": "a minimalist wooden study desk",
                "action": "the vinyl figure examines a vivid cobalt cup",
            },
            {
                "clip_number": 2,
                "grammar": "expressive_xray_brain",
                "brain_clip": True,
                "environment": "neurology dark void",
            },
        ],
    }
    compiled = populate_expressive_v8_reference_contract(plan, daisy_chain_keyframes=True)
    anchors = compiled.get("reference_anchors") or []
    non_brain_anchors = [a for a in anchors if a.get("setting") == "real_env"]
    brain_anchors = [a for a in anchors if a.get("setting") == "brain_studio"]
    assert non_brain_anchors
    assert expected_clause in non_brain_anchors[0]["prompt"]
    assert "daylight" in non_brain_anchors[0]["prompt"].lower()
    assert brain_anchors and expected_clause not in brain_anchors[0]["prompt"]

    # Ensure Act lighting still keeps context_split compose within (18, 64) word bounds
    lo, hi = EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    cs_prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        scene_body=f"Clothed 2.5D vinyl character checks notes in {l2}",
        grammar="expressive_vinyl_world",
        camera_move="gentle_push_in",
        context_split=True,
    )
    cs_core = cs_prompt.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    assert lo <= len(cs_core.split()) <= hi
    assert not BANNED_FLOW_CAMERA_HARDWARE_RE.search(cs_core)


def test_p1_4_hero_low_angle_and_alternating_camera_moves() -> None:
    from pipeline.depiction_rules import (
        BANNED_FLOW_CAMERA_HARDWARE_RE,
        EXPRESSIVE_V8_CAMERA_DESCRIPTORS,
        EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS,
        EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS,
        resolve_alternating_camera_move,
    )
    from pipeline.prompt_builder import build_expressive_v8_prompts, validate_expressive_v8_prompts

    expected_desc = "Subtle upward low-angle hero framing (~40% frame fill) with smooth disembodied push-in."
    assert EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS["hero_low_angle"] == expected_desc
    assert "hero_low_angle" in EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS
    assert "smooth_pull_back" in EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS
    for key in ("hero_low_angle", "smooth_pull_back"):
        assert not BANNED_FLOW_CAMERA_HARDWARE_RE.search(EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS[key])
        assert not BANNED_FLOW_CAMERA_HARDWARE_RE.search(EXPRESSIVE_V8_SUPPLEMENTAL_CAMERA_DESCRIPTORS[key])
        assert "dolly" not in EXPRESSIVE_V8_COMPACT_CAMERA_DESCRIPTORS[key].lower()
    assert len(EXPRESSIVE_V8_CAMERA_DESCRIPTORS) >= 28

    assert resolve_alternating_camera_move(0, explicit_move="locked_tripod") == "locked_tripod"
    non_brain_seq = [resolve_alternating_camera_move(i, is_brain=False) for i in range(6)]
    assert set(non_brain_seq) == {"gentle_push_in", "smooth_pull_back", "hero_low_angle"}
    for i in range(len(non_brain_seq) - 1):
        assert non_brain_seq[i] != non_brain_seq[i + 1]
    brain_seq = [resolve_alternating_camera_move(i, is_brain=True) for i in range(4)]
    assert all(m.startswith("neural_") for m in brain_seq)
    assert brain_seq[0] != brain_seq[1]

    # Check `build_expressive_v8_prompts` + `validate_expressive_v8_prompts` across a valid 14-clip plan
    sample_cams = ["hero_low_angle", "smooth_pull_back", "gentle_push_in"]
    clips_spec = [
        {
            "clip_number": i,
            "grammar": "expressive_vinyl_world",
            "camera": sample_cams[(i - 1) % len(sample_cams)],
            "reference_image": f"03_visuals/reference_images/kf_{i:02d}.png",
            "action": (
                "the vinyl character grabs the bright snack cup briskly across the desk"
                if i % 2 == 1
                else "the vinyl character steps backward in surprise across the desk"
            ),
        }
        for i in range(1, 15)
    ]
    plan = {
        "style_profile": "expressive_25d_v8",
        "schema_version": 8,
        "allow_legacy_v8_clip_count": True,
        "allow_low_flight_ratio": True,
        "clips": clips_spec,
    }
    clips = build_expressive_v8_prompts(plan, narrations=[f"Short test narration line {i}." for i in range(1, 15)])
    assert expected_desc in clips[0]["prompt"]
    issues = validate_expressive_v8_prompts(clips, plan)
    assert not any("hero_low_angle" in iss or "smooth_pull_back" in iss or "camera clause" in iss for iss in issues)


# ---------------------------------------------------------------------------
# P1-6: Intra-Cut 4x3 (64x36) 1-Frame Luminance Flicker Detector
# ---------------------------------------------------------------------------


def test_p1_6_intracut_luma_flicker_detector() -> None:
    from pipeline.posthoc_qa import detect_intracut_grid_luma_flicker

    # 1. Smooth slowly drifting gradient frames -> 0 flicker spikes
    smooth_frames = [
        np.full((72, 128, 3), int(90 + i * 1.5), dtype=np.uint8)
        for i in range(10)
    ]
    res_smooth = detect_intracut_grid_luma_flicker(smooth_frames, fps=30.0, cut_index=1)
    assert res_smooth["intracut_flicker_spikes"] == 0
    assert res_smooth["extreme_flicker_warning"] is False
    assert res_smooth["exempt_planned_fast_move"] is False

    # 2. 1-frame flash at frame 5 (+55 luma) -> detected & extreme warning triggered
    flash_frames = [np.full((72, 128, 3), 80, dtype=np.uint8) for _ in range(10)]
    flash_frames[5] = np.full((72, 128, 3), 135, dtype=np.uint8)
    res_flash = detect_intracut_grid_luma_flicker(flash_frames, fps=30.0, cut_index=2)
    assert res_flash["intracut_flicker_spikes"] >= 1
    assert res_flash["max_spike_delta"] >= 32.0
    assert res_flash["extreme_flicker_warning"] is True

    # 3. Cut boundary edge flash at index 0 & index 9 -> ignored due to boundary_trim_frames=2
    edge_frames = [np.full((72, 128, 3), 80, dtype=np.uint8) for _ in range(10)]
    edge_frames[0] = np.full((72, 128, 3), 220, dtype=np.uint8)
    edge_frames[9] = np.full((72, 128, 3), 220, dtype=np.uint8)
    res_edge = detect_intracut_grid_luma_flicker(edge_frames, fps=30.0, cut_index=3, boundary_trim_frames=2)
    assert res_edge["intracut_flicker_spikes"] == 0
    assert res_edge["extreme_flicker_warning"] is False

    # 4. Planned fast move (whip_pan) -> exempt_planned_fast_move=True & extreme_flicker_warning=False
    res_whip = detect_intracut_grid_luma_flicker(
        flash_frames, fps=30.0, camera_move="whip_pan_occlusion", cut_index=4
    )
    assert res_whip["exempt_planned_fast_move"] is True
    assert res_whip["extreme_flicker_warning"] is False


# ---------------------------------------------------------------------------
# Tier A-1: CLI --summary & `main.py qa-summary`
# ---------------------------------------------------------------------------


def test_tier_a1_compact_qa_digest_and_cli_qa_summary(tmp_path: Path) -> None:
    from pipeline.cli import build_compact_qa_digest

    huge_report = {
        "project_id": "v8_test_project",
        "passed": False,
        "gates": {f"DQ{i}": {"passed": (i % 2 == 0)} for i in range(1, 20)},
        "defects": [f"Defect #{i}: very long synthetic failure description {'x' * 90}" for i in range(40)],
        "summary": {"weak_cut_indices": list(range(1, 30)), "mean_clarity_score": 68.5},
    }
    digest = build_compact_qa_digest(huge_report, stage="episode-qa", max_bytes=1800)
    raw_bytes = json.dumps(digest, ensure_ascii=False).encode("utf-8")
    assert len(raw_bytes) <= 1800
    assert digest["passed"] is False
    assert len(digest["failed_gates"]) >= 1
    assert len(digest["suspect_clips"]) >= 1

    # Stage synthetic on-disk QA reports inside tmp_path & test `main.py qa-summary --dir`
    (tmp_path / "03_visuals").mkdir(parents=True)
    (tmp_path / "04_audio").mkdir(parents=True)
    (tmp_path / "05_assembly").mkdir(parents=True)
    (tmp_path / "03_visuals" / "reference_image_qa_report.json").write_text(
        json.dumps({"pre_generation_ready": True}), encoding="utf-8"
    )
    (tmp_path / "04_audio" / "prosody_report.json").write_text(
        json.dumps({"prosody_mode": "expressive_us_v8", "total_duration_sec": 77.6}), encoding="utf-8"
    )
    (tmp_path / "05_assembly" / "prosody_qa_report.json").write_text(
        json.dumps({"passed": True, "gates": {"P1": {"passed": True}}}), encoding="utf-8"
    )
    (tmp_path / "05_assembly" / "dynamic_episode_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "gates": {"DQ5": {"passed": False}, "DQ1": {"passed": True}},
                "defects": ["DQ5 camera pacing violation on cut 4", "extra defect " + ("y" * 200)],
                "suspect_clips": [4, 7],
            }
        ),
        encoding="utf-8",
    )
    (tmp_path / "05_assembly" / "posthoc_semantic_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "summary": {"weak_cut_indices": [7, 11], "mean_clarity_score": 71.2},
                "defects": ["R64 clarity low on cut 11"],
            }
        ),
        encoding="utf-8",
    )

    proc = subprocess.run(
        [sys.executable, "-X", "utf8", "main.py", "qa-summary", "--dir", str(tmp_path)],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.strip().encode("utf-8")) <= 1500
    out = json.loads(proc.stdout)
    assert out["passed"] is False
    assert out["stages"]["prosody"] == {"present": True, "passed": True}
    assert "prosody" not in out["failed_gates"]
    assert "episode_qa:DQ5" in out["failed_gates"]
    assert 4 in out["suspect_clips"] and 7 in out["suspect_clips"] and 11 in out["suspect_clips"]

    # When only timing-only 04_audio/prosody_report.json exists, prosody QA stage is treated as not present
    (tmp_path / "05_assembly" / "prosody_qa_report.json").unlink()
    from pipeline.cli import collect_project_qa_summary

    summary_timing_only = collect_project_qa_summary(tmp_path)
    assert summary_timing_only["stages"]["prosody"] == {"present": False, "passed": None}

    # Confirm `--summary` is accepted cleanly in parser help on all 4 required commands & video-autopsy alias
    for subcmd in ("episode-qa", "autopsy", "video-autopsy", "ref-qa", "dossier"):
        h = subprocess.run(
            [sys.executable, "-X", "utf8", "main.py", subcmd, "--help"],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=False,
        )
        assert h.returncode == 0, f"{subcmd} --help failed: {h.stderr}"
        assert "--summary" in h.stdout


# ---------------------------------------------------------------------------
# Tier S-3: Coarse-to-Fine 2-Stage VLM Triage Sheet Builder
# ---------------------------------------------------------------------------


def test_tier_s3_vlm_triage_sheets_and_fine_crops(tmp_path: Path) -> None:
    from scripts.render_qa_sheets import (
        render_coarse_triage_sheets,
        render_fine_suspect_crops,
    )

    src_dir = tmp_path / "inputs"
    out_dir = tmp_path / "triage_out"
    src_dir.mkdir()
    img_paths: list[Path] = []
    for i in range(1, 15):
        p = src_dir / f"cut_{i:02d}.png"
        im = Image.new("RGB", (540, 960), ((i * 17) % 255, (i * 31) % 255, 120))
        im.save(p, format="PNG")
        img_paths.append(p)
    small_p = src_dir / "small_ref.png"
    Image.new("RGB", (180, 300), (40, 200, 90)).save(small_p, format="PNG")

    coarse = render_coarse_triage_sheets(img_paths, out_dir / "coarse")
    assert len(coarse) == 2
    assert coarse[0]["tile_count"] == 12
    assert coarse[1]["tile_count"] == 2
    for sheet in coarse:
        sp = Path(sheet["sheet_path"])
        assert sp.exists() and sp.suffix == ".jpg"
        with Image.open(sp) as check_im:
            assert check_im.size == (1536, 1536)

    fine = render_fine_suspect_crops([img_paths[0], small_p], out_dir / "fine", crop_size=384)
    assert len(fine) == 2
    with Image.open(fine[0]["crop_path"]) as c0:
        assert c0.size == (384, 384)
    with Image.open(fine[1]["crop_path"]) as c1:
        # Never upscales a 180x300 source past its native minor dimension
        assert c1.size[0] <= 180 and c1.size[1] <= 180 and c1.size[0] == c1.size[1]

    # End-to-end CLI invocation
    cli_out = tmp_path / "cli_triage"
    proc = subprocess.run(
        [
            sys.executable,
            "-X",
            "utf8",
            "scripts/render_qa_sheets.py",
            "--files",
            *[str(p) for p in img_paths[:4]],
            "--suspects",
            "c01,c04",
            "--out-dir",
            str(cli_out),
        ],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, proc.stderr
    assert len(proc.stdout.strip().encode("utf-8")) <= 1536
    manifest = json.loads(proc.stdout)
    assert manifest["coarse_sheet_count"] == 1
    assert manifest["fine_crop_count"] == 2


# ---------------------------------------------------------------------------
# Master Docs & Locked Assets Bible Parity
# ---------------------------------------------------------------------------


def test_master_docs_and_assets_bible_parity() -> None:
    bible_script = WORKSPACE_ROOT / "scripts" / "verify_assets_bible.py"
    bible_md = WORKSPACE_ROOT / "docs" / "LOCKED_ASSETS_AND_REFERENCES_BIBLE.md"
    master_md = WORKSPACE_ROOT / "docs" / "ALL_ABOUT_BRAIN_MASTER_PIPELINE.md"
    golden_jpg = WORKSPACE_ROOT / "docs" / "assets_preview" / "ALL_ABOUT_BRAIN_GOLDEN_STYLE_SHEET.jpg"

    assert bible_script.exists(), "Missing scripts/verify_assets_bible.py"
    proc = subprocess.run(
        [sys.executable, "-X", "utf8", str(bible_script), "--check"],
        cwd=str(WORKSPACE_ROOT),
        capture_output=True,
        text=True,
        check=False,
    )
    assert proc.returncode == 0, f"verify_assets_bible.py --check failed:\n{proc.stdout}\n{proc.stderr}"
    check_json = json.loads(proc.stdout)
    assert check_json.get("passed") is True

    assert bible_md.exists() and bible_md.stat().st_size > 10_000
    assert master_md.exists() and master_md.stat().st_size > 5_000
    assert golden_jpg.exists() and golden_jpg.stat().st_size > 50_000
    with Image.open(golden_jpg) as g_im:
        assert g_im.width >= 1000 and g_im.height >= 500

    # Verify 84 active approved + 15 retired_r88_cartoon_face = 99 locked + 1 deferred (J04) & 15 contact sheets
    ca_root = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "canonical_assets"
    active_approved_slots = 0
    retired_r88_slots = 0
    deferred_slots = 0
    sheet_files = 0
    for pack in ("v1", "v1_1", "v1_2"):
        man_path = ca_root / pack / "manifest.json"
        man = json.loads(man_path.read_text(encoding="utf-8"))
        slots_raw = man.get("slots")
        slot_items = list(slots_raw.values()) if isinstance(slots_raw, dict) else list(slots_raw or [])
        for slot_meta in slot_items:
            if not isinstance(slot_meta, dict):
                continue
            status = slot_meta.get("status")
            if status not in ("approved", "retired_r88_cartoon_face"):
                deferred_slots += 1
                continue
            cand_shas = [
                str(c.get("sha256") or "")
                for c in (slot_meta.get("candidates") or [])
                if isinstance(c, dict) and (c.get("status") == "approved" or c.get("sha256_locked"))
            ]
            slot_sha = str(slot_meta.get("sha256") or slot_meta.get("approved_sha256") or "")
            assert len(slot_sha) >= 32 or any(len(s) >= 32 for s in cand_shas)
            if status == "approved":
                active_approved_slots += 1
            else:
                retired_r88_slots += 1
        sheets_dir = ca_root / pack / "sheets"
        sheet_files += len([p for p in sheets_dir.iterdir() if p.is_file()]) if sheets_dir.is_dir() else 0
    assert active_approved_slots == 84
    assert retired_r88_slots == 15
    assert active_approved_slots + retired_r88_slots == 99
    assert deferred_slots == 1
    assert sheet_files == 15
    assert check_json.get("active_locked_slots") == 84
    assert check_json.get("retired_r88_slots") == 15
    assert check_json.get("locked_slots") == 99
    assert check_json.get("deferred_slots") == 1
    assert check_json.get("contact_sheets") == 15

    # Verify 4 Ep #31 original reference PNGs
    ep31_dir = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / "expressive_25d_v8_refs"
    ep31_pngs = sorted(ep31_dir.glob("ep31_orig_*.png"))
    assert len(ep31_pngs) == 4

    # Verify 4 fonts across channel + pipeline assets/fonts
    fonts = list((WORKSPACE_ROOT / "BCI_Shorts_Channel" / "assets" / "fonts").glob("*.ttf")) + list(
        (WORKSPACE_ROOT / "pipeline" / "assets" / "fonts").glob("*.ttf")
    )
    assert len(fonts) == 4

    # Verify 2 BGM mp3s & 6 KB reusable packs
    kb_packs = WORKSPACE_ROOT / "BCI_Shorts_Channel" / "knowledge_base" / "reusable_packs"
    bgm_mp3s = list((kb_packs / "bgm_bank").glob("*.mp3"))
    kb_jsons = [p for p in kb_packs.glob("*.json") if p.is_file()]
    assert len(bgm_mp3s) == 2
    assert len(kb_jsons) == 6
