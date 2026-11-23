"""
Unit and integration tests for Rule R74-B & Rule R71-B:
  1. 31/31 Complete Brain Coordinate Atlas (`ANATOMY_FUNCTION_MAP` <-> `ANATOMY_SCREEN_ANCHORS`, 0 generic fallback)
  2. 4-State Pathology (`active | silenced | severed | rerouted`), Prompt Sanitizer, State-Keyed `B1` Anchors & CV QA Compatibility
  3. `Previs v2.4` 3D `neural_tract_bridge` + `#D4AF37` `kintsugi_fault_disc` + `#5B6778` Destination Sphere
  4. `Rule R71-B` `single_region` / `pathway_relay` (`──▶`) / `pathway_severed` (`── ✕ ──`) Pen Callouts & Safe Zone (`X=48..910, Y=12%..65%`)
  5. `Rule R74-B` Psychology (`12-26%`) vs Neuroscience (`24-38%`, `>=45%` reveal) Validator & `Ep #7` Frozen Compatibility
"""

from __future__ import annotations

import copy
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline.anatomy_label_overlay import (
    render_anatomy_callout_rgba_frame,
    resolve_anatomy_callout_windows,
)
from pipeline.anatomy_map import (
    ANATOMY_FUNCTION_MAP,
    ANATOMY_SCREEN_ANCHORS,
    build_neural_state_clip_clause,
    build_neural_state_macro_desc,
    resolve_anatomy_screen_anchor,
)
from pipeline.depiction_rules import BANNED_BRAIN_PARTICLE_TOKENS
from pipeline.dynamic_episode_qa import verify_pre_flow_contract
from pipeline.flow_prompt_builder import (
    _PROP_BANNED_TOKENS,
    build_flow_prompts,
    sanitize_prompt_for_flow as sanitize_scene,
    validate_expressive_v8_prompts,
)
from pipeline.porcelain_anchor_pack import populate_expressive_v8_reference_contract
from pipeline.posthoc_semantic_qa import _compute_brain_highlight_chroma
from pipeline.previs_blender import (
    is_blender_available,
    render_previs_keyframes,
    synthesize_default_previs_spec_for_clip,
)
from pipeline.prompt_quality_v5 import (
    validate_production_diorama_v6,
    validate_r74b_neuro_pathway_contract,
)
from pipeline.reference_image_qa import (
    build_reference_image_specs,
    inspect_single_reference_image,
)


def test_r74b_axis1_complete_31_of_31_brain_coordinate_atlas() -> None:
    """All 31 canonical keys in ANATOMY_FUNCTION_MAP must map to unique 3D coordinates in ANATOMY_SCREEN_ANCHORS."""
    func_keys = list(ANATOMY_FUNCTION_MAP.keys())
    assert len(func_keys) >= 31

    missing = [k for k in func_keys if k not in ANATOMY_SCREEN_ANCHORS]
    assert missing == [], f"Missing ANATOMY_SCREEN_ANCHORS entries: {missing}"

    xyz_map: dict[tuple[float, float, float], str] = {}
    for region in func_keys:
        resolved = resolve_anatomy_screen_anchor(region)
        assert resolved["canonical"] == region
        xyz = tuple(round(float(v), 4) for v in resolved["pos_3d_brain_xyz"])
        assert len(xyz) == 3
        assert xyz not in xyz_map, f"Duplicate pos_3d_brain_xyz {xyz} shared by {region!r} and {xyz_map[xyz]!r}"
        xyz_map[xyz] = region
        assert resolved.get("macro_visual_desc"), f"Missing macro_visual_desc on {region}"
        assert resolved.get("glass_visual_desc"), f"Missing glass_visual_desc on {region}"


