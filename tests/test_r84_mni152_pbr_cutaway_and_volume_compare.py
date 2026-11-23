"""Unit & integration tests for Rule R84 (Blender 4.2 Cycles MNI152 PBR Surgical Cutaway & 2.5x Dashed Volume Compare)."""

from __future__ import annotations

import json
from pathlib import Path

import cv2
import numpy as np
from PIL import Image

from pipeline.anatomy_label_overlay import _render_r78m_dual_callout_rgba, resolve_anatomy_callout_windows
from pipeline.brain_simulator_blender import (
    STACKED_BOT_BOX,
    STACKED_TOP_BOX,
    _draw_dashed_mask_contour,
    is_brain_simulator_clip_spec,
    load_atlas_manifest,
    render_brain_simulator_clip,
)
from pipeline.config import (
    R84_BLENDER_RENDER_ENGINE,
    R84_CYCLES_SAMPLES,
    R84_STACKED_CUTAWAY_ZOOM,
    is_r84_mni152_cutaway_pbr_plan,
)
from pipeline.diorama_assembler import build_v7_dynamic_edl
from pipeline.posthoc_semantic_qa import _max_horizontal_plaque_glyph_run


def test_agents_md_budget_and_r84_constants() -> None:
    agents_md = Path(__file__).resolve().parents[1] / ".agents" / "AGENTS.md"
    raw = agents_md.read_bytes()
    lines = raw.decode("utf-8").splitlines()
    assert len(lines) <= 60, f"AGENTS.md line budget exceeded: {len(lines)}"
    assert 3_000 <= len(raw) <= 6_500, f"AGENTS.md byte budget out of range: {len(raw)}"
    assert "Retired Tier-3" in raw.decode("utf-8")
    brain_md = (Path(__file__).resolve().parents[1] / ".agents" / "rules" / "brain_depiction_rules.md").read_text(encoding="utf-8")
    retired_md = (Path(__file__).resolve().parents[1] / ".agents" / "rules" / "_archive" / "retired_rules_2026-11-18.md").read_text(encoding="utf-8")
    assert "R84" in brain_md and "R84" in retired_md
    assert R84_BLENDER_RENDER_ENGINE == "CYCLES"
    assert R84_CYCLES_SAMPLES >= 12
    assert R84_STACKED_CUTAWAY_ZOOM == 2.5
    assert is_r84_mni152_cutaway_pbr_plan({"r84_mode": True}) is True
    assert is_r84_mni152_cutaway_pbr_plan({}, project_id="v8_ep13_future_study") is False
    assert is_r84_mni152_cutaway_pbr_plan({}, project_id="v8_ep08_capgras_imposter_delusion") is False


def test_is_brain_simulator_clip_spec_r84_routing() -> None:
    assert is_brain_simulator_clip_spec({"grammar": "brain_simulator_3d", "render_engine": "blender_3d_simulator", "r78m_flow_prompt": "legacy"}) is True
    assert is_brain_simulator_clip_spec({"grammar": "brain_simulator_3d", "render_engine": "google_flow"}) is False
    assert is_brain_simulator_clip_spec({"grammar": "brain_simulator_3d"}) is True


def test_dashed_baseline_contour_plaque_clean_and_visible() -> None:
    panel = np.full((320, 640, 3), (20, 24, 34), dtype=np.uint8)
    mask = np.zeros((320, 640), dtype=np.uint8)
    cv2.ellipse(mask, (320, 160), (180, 75), -14.0, 0, 360, 255, -1)
    out = _draw_dashed_mask_contour(panel, mask)
    bright_px = int(np.count_nonzero(out.mean(axis=2) > 180))
    assert bright_px >= 400
    assert _max_horizontal_plaque_glyph_run(cv2.cvtColor(out, cv2.COLOR_RGB2BGR)) <= 2