def _render_synthetic_state_brain_png(path: Path, state: str) -> np.ndarray:
    """Builds a realistic 1080x1920 studio glass-brain test frame for CV gate verification (Q1-Q7 & R64 chroma)."""
    h, w = 1920, 1080
    # Deep studio slate backdrop (non-black to avoid letterbox trigger, rich gradient for entropy)
    yy = np.linspace(38, 62, h, dtype=np.float32)[:, None]
    xx = np.linspace(-8, 8, w, dtype=np.float32)[None, :]
    rng = np.random.default_rng(42 + sum(ord(c) for c in state))
    micro_tex = rng.normal(0.0, 4.5, size=(h, w, 3)).astype(np.float32)

    base = np.zeros((h, w, 3), dtype=np.float32)
    base[:, :, 0] = yy + xx + 18.0  # B
    base[:, :, 1] = yy + 6.0       # G
    base[:, :, 2] = yy - 4.0       # R
    img = np.clip(base + micro_tex, 14, 245).astype(np.uint8)

    # Frosted borosilicate outer cortical shell + gyri ridges (porcelain/vinyl glass S <= 55, V >= 150)
    cv2.ellipse(img, (540, 920), (360, 460), 0, 0, 360, (214, 210, 206), -1, cv2.LINE_AA)
    cv2.ellipse(img, (540, 920), (320, 415), 0, 0, 360, (68, 62, 58), -1, cv2.LINE_AA)
    for r_idx in range(14):
        ang = r_idx * 25
        rx = int(540 + 235 * np.cos(np.deg2rad(ang)))
        ry = int(920 + 300 * np.sin(np.deg2rad(ang)))
        cv2.circle(img, (rx, ry), 46, (218, 214, 208), 5, cv2.LINE_AA)

    # Surrounding cortical reference tracts (sapphire-blue & warm kintsugi gold seams preserved across ALL states)
    cv2.line(img, (320, 680), (510, 860), (235, 165, 42), 14, cv2.LINE_AA)   # BGR sapphire-cyan
    cv2.line(img, (760, 700), (580, 860), (52, 182, 232), 12, cv2.LINE_AA)   # BGR warm amber-gold

    if state == "active":
        cv2.circle(img, (540, 960), 115, (56, 52, 226), -1, cv2.LINE_AA)      # crimson-red core
    elif state == "silenced":
        # Dormant frosted slate-glass core surrounded by active cortical reference tracts
        cv2.circle(img, (540, 960), 115, (142, 134, 126), -1, cv2.LINE_AA)
        cv2.circle(img, (540, 960), 115, (196, 192, 186), 6, cv2.LINE_AA)
    elif state == "severed":
        # Proximal luminous tract halting at kintsugi gold fault seam + unlit slate destination hub
        cv2.line(img, (360, 1020), (505, 965), (56, 178, 236), 18, cv2.LINE_AA)
        cv2.ellipse(img, (535, 955), (14, 48), 22, 0, 360, (55, 175, 212), -1, cv2.LINE_AA)
        cv2.circle(img, (665, 920), 82, (132, 124, 116), -1, cv2.LINE_AA)
    elif state == "rerouted":
        # Detour bypass bridge glowing pearl-aqua & warm amber-gold into reignited hub
        cv2.ellipse(img, (540, 950), (165, 110), 0, 195, 345, (212, 224, 96), 16, cv2.LINE_AA)
        cv2.circle(img, (675, 940), 92, (48, 176, 238), -1, cv2.LINE_AA)

    ok, buf = cv2.imencode(".png", img)
    assert ok
    path.write_bytes(buf.tobytes())
    return img


def test_r74b_axis2_four_states_sanitizer_cache_keys_and_cv_gates(tmp_path: Path) -> None:
    """All 4 neural states pass prompt sanitizers, isolate B1 reference IDs, and pass Q2/Q4/Q6 + R64 chroma."""
    for region in ("fusiform face area", "amygdala", "auditory cortex", "Broca's area", "Wernicke's area"):
        for state in cfg.EXPRESSIVE_V8_NEURAL_STATES:
            end_reg = "amygdala" if region != "amygdala" else "prefrontal cortex"
            macro_txt = build_neural_state_macro_desc(region, state, end_region=end_reg)
            clip_txt = build_neural_state_clip_clause(region, state, end_region=end_reg)
            for sample in (macro_txt, clip_txt):
                low = sample.lower()
                assert "#" not in sample, f"Hex code leaked into prompt text: {sample}"
                for bad in BANNED_BRAIN_PARTICLE_TOKENS:
                    assert bad.lower() not in low, f"Banned brain token {bad!r} in {sample!r}"
                for bad_prop in ("electric", "neon", " glowing slime", "blood"):
                    assert bad_prop not in low, f"Banned token {bad_prop!r} in {sample!r}"
                cleaned = sanitize_scene(sample)
                assert len(cleaned.split()) >= 8

    # Verify synthetic frames for silenced / severed / rerouted pass Q1..Q7 (esp. Q2, Q4, Q6) and R64 highlight chroma >= 6.0
    for state in ("active", "silenced", "severed", "rerouted"):
        png_p = tmp_path / f"ref_brain_B1_amygdala_{state}_macro_9x16.png"
        bgr = _render_synthetic_state_brain_png(png_p, state)
        spec = {
            "ref_id": png_p.stem,
            "category": "brain_anchor",
            "role": "brain_mechanism",
            "setting": "brain_studio",
            "style_profile": cfg.EXPRESSIVE_25D_V8_STYLE_PROFILE,
            "filename": png_p.name,
        }
        rep = inspect_single_reference_image(png_p, spec, aspect="9:16")
        assert rep["axes_q1_to_q7"]["Q2_lighting_and_exposure"] is True, f"Q2 failed on {state}: {rep}"
        assert rep["axes_q1_to_q7"]["Q4_porcelain_cast_fidelity"] is True, f"Q4 failed on {state}: {rep}"
        assert rep["axes_q1_to_q7"]["Q6_brain_4point_color_code"] is True, f"Q6 failed on {state}: {rep}"
        assert rep["passed"] is True, f"Reference QA failed on {state}: {rep}"

        roi_360 = cv2.resize(bgr[360:1150, 50:1030], (360, 290), interpolation=cv2.INTER_AREA)
        chroma = _compute_brain_highlight_chroma(roi_360)
        assert chroma >= 6.0, f"R64 brain highlight chroma too low ({chroma}) on {state}"

    # Verify state-keyed B1 anchor isolation when amygdala is severed in Dive 1 and rerouted in Dive 2
    plan = {
        "project_id": "v8_ep08_state_cache_test",
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "topic_focus": "neuroscience",
        "r72_mode": True,
        "r73_mode": True,
        "r74_mode": True,
        "clips": [
            {
                "id": 1,
                "clip_number": 1,
                "sentence_index": 1,
                "act": 1,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "location_id": "clinic_room",
                "cast_roles": ["protagonist"],
                "scene": "Patient stares across the sunlit clinic table as ink eyes widen in disbelief.",
            },
            {
                "id": 2,
                "clip_number": 2,
                "sentence_index": 8,
                "act": 3,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_fpv_dive_in",
                "location_id": "brain_studio",
                "brain_region": "fusiform face area",
                "neural_state": "active",
                "scene": "FPV probe dives into frosted crystal fusiform ridges glowing warm amber-gold.",
            },
            {
                "id": 3,
                "clip_number": 3,
                "sentence_index": 9,
                "act": 3,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_tract_relay_flight",
                "location_id": "brain_studio",
                "brain_region": "fusiform face area",
                "end_brain_region": "amygdala",
                "start_neural_state": "active",
                "neural_state": "severed",
                "callout_mode": "pathway_severed",
                "scene": "Camera races along the crystal fiber bridge until it halts at a clean kintsugi gold fault break before the dark amygdala.",
            },
            {
                "id": 4,
                "clip_number": 4,
                "sentence_index": 10,
                "act": 4,
                "grammar": "expressive_vinyl_world",
                "camera_move": "gentle_push_in",
                "location_id": "clinic_phone_desk",
                "cast_roles": ["protagonist"],
                "scene": "Patient lifts the corded landline receiver to his ear and smiles warmly in recognition.",
            },
            {
                "id": 5,
                "clip_number": 5,
                "sentence_index": 11,
                "act": 5,
                "grammar": "expressive_xray_brain",
                "camera_move": "neural_tract_relay_flight",
                "location_id": "brain_studio",
                "brain_region": "auditory cortex",
                "end_brain_region": "amygdala",
                "start_neural_state": "active",
                "neural_state": "rerouted",
                "callout_mode": "pathway_relay",
                "scene": "Camera glides along an arching pearl-aqua crystal detour bridge from auditory cortex straight into the reignited amygdala.",
            },
        ],
    }
    pdir = tmp_path / "v8_ep08_state_cache_test"
    (pdir / "03_visuals").mkdir(parents=True)
    pop = populate_expressive_v8_reference_contract(plan, project_dir=pdir, synthesize_scene_anchors=True)
    ref_ids = {r["ref_id"] for r in pop["reference_anchors"]}
    assert "ref_brain_B1_amygdala_severed_macro_9x16" in ref_ids
    assert "ref_brain_B1_amygdala_rerouted_macro_9x16" in ref_ids

    by_num = {int(c["clip_number"]): c for c in pop["clips"]}
    assert by_num[3]["end_reference_image"].endswith("ref_brain_B1_amygdala_severed_macro_9x16.png")
    assert by_num[5]["end_reference_image"].endswith("ref_brain_B1_amygdala_rerouted_macro_9x16.png")
    assert by_num[3]["end_reference_image"] != by_num[5]["end_reference_image"]

    specs_doc = build_reference_image_specs(pop, ["s"] * 12)
    spec_by_id = {s["ref_id"]: s for s in specs_doc["all_specs"]}
    assert spec_by_id["ref_brain_B1_amygdala_severed_macro_9x16"]["neural_state"] == "severed"
    assert spec_by_id["ref_brain_B1_amygdala_rerouted_macro_9x16"]["neural_state"] == "rerouted"