def test_edl_and_stacked_vstack_callout_non_crossing() -> None:
    clips_18 = [
        {
            "id": i,
            "clip_number": i,
            "sentence_index": i,
            "end_sentence_index": i,
            "grammar": "brain_simulator_3d" if i == 1 else "expressive_vinyl_world",
            "render_engine": "blender_3d_simulator" if i == 1 else "google_flow",
            "camera_move": "circuit_cooperation_drone" if i == 1 else "gentle_push_in",
            "start_brain_region": "hippocampus" if i == 1 else None,
            "end_brain_region": "hippocampus" if i == 1 else None,
            "stacked_cutaway_brain_compare": (i == 1),
            "dashed_baseline": (i == 1),
            "morph_mode": "posterior_hypertrophy" if i == 1 else None,
            "r78m_callout": (
                {
                    "left_lbl": "Taxi Driver",
                    "right_lbl": "Bus Driver",
                    "arrow": "vs",
                    "sub": "Rear +33% Outside Dashed Line",
                    "left_rgb": [232, 84, 96],
                    "right_rgb": [66, 168, 228],
                }
                if i == 1
                else None
            ),
        }
        for i in range(1, 19)
    ]
    vp = {
        "schema": 8,
        "style_profile": "expressive_25d_v8",
        "r82_mode": True,
        "r84_mode": True,
        "clips": clips_18,
    }
    spans = [
        {
            "sentence_index": i,
            "start_sec": round((i - 1) * 4.5, 2),
            "end_sec": round(i * 4.5 - 0.1, 2),
            "duration_sec": 4.4,
        }
        for i in range(1, 19)
    ]
    edl = build_v7_dynamic_edl(
        vp,
        spans,
        [Path(f"/tmp/clip_{i}.mp4") for i in range(1, 19)],
        speech_end_sec=81.0,
        total_duration_sec=81.2,
        virtual_clip_duration_sec=6.0,
    )
    cut0 = edl["cuts"][0]
    assert cut0["mode"] == "split_vstack"
    assert cut0["stacked_cutaway_brain_compare"] is True

    fake_track = {
        "layout": "stacked_vstack",
        "width": 1080,
        "height": 1920,
        "fps": 30.0,
        "n_frames": 30,
        "start_region": "hippocampus",
        "end_region": "hippocampus",
        "frames": [
            {
                "frame": i,
                "t_sec": round(i / 30.0, 4),
                "anchors": {
                    "start": {"x_px": 390.0, "y_px": 610.0, "x_norm": 390.0 / 1080.0, "y_norm": 610.0 / 1920.0},
                    "end": {"x_px": 740.0, "y_px": 1030.0, "x_norm": 740.0 / 1080.0, "y_norm": 1030.0 / 1920.0},
                },
            }
            for i in range(30)
        ],
    }
    cws = resolve_anatomy_callout_windows(edl, vp)
    assert len(cws) == 1
    cws[0]["camera_track"] = fake_track
    canvas = Image.new("RGBA", (1080, 1920), (0, 0, 0, 0))
    rendered = _render_r78m_dual_callout_rgba(
        canvas,
        cws[0],
        0.8,
        1.0,
        width=1080,
        height=1920,
        safe_x_left=60.0,
        safe_x_right=920.0,
        safe_y_top=150,
        safe_y_bot=1260,
        frame_index=12,
    )
    arr = np.asarray(rendered)
    assert int(np.count_nonzero(arr[:, :, 3] > 32)) > 2000
    # Strict right UI rail clearance (X >= 925 has zero ink)
    assert int(np.count_nonzero(arr[:, 926:, 3] > 0)) == 0


def test_r84_cycles_stacked_and_cutaway_smoke_render(tmp_path: Path) -> None:
    mf = load_atlas_manifest()
    assert "hippocampus" in mf["regions"]
    out_mp4 = tmp_path / "clip_17.mp4"
    res = render_brain_simulator_clip(
        {
            "grammar": "brain_simulator_3d",
            "render_engine": "blender_3d_simulator",
            "camera_move": "circuit_cooperation_drone",
            "start_brain_region": "hippocampus",
            "end_brain_region": "hippocampus",
            "stacked_cutaway_brain_compare": True,
            "dashed_baseline": True,
            "morph_mode": "posterior_hypertrophy",
            "cycles_samples": 6,
            "n_frames": 6,
        },
        out_mp4,
        fps=6,
        threads=4,
        force=True,
    )
    assert out_mp4.is_file() and out_mp4.stat().st_size > 10_000
    assert res["sim_qa"]["passed"] is True, f"SQ failed: {res['sim_qa']}"
    track = json.loads(Path(res["camera_track_path"]).read_text(encoding="utf-8"))
    assert track["layout"] == "stacked_vstack"
    assert len(track["frames"]) == 6
    f0 = track["frames"][0]["anchors"]
    assert STACKED_TOP_BOX[1] <= f0["start"]["y_px"] <= STACKED_TOP_BOX[3]
    assert STACKED_BOT_BOX[1] <= f0["end"]["y_px"] <= STACKED_BOT_BOX[3]