def test_r74b_axis3_previs_v24_tract_bridge_and_severed_kintsugi_fault_disc(tmp_path: Path) -> None:
    """Previs v2.4 renders 3D neural_tract_bridge + #D4AF37 kintsugi_fault_disc + #5B6778 destination sphere."""
    clip = {
        "clip_number": 14,
        "grammar": "expressive_xray_brain",
        "camera_move": "neural_tract_relay_flight",
        "brain_region": "fusiform face area",
        "end_brain_region": "amygdala",
        "neural_state": "severed",
        "scene": "FPV probe races from fusiform face area along the crystal tract bridge and halts at a kintsugi gold fault seam before the dark amygdala.",
    }
    spec = synthesize_default_previs_spec_for_clip(clip, 14)
    assert spec["neural_cutaway_stage"] is True
    assert spec["r74_neural_state"] == "severed"
    block_ids = {b["block_id"]: b for b in spec["room_blocks"]}
    assert "neural_tract_bridge" in block_ids
    assert "neural_tract_bridge_distal" in block_ids
    assert "kintsugi_fault_disc" in block_ids
    assert block_ids["kintsugi_fault_disc"]["color_hex"] == "#D4AF37"

    prop_by_id = {p["prop_id"]: p for p in spec["props"]}
    assert prop_by_id["subcortical_amygdala"]["color_hex"] == "#5B6778"

    # Test deterministic CPU Workbench renderer
    cpu_out = render_previs_keyframes(spec, tmp_path / "previs_cpu", backend="workbench_cpu")
    assert cpu_out["backend_used"] == "workbench_cpu"
    assert cpu_out["visibility_gate_start"]["passed"] is True
    assert cpu_out["visibility_gate_end"]["passed"] is True
    end_bgr = cv2.imread(cpu_out["end_png"])
    assert end_bgr is not None and end_bgr.size > 0
    # Verify shaded #D4AF37 kintsugi_fault_disc gold pixels (shade 0.54..0.98 -> R > G >> B) exist in end_png
    end_rgb = end_bgr[:, :, ::-1].astype(np.float32)
    gold_mask = (
        (end_rgb[:, :, 0] >= 105.0)
        & (end_rgb[:, :, 1] >= 85.0)
        & (end_rgb[:, :, 0] - end_rgb[:, :, 2] >= 65.0)
        & (end_rgb[:, :, 1] - end_rgb[:, :, 2] >= 45.0)
    )
    assert int(np.sum(gold_mask)) >= 20, "Expected visible #D4AF37 kintsugi_fault_disc pixels in Previs end_png"

    # Verify generated Blender Python script compiles cleanly with p0 -> p1 cylinder support
    bl_script_src = Path(cpu_out["blender_script"]).read_text(encoding="utf-8")
    compile(bl_script_src, cpu_out["blender_script"], "exec")
    assert "kintsugi_fault_disc" in bl_script_src


@pytest.mark.slow
def test_r74b_axis3_previs_v24_blender_subprocess(tmp_path: Path) -> None:
    """Slow E2E check: runs headless Blender 4.x on a severed neural_tract_relay_flight spec."""
    if not is_blender_available():
        pytest.skip("Blender executable not available")
    clip = {
        "clip_number": 14,
        "grammar": "expressive_xray_brain",
        "camera_move": "neural_tract_relay_flight",
        "brain_region": "fusiform face area",
        "end_brain_region": "amygdala",
        "neural_state": "severed",
        "scene": "FPV probe races from fusiform face area along the crystal tract bridge and halts at a kintsugi gold fault seam.",
    }
    spec = synthesize_default_previs_spec_for_clip(clip, 14)
    bl_out = render_previs_keyframes(spec, tmp_path / "previs_blender", backend="blender")
    assert bl_out["backend_used"] == "blender"
    assert Path(bl_out["end_png"]).exists()


def test_r71b_axis4_pathway_relay_and_severed_pen_callouts_safe_zone() -> None:
    """R71-B renders pathway_severed (── ✕ ──), pathway_relay (──▶), and silenced tags strictly inside X=48..910, Y=12%..65%."""
    cuts = [
        {
            "cut_index": 12,
            "grammar": "expressive_xray_brain",
            "camera_move": "neural_tract_relay_flight",
            "brain_region": "fusiform face area",
            "end_brain_region": "amygdala",
            "neural_state": "severed",
            "callout_mode": "pathway_severed",
            "callout_gloss": "Signal Blocked!",
            "out_start_sec": 34.0,
            "out_end_sec": 37.2,
            "sentence_indices": [10],
        },
        {
            "cut_index": 18,
            "grammar": "expressive_xray_brain",
            "camera_move": "neural_tract_relay_flight",
            "brain_region": "auditory cortex",
            "end_brain_region": "amygdala",
            "neural_state": "rerouted",
            "callout_mode": "pathway_relay",
            "callout_gloss": "Voice Detour Intact",
            "out_start_sec": 52.0,
            "out_end_sec": 55.2,
            "sentence_indices": [15],
        },
        {
            "cut_index": 20,
            "grammar": "expressive_xray_brain",
            "camera_move": "neural_macro_orbit_hold",
            "brain_region": "prefrontal cortex",
            "neural_state": "silenced",
            "callout_mode": "single_region",
            "out_start_sec": 60.0,
            "out_end_sec": 63.0,
            "sentence_indices": [17],
        },
    ]
    windows = resolve_anatomy_callout_windows({"cuts": cuts})
    assert len(windows) == 3

    w_sev, w_rel, w_sil = windows[0], windows[1], windows[2]
    assert w_sev["callout_mode"] == "pathway_severed"
    assert w_rel["callout_mode"] == "pathway_relay"
    assert w_sil["callout_mode"] == "single_region"
    assert "Offline" in w_sil["short_role"]

    for win in windows:
        pil_rgba = render_anatomy_callout_rgba_frame(
            win,
            t_rel=1.1,
            total_dur=float(win["duration_sec"]),
            width=1080,
            height=1920,
        )
        rgba = np.asarray(pil_rgba, dtype=np.uint8)
        assert rgba.shape == (1920, 1080, 4)
        alpha = rgba[:, :, 3]
        assert int(np.sum(alpha > 0)) >= 800, f"Expected visible ink strokes for {win['callout_mode']}"

        # Strict universal safe-zone guard: alpha == 0 outside X=48..910px and Y=12%..65% (231..1248px)
        assert int(np.max(alpha[:, :48])) == 0
        assert int(np.max(alpha[:, 911:])) == 0
        assert int(np.max(alpha[: int(1920 * 0.12), :])) == 0
        assert int(np.max(alpha[int(1920 * 0.65) + 1 :, :])) == 0

    # Verify crimson break-cross (#EF4444 -> RGB 239, 68, 68) ink pixels appear on pathway_severed
    pil_sev = render_anatomy_callout_rgba_frame(
        w_sev,
        t_rel=1.2,
        total_dur=float(w_sev["duration_sec"]),
        width=1080,
        height=1920,
    )
    rgba_sev = np.asarray(pil_sev, dtype=np.uint8)
    vis_px = rgba_sev[rgba_sev[:, :, 3] >= 120][:, :3].astype(np.int32)
    red_dominance = (vis_px[:, 0] - vis_px[:, 1] >= 90) & (vis_px[:, 0] >= 180)
    assert int(np.sum(red_dominance)) >= 25, "Expected crimson #EF4444 break-cross ink on pathway_severed"


def _build_synthetic_r74b_neuro_plan_and_script() -> tuple[dict[str, Any], dict[str, Any], list[str]]:
    lines = [
        "Why would a loving son look straight at his own father and swear he is an impostor?",
        "After a car crash in San Diego, neuroscientist Vilayanur Ramachandran met a young man named David.",
        "David stared at his parents in the clinic and insisted two identical strangers had replaced them.",
        "Doctor Ramachandran hooked tiny sweat sensors to David's fingers while showing family photos.",
        "Normally your palms spark a tiny sweat jolt the instant you spot someone you love.",
        "David named every face in the stack without a single mistake.",
        "Yet his skin monitor stayed flat as glass on his own mother and father!",
        "Wait, how could he recognize every feature on his dad's face and feel nothing at all?",
        "Inside David's head, his brain's face detector — the fusiform cortex — still lit up sharp and clear.",
        "The crash had snapped the cable carrying that signal to his emotional hub — the amygdala.",
        "Seeing his father matched the right photo file, with zero gut warmth attached.",
        "So his brain invented the only story that fit: this man must be a double.",
        "Then David's parents stepped next door and called him on a clinic landline.",
        "The second he heard his father's voice, David relaxed and greeted his real dad!",
        "Sound travels along a separate cable from hearing hubs straight into the amygdala.",
        "Phone calls worked every time, until his parents walked back through the clinic door.",
        "Familiarity is not something you see — it is a gut signal you feel.",
    ]
    script_doc: dict[str, Any] = {
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "topic_focus": "neuroscience",
        "voice_preset": "elevenlabs_v4",
        "opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "r72_mode": True,
        "r73_mode": True,
        "r74_mode": True,
        "core_reveal_sentence_index": 9,
        "lines": lines,
        "script": " ".join(lines),
    }

    # 25 clips total:
    # Clips 1..11 (indices 0..10 -> 0%..40%): 100% human & exterior/drone scenes (0% brain)
    # Clip 12..14 (48%..56%): Dive 1 (3 brain clips: dive_in FFA -> tract_relay FFA->amygdala severed -> pullback amygdala severed)
    # Clips 15..18: Human clinical twist (landline call)
    # Clips 19..22: Dive 2 (3 brain clips + 1 human -> total 7/25 = 28.0% brain clips!)
    clips: list[dict[str, Any]] = []
    brain_specs: dict[int, dict[str, Any]] = {
        13: {
            "s_idx": 9,
            "camera_move": "neural_fpv_dive_in",
            "brain_region": "fusiform face area",
            "neural_state": "active",
            "scene": "Fast FPV probe plunges through frosted crystal cortical folds into glowing amber-gold fusiform glass ridges.",
        },
        14: {
            "s_idx": 10,
            "camera_move": "neural_tract_relay_flight",
            "brain_region": "fusiform face area",
            "end_brain_region": "amygdala",
            "start_neural_state": "active",
            "neural_state": "severed",
            "callout_mode": "pathway_severed",
            "scene": "Camera races along the crystal fiber bridge and halts at a kintsugi gold fault break before the dark slate amygdala.",
        },
        15: {
            "s_idx": 11,
            "camera_move": "neural_fpv_pullback_out",
            "brain_region": "amygdala",
            "neural_state": "severed",
            "scene": "Rapid FPV pullback glides backward from the unlit slate crystal amygdala out into the full translucent glass brain.",
        },
        20: {
            "s_idx": 15,
            "camera_move": "neural_fpv_dive_in",
            "brain_region": "auditory cortex",
            "neural_state": "active",
            "scene": "Fast FPV probe dives through temporal crystal folds into luminous sapphire-blue auditory glass ridges.",
        },
        21: {
            "s_idx": 15,
            "camera_move": "neural_tract_relay_flight",
            "brain_region": "auditory cortex",
            "end_brain_region": "amygdala",
            "start_neural_state": "active",
            "neural_state": "rerouted",
            "callout_mode": "pathway_relay",
            "scene": "Camera glides along an arching pearl-aqua detour crystal tract straight into the reignited amber-gold amygdala.",
        },
        22: {
            "s_idx": 16,
            "camera_move": "neural_fpv_pullback_out",
            "brain_region": "amygdala",
            "neural_state": "rerouted",
            "scene": "Rapid FPV pullback rockets out from the reignited amber-gold crystal amygdala back to the full 3D glass brain.",
        },
        24: {
            "s_idx": 17,
            "camera_move": "neural_macro_orbit_hold",
            "brain_region": "prefrontal cortex",
            "neural_state": "active",
            "scene": "Tight macro orbit holds around warm amber-gold prefrontal crystal ridges inside frosted borosilicate cortical walls.",
        },
    }
    for idx in range(25):
        c_num = idx + 1
        s_idx = min(len(lines), (idx * len(lines)) // 25 + 1)
        if c_num in brain_specs:
            bs = brain_specs[c_num]
            entry: dict[str, Any] = {
                "id": c_num,
                "clip_number": c_num,
                "sentence_index": bs["s_idx"],
                "act": min(6, (idx * 6) // 25 + 1),
                "visual_grammar": "expressive_xray_brain",
                "grammar": "expressive_xray_brain",
                "camera": bs["camera_move"],
                "camera_move": bs["camera_move"],
                "location_id": "brain_studio",
                "cast_roles": [],
                "cameo_easter_egg": False,
                "transition_out": "daisy_chain_bridge",
                "brain_region": bs["brain_region"],
                "neural_state": bs["neural_state"],
                "scene": bs["scene"],
            }
            for extra_k in ("end_brain_region", "start_neural_state", "callout_mode"):
                if extra_k in bs:
                    entry[extra_k] = bs[extra_k]
            clips.append(entry)
            continue

        grammar = "expressive_vinyl_world"
        cam = "gentle_push_in"
        loc = f"ucsd_clinic_zone_{idx % 4}"
        trans = "daisy_chain_bridge"
        scene = "Patient sits across the bright clinic desk as gloved hands grip the chair and ink eyes narrow."
        if c_num == 1:
            grammar = "expressive_reaction_closeup"
            cam = "locked_tripod"
            loc = "ucsd_exam_chair"
        elif c_num == 2:
            grammar = "expressive_exterior_establishing"
            cam = "drone_aerial_approach"
            loc = "ucsd_campus_aerial"
            trans = "seamless_relay_cut"
            scene = "High FPV drone sweeps over sunlit coastal San Diego concrete campus plazas and eucalyptus trees."
        elif c_num == 3:
            grammar = "architectural_cutaway_portal"
            cam = "fpv_window_portal_breach"
            loc = "ucsd_clinic_cutaway"
            scene = "FPV drone breaches the tall glass clinic window as coastal sandstone wall slices open into the exam room."
        elif c_num in (5, 7, 9, 11, 16, 18, 23):
            grammar = "expressive_exterior_establishing"
            cam = "drone_high_orbit_drop" if c_num % 2 == 1 else "drone_skyline_pullback"
            loc = f"lajolla_walkway_{c_num}"
            scene = "Fast FPV drone arcs over sunlit coastal courtyard walkways as vinyl figures walk beneath palm shadows."
        elif c_num == 19:
            grammar = "expressive_cameo_world"
            cam = "locked_tripod"
            loc = "ucsd_phone_desk"
            scene = "Patient smiles holding the landline receiver while a tiny 4cm Mini-Cortex figurine nods once beside the cradle."

        clips.append(
            {
                "id": c_num,
                "clip_number": c_num,
                "sentence_index": s_idx,
                "act": min(6, (idx * 6) // 25 + 1),
                "visual_grammar": grammar,
                "grammar": grammar,
                "camera": cam,
                "camera_move": cam,
                "location_id": loc,
                "cast_roles": ["protagonist"],
                "cameo_easter_egg": c_num == 19,
                "transition_out": trans,
                "scene": scene,
            }
        )

    plan: dict[str, Any] = {
        "project_id": "v8_ep08_capgras_synth_test",
        "schema_version": 8,
        "production_profile": "shorts_expressive_v8",
        "style_profile": "expressive_25d_v8",
        "topic_focus": "neuroscience",
        "opening_mode": "paradox_question",
        "ending_mode": "mic_drop",
        "r72_mode": True,
        "r73_mode": True,
        "r74_mode": True,
        "core_reveal_sentence_index": 9,
        "zero_clip_reuse": True,
        "real_world_targets": [
            {"target_id": "ucsd_geisel_campus", "category": "institution", "query": "UC San Diego campus"},
            {"target_id": "la_jolla_street", "category": "urban_setting", "query": "La Jolla coastal street"},
            {"target_id": "gsr_polygraph_rig", "category": "scientific_apparatus", "query": "Galvanic skin response sensor"},
        ],
        "thumbnail": {
            "profile": "in_skull_cutaway_split_v4",
            "top_split_label": "SAME FACE",
            "bottom_split_label": "IMPOSTOR?!",
            "in_skull_split_prompt": (
                "Bright high-key 50/50 vertical split of the same expressive young man looking at his father, "
                "top half calm recognition with dormant cool-grey 3D glass brain cutaway, bottom half shocked recoil "
                "with fiery crimson-red severed 3D glass brain cutaway and bold red arrow."
            ),
            "cover_sentence_index": 1,
        },
        "clips": clips,
    }
    return plan, script_doc, lines


def test_r74b_axis5_topic_focus_validator_branching_and_ep07_regression() -> None:
    """R74-B enforces neuroscience 24-38% / >=45% / pathway+state rules while keeping Ep #7 psychology 100% green."""
    plan, script_doc, lines = _build_synthetic_r74b_neuro_plan_and_script()
    built = build_flow_prompts(plan, lines)

    issues_ok = validate_r74b_neuro_pathway_contract(plan, built, lines=lines, script_doc=script_doc)
    assert issues_ok == [], f"Valid neuroscience plan failed R74-B: {issues_ok}"
    v8_issues = validate_expressive_v8_prompts(built, plan=plan)
    assert [x for x in v8_issues if "xray_timing_v8" in x] == []
    pre_flow = verify_pre_flow_contract(plan, lines, built, script_doc=script_doc)
    r74b_pre = [x for x in pre_flow if "[r74b_" in x or "v8_brain_ban" in x]
    assert r74b_pre == [], f"Unexpected pre-flow R74-B / timing issues: {r74b_pre}"

    # 1. Early brain clip in 0-44% must fail on neuroscience
    early_plan = copy.deepcopy(plan)
    early_plan["clips"][4]["grammar"] = "expressive_xray_brain"
    early_plan["clips"][4]["visual_grammar"] = "expressive_xray_brain"
    early_plan["clips"][4]["camera_move"] = "neural_macro_orbit_hold"
    early_plan["clips"][4]["brain_region"] = "amygdala"
    early_plan["clips"][4]["neural_state"] = "active"
    early_issues = validate_r74b_neuro_pathway_contract(
        early_plan, build_flow_prompts(early_plan, lines), lines=lines, script_doc=script_doc
    )
    assert any("first brain clip" in x for x in early_issues), f"Expected early brain error, got: {early_issues}"

    # 2. Missing non-default neural_state must fail on neuroscience
    all_active_plan = copy.deepcopy(plan)
    for cl in all_active_plan["clips"]:
        if cl.get("grammar") == "expressive_xray_brain":
            cl["neural_state"] = "active"
    active_issues = validate_r74b_neuro_pathway_contract(
        all_active_plan, build_flow_prompts(all_active_plan, lines), lines=lines, script_doc=script_doc
    )
    assert any("non-default neural_state" in x for x in active_issues), f"Expected state error, got: {active_issues}"

    # 3. Psychology topic_focus must reject >26% brain ratio (28% > 26%)
    psych_over_plan = copy.deepcopy(plan)
    psych_over_plan["topic_focus"] = "psychology"
    psych_over_script = copy.deepcopy(script_doc)
    psych_over_script["topic_focus"] = "psychology"
    psych_over_issues = validate_r74b_neuro_pathway_contract(
        psych_over_plan, build_flow_prompts(psych_over_plan, lines), lines=lines, script_doc=psych_over_script
    )
    assert any("topic_focus='psychology' brain clip ratio" in x for x in psych_over_issues), (
        f"Expected psychology ratio error, got: {psych_over_issues}"
    )

    # 4. On-disk Ep #7 (`v8_ep07_harvard_reversible_choice_paradox`) regression check
    ep07_dir = cfg.PROJECTS_DIR / "v8_ep07_harvard_reversible_choice_paradox"
    if ep07_dir.exists():
        ep07_plan = json.loads((ep07_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
        ep07_script = json.loads((ep07_dir / "02_script" / "script.json").read_text(encoding="utf-8"))
        ep07_prompts = json.loads((ep07_dir / "03_visuals" / "flow_all_in_one_prompts.json").read_text(encoding="utf-8"))
        ep07_lines = list(ep07_script.get("lines") or [])
        ep07_r74b = validate_r74b_neuro_pathway_contract(
            ep07_plan, ep07_prompts.get("clips") or [], lines=ep07_lines, script_doc=ep07_script
        )
        assert ep07_r74b == [], f"Frozen Ep #7 failed R74-B check: {ep07_r74b}"
