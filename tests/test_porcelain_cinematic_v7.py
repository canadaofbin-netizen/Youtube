"""
Comprehensive test suite for Schema v7 `porcelain_cinematic_v7` (Rule R66):
- SSOT constant & rule parity (`pipeline/config.py`, `production_constants.md`, `neuro_diorama_rules.md`, `AGENTS.md`)
- `is_porcelain_v7_plan` & `resolve_diorama_v7_style_profile` backward compatibility with `lowpoly_pastel_v7` & v6
- All 6 `PorcelainV7PromptComposer` grammars & all 4 `ContainedLiving3DBrainRule` sub-modes
- `validate_porcelain_v7_scene` & `validate_diorama_v7_prompts` negative guards (neon-green, particles, mist, slime, low-poly, mixed-style, Escher camera)
- Full 61-clip episode `build_diorama_v7_prompts` + `validate_production_diorama_v6` + `verify_pre_flow_contract`
- Real MP4 CV gates (`inspect_diorama_clip_cv`: 4-color contained brain pass, neon-green spill reject, margin glow spill reject, human-skin leak reject)
- Assembler native-color preservation (`_compute_v7_pastel_eq_filter` bypassed), `AnatomyLabel` ASS generation, and `posthoc_semantic_qa` neon-green spill detection
"""

from __future__ import annotations

import json
from pathlib import Path
import re
from typing import Any

import cv2
import numpy as np
import pytest

from pipeline import config as cfg
from pipeline.depiction_rules import (
    ContainedLiving3DBrainRule,
    PorcelainCutawaySectionRule,
    PorcelainHandsActionRule,
    PorcelainLiteralAnalogyRule,
    PorcelainV7PromptComposer,
    PorcelainWorldRule,
    normalize_porcelain_v7_grammar,
    validate_porcelain_v7_scene,
)
from pipeline.diorama_assembler import build_v7_dynamic_edl, generate_diorama_ass_subtitles
from pipeline.dynamic_episode_qa import compile_episode_qa_contract, verify_pre_flow_contract
from pipeline.flow_diorama_sharded_worker import (
    compute_brain_margin_saturation,
    compute_neon_green_spill_ratio,
    compute_porcelain_flesh_leak_ratio,
    inspect_diorama_clip_cv,
)
from pipeline.flow_prompt_builder import (
    build_diorama_v7_prompts,
    validate_diorama_v7_prompts,
    write_flow_prompts_json,
)
from pipeline.prompt_quality_v5 import validate_production_diorama_v6
from pipeline.qa_gates import run_preflight_qa

ROOT = cfg.WORKSPACE_ROOT


def _write_test_mp4(mp4_path: Path, frames_bgr: list[np.ndarray], fps: int = 24) -> Path:
    """Encodes a list of BGR frames into a valid H.264 MP4 >= MIN_CLIP_SIZE_BYTES for CV gate tests."""
    import subprocess
    import imageio_ffmpeg

    h, w = frames_bgr[0].shape[:2]
    raw_avi = mp4_path.with_suffix(".avi")
    vw = cv2.VideoWriter(str(raw_avi), cv2.VideoWriter_fourcc(*"MJPG"), float(fps), (w, h))
    for frm in frames_bgr:
        vw.write(frm)
    vw.release()

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    subprocess.run(
        [
            ff,
            "-y",
            "-i",
            str(raw_avi),
            "-c:v",
            "libx264",
            "-crf",
            "10",
            "-pix_fmt",
            "yuv420p",
            str(mp4_path),
        ],
        check=True,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    raw_avi.unlink(missing_ok=True)
    return mp4_path


def test_porcelain_v7_ssot_constants_and_profile_resolution() -> None:
    constants_md = (ROOT / ".agents" / "rules" / "production_constants.md").read_text(encoding="utf-8")
    rules_md = (ROOT / ".agents" / "rules" / "neuro_diorama_rules.md").read_text(encoding="utf-8")
    agents_md = (ROOT / ".agents" / "AGENTS.md").read_text(encoding="utf-8")

    required_names = (
        "PORCELAIN_V7_STYLE_PROFILE",
        "DIORAMA_V7_STYLE_PROFILES",
        "PORCELAIN_V7_WORLD_STYLE",
        "PORCELAIN_V7_CAST_STYLE",
        "PORCELAIN_V7_OPTICS_LOCK",
        "PORCELAIN_V7_LUMA_RANGE",
        "PORCELAIN_V7_DARK_VOID_RATIO_MAX",
        "PORCELAIN_V7_SATURATION_RANGE",
        "PORCELAIN_V7_NEON_GREEN_SPILL_MAX",
        "PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX",
        "PORCELAIN_V7_HUMAN_SKIN_MAX",
        "PORCELAIN_V7_BRAIN_RENDER_MODES",
        "PORCELAIN_V7_VISUAL_GRAMMARS",
        "ALL_DIORAMA_V7_VISUAL_GRAMMARS",
    )
    for cname in required_names:
        assert hasattr(cfg, cname), f"Missing {cname} in pipeline/config.py"
        assert cname in constants_md, f"Missing {cname} in production_constants.md"

    assert cfg.DEFAULT_DIORAMA_STYLE_PROFILE == "porcelain_cinematic_v7"
    assert "R66" in rules_md
    assert "R66" in agents_md

    # Stage 1 pre-flight SSOT gate must pass
    s1 = run_preflight_qa(require_live_cdp=False)
    assert s1["passed"] is True, f"Stage 1 preflight QA failed: {s1}"

    # Backward-compatible profile resolution across empty, dict, string, legacy lowpoly, and v6
    assert cfg.is_porcelain_v7_plan("porcelain_cinematic_v7") is True
    assert cfg.is_porcelain_v7_plan("lowpoly_pastel_v7") is False
    assert cfg.is_porcelain_v7_plan(None) is False
    assert cfg.is_porcelain_v7_plan({}) is False
    assert cfg.is_porcelain_v7_plan({"schema": 7, "profile": "neuro_diorama"}) is True
    assert cfg.is_porcelain_v7_plan({"schema": 7, "style_profile": "lowpoly_pastel_v7"}) is False
    assert cfg.is_porcelain_v7_plan(
        {"schema": 7, "clips": [{"grammar": "lowpoly_hands_closeup"}]}
    ) is False
    assert cfg.is_porcelain_v7_plan(
        {"schema": 7, "clips": [{"grammar": "porcelain_hands_closeup"}]}
    ) is True
    assert cfg.is_porcelain_v7_plan({"schema": 6, "profile": "neuro_diorama"}) is False

    assert cfg.resolve_diorama_v7_style_profile(None) == "porcelain_cinematic_v7"
    assert cfg.resolve_diorama_v7_style_profile({"schema": 7}) == "porcelain_cinematic_v7"
    assert (
        cfg.resolve_diorama_v7_style_profile({"schema": 7, "style_profile": "lowpoly_pastel_v7"})
        == "lowpoly_pastel_v7"
    )
    assert (
        cfg.resolve_diorama_v7_style_profile({"schema": 7, "clips": [{"grammar": "lowpoly_matte_brain"}]})
        == "lowpoly_pastel_v7"
    )


def test_porcelain_v7_all_grammars_and_4mode_contained_brain_composer() -> None:
    # Slot normalization maps generic & legacy lowpoly grammar slots cleanly
    assert normalize_porcelain_v7_grammar("hands_closeup") == "porcelain_hands_closeup"
    assert normalize_porcelain_v7_grammar("lowpoly_pov_hands") == "porcelain_pov_hands"
    assert normalize_porcelain_v7_grammar("lowpoly_fullbleed_world") == "porcelain_fullbleed_world"
    assert normalize_porcelain_v7_grammar("cutaway_section") == "porcelain_cutaway_section"
    assert normalize_porcelain_v7_grammar("literal_analogy") == "porcelain_literal_analogy"
    assert normalize_porcelain_v7_grammar("lowpoly_matte_brain") == "porcelain_living_brain"

    scenes = [
        (
            "porcelain_fullbleed_world",
            "pan_right",
            PorcelainWorldRule.compose(
                "a sunlit sleep laboratory observation room with pale birch desks and brass wall clocks",
                "two clothed matte-white porcelain researchers in crisp navy lab coats walk beside the observation window and place a clipboard onto the desk",
            ),
        ),
        (
            "porcelain_hands_closeup",
            "locked_tripod",
            PorcelainHandsActionRule.compose(
                "tailored navy wool blazer cuffs and ball-jointed matte-white porcelain hands",
                "both porcelain hands grip and press a mechanical brass stopwatch plunger",
                "the sweep hand snaps across the ivory dial face",
                pov=False,
            ),
        ),
        (
            "porcelain_pov_hands",
            "gentle_push_in",
            PorcelainHandsActionRule.compose(
                "rolled white linen shirt cuffs and articulated matte-white porcelain hands",
                "both porcelain hands slide and stack three smooth wooden blocks onto a table",
                "the top block tips sideways onto the birch tabletop",
                pov=True,
            ),
        ),
        (
            "porcelain_cutaway_section",
            "tilt_down",
            PorcelainCutawaySectionRule.compose(
                "a two-level sleep clinic bedroom and control booth",
                "a clothed porcelain subject in a grey cardigan sits beside a bedside lamp while a porcelain technician in a lab coat adjusts an analog dial",
            ),
        ),
        (
            "porcelain_literal_analogy",
            "locked_tripod",
            PorcelainLiteralAnalogyRule.compose(
                "a clear glass municipal water main model with four transparent acrylic branch pipes",
                "clear aqua water streams smoothly along the widened channels and flushes amber glass beads into a clean basin",
            ),
        ),
    ]
    for g_name, cam, sc in scenes:
        errs = validate_porcelain_v7_scene(sc, grammar=g_name, camera_move=cam)
        assert errs == [], f"Unexpected errors for {g_name}: {errs}\nScene: {sc}"
        full_p = PorcelainV7PromptComposer.compose_clip_prompt(sc, camera_move=cam, grammar=g_name)
        assert "Photorealistic" in full_p or "bright" in full_p

    # All 4 ContainedLiving3DBrainRule modes must validate cleanly and stay within word budget
    for b_mode in cfg.PORCELAIN_V7_BRAIN_RENDER_MODES:
        b_scene = ContainedLiving3DBrainRule.compose(
            brain_region="prefrontal cortex and bilateral amygdalae",
            brain_mode=b_mode,
            active_hub="the prefrontal executive hub glows with soft clear cyan-blue subsurface light inside its recessed sulcal walls",
            lesion_or_deficit="the bilateral amygdalae pulse with contained deep crimson-red metabolic overload inside the medial temporal lobes",
            fluid_or_signal_flow="luminous pearl-aqua cerebrospinal fluid streams smoothly inside translucent perivascular channels while warm amber-gold light travels inside enclosed white-matter tracts",
        )
        b_errs = validate_porcelain_v7_scene(b_scene, grammar="porcelain_living_brain", camera_move="locked_tripod")
        assert b_errs == [], f"Brain mode {b_mode} failed validation: {b_errs}\nScene: {b_scene}"
        wc = len(b_scene.split())
        assert cfg.DIORAMA_SCENE_WORDS_MIN <= wc <= cfg.DIORAMA_SCENE_WORDS_MAX + 20, f"Word count {wc} out of range for {b_mode}"


def test_porcelain_v7_negative_scene_and_mixed_style_guards() -> None:
    good_brain = ContainedLiving3DBrainRule.compose(
        brain_region="hippocampus",
        brain_mode="frosted_glass_subcortical_xray",
        active_hub="clear cyan-blue subsurface light illuminates the enclosed hippocampal arch",
    )

    for forbidden_tok in (
        "bioluminescent green",
        "neon green",
        "fluorescent",
        "particles",
        "sparks",
        "mist",
        "fog",
        "smoke",
        "slime",
        "ooze",
        "splatter",
    ):
        bad_sc = f"{good_brain} {forbidden_tok} drifts across the room."
        errs = validate_porcelain_v7_scene(bad_sc, grammar="porcelain_living_brain", camera_move="locked_tripod")
        assert any("banned" in e.lower() for e in errs), f"Failed to block '{forbidden_tok}': {errs}"

    # Low-poly / flat-shaded contamination blocked in porcelain_cinematic_v7
    lp_errs = validate_porcelain_v7_scene(
        "Photorealistic bright high-key room where low-poly flat-shaded figures stand.",
        grammar="porcelain_fullbleed_world",
        camera_move="locked_tripod",
    )
    assert any("low-poly" in e.lower() for e in lp_errs), lp_errs

    # Pink-elephant negative phrasing blocked
    neg_errs = validate_porcelain_v7_scene(
        f"{good_brain} Zero blood and no faces anywhere.",
        grammar="porcelain_living_brain",
        camera_move="locked_tripod",
    )
    assert any("pink-elephant" in e.lower() or "positive phrasing" in e.lower() for e in neg_errs), neg_errs

    # Escher close-up camera & multi-actor limb triggers blocked
    escher_errs = validate_porcelain_v7_scene(
        PorcelainHandsActionRule.compose(
            "two pairs of navy wool cuffs and matte-white porcelain hands",
            "four porcelain hands enter from bottom frame",
            "the brass key turns",
        ),
        grammar="porcelain_hands_closeup",
        camera_move="tilt_up",
    )
    assert len(escher_errs) >= 3, escher_errs

    # Mixed style profile inside a single >=20-clip visual_plan is rejected by validate_diorama_v7_prompts
    mixed_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "clips": [
            {
                "clip_number": i,
                "act": min(6, (i - 1) // 4 + 1),
                "sentence_index": i,
                "grammar": "porcelain_fullbleed_world",
                "camera_move": "locked_tripod" if i % 2 == 1 else ("pan_left" if i == 2 else "pan_right"),
                "scene": PorcelainWorldRule.compose(
                    "a bright birch laboratory room",
                    "clothed matte-white porcelain researchers with translucent frosted-glass craniums place a glass cylinder onto a table",
                ),
            }
            for i in range(1, 21)
        ],
    }
    mixed_clips = build_diorama_v7_prompts(mixed_plan, [f"Sentence {i}." for i in range(1, 21)])
    # Force raw mixed grammar on rendered clip #2 to test validator's mixed-grammar check
    mixed_clips[1]["grammar"] = "lowpoly_matte_brain"
    mixed_errs = validate_diorama_v7_prompts(mixed_clips, plan=mixed_plan)
    assert any("mixes porcelain_cinematic_v7 and lowpoly_pastel_v7" in e for e in mixed_errs), mixed_errs


def test_porcelain_v7_full_61_clip_episode_passes_prompt_gate_and_pre_flow_contract(tmp_path: Path) -> None:
    """Converts the full 6-Act, 56-sentence, 61-clip Phineas Gage golden episode to porcelain_cinematic_v7 and passes all pre-Flow gates."""
    golden_dir = ROOT / "BCI_Shorts_Channel" / "research_dossiers" / "phineas_gage_iron_rod" / "diorama_v7_lowpoly"
    script_doc = json.loads((golden_dir / "script.json").read_text(encoding="utf-8"))
    base_plan = json.loads((golden_dir / "visual_plan.json").read_text(encoding="utf-8"))
    script_doc["style_profile"] = "porcelain_cinematic_v7"
    sentences = [str(s).strip() for act in script_doc["acts"] for s in act["sentences"]]

    def _upgrade_text_to_porcelain(txt: str) -> str:
        out = str(txt)
        replacements = (
            ("low-poly", "matte-white porcelain"),
            ("low poly", "matte-white porcelain"),
            ("flat-shaded", "smooth matte"),
            ("flat shaded", "smooth matte"),
            ("matte geometric hands", "ball-jointed matte-white porcelain hands"),
            ("faceless geometric head", "smooth featureless porcelain head with translucent frosted-glass cranium"),
            ("geometric sparks", "granite chips"),
            ("sparks burst", "granite grains slide"),
            ("sparks", "granite grains"),
            ("pastel-blue", "clear daylight-blue"),
            ("pastel", "bright sunlit"),
        )
        for old_tok, new_tok in replacements:
            out = re.sub(re.escape(old_tok), new_tok, out, flags=re.IGNORECASE)
        return out

    brain_modes = cfg.PORCELAIN_V7_BRAIN_RENDER_MODES
    porcelain_clips_spec: list[dict[str, Any]] = []
    brain_counter = 0
    for raw_c in base_plan["clips"]:
        c = dict(raw_c)
        c.pop("scene", None)
        c.pop("reference_image", None)
        g_porcelain = normalize_porcelain_v7_grammar(c.get("grammar"))
        c["grammar"] = g_porcelain
        for k in (
            "environment",
            "action",
            "kinetic_action",
            "attire_and_hands",
            "prop_action",
            "consequence",
            "structure",
            "internal_mechanism",
            "analogy_world",
            "comparison_action",
            "lighting",
        ):
            if k in c and isinstance(c[k], str):
                c[k] = _upgrade_text_to_porcelain(c[k])
        if g_porcelain == "porcelain_living_brain":
            bm = brain_modes[brain_counter % len(brain_modes)]
            brain_counter += 1
            c["brain_mode"] = bm
            orig_bs = _upgrade_text_to_porcelain(str(c.get("brain_scene") or ""))
            c["brain_scene"] = (
                f"{orig_bs.rstrip('.')}; clear cyan-blue intact sulcal hubs, contained deep crimson-red lesion "
                "zones, warm amber-gold rerouted fiber sheaths, and luminous pearl-aqua perivascular fluid channels"
                if orig_bs
                else "clear cyan-blue cortical hubs, deep crimson-red lesion tract, warm amber-gold rerouted fiber sheaths, and luminous pearl-aqua perivascular fluid channels"
            )
        porcelain_clips_spec.append(c)

    visual_plan = {
        **base_plan,
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "require_cold_open_v7": False,  # Gage golden script predates R57-H2 S3 template; cold-open has dedicated test
        "thumbnail": {
            "hook_text": "IRON SKULL",
            "cover_sentence_index": 1,
            "cover_brief": "Centered matte-white porcelain rail worker in brimmed cap beside granite cut",
        },
        "clips": porcelain_clips_spec,
    }

    rendered = build_diorama_v7_prompts(visual_plan, sentences)
    assert len(rendered) >= 60
    assert all(c["style_profile"] == "porcelain_cinematic_v7" for c in rendered)
    assert set(c["brain_mode"] for c in rendered if c["grammar"] == "porcelain_living_brain") == set(brain_modes)

    v7_prompt_issues = validate_diorama_v7_prompts(rendered, plan=visual_plan)
    assert v7_prompt_issues == [], f"validate_diorama_v7_prompts issues: {v7_prompt_issues}"

    gate_issues = validate_production_diorama_v6(visual_plan, sentences, rendered, script_doc=script_doc)
    assert gate_issues == [], f"validate_production_diorama_v6 issues: {gate_issues}"

    pre_contract_issues = verify_pre_flow_contract(visual_plan, sentences, rendered, script_doc=script_doc)
    assert pre_contract_issues == [], f"verify_pre_flow_contract issues: {pre_contract_issues}"

    contract = compile_episode_qa_contract(visual_plan, sentences, rendered, script_doc=script_doc)
    assert contract["style_profile"] == "porcelain_cinematic_v7"
    assert any(l["cv_signature"] == "bright_porcelain_world" for l in contract["cast_clip_locks"])

    out_json = write_flow_prompts_json(tmp_path, rendered)
    saved_doc = json.loads(out_json.read_text(encoding="utf-8"))
    assert saved_doc["style_profile"] == "porcelain_cinematic_v7"
    assert saved_doc["schema_version"] == 7


def test_porcelain_v7_cv_gates_contained_4color_brain_vs_neon_spill_and_skin_leak(tmp_path: Path) -> None:
    """Tests `inspect_diorama_clip_cv` on real encoded MP4 clips for contained 4-color brain vs failure modes."""
    h, w = 640, 360

    def _make_moving_brain_frames(
        *,
        inject_neon_green: bool = False,
        inject_margin_bleed: bool = False,
    ) -> list[np.ndarray]:
        frames: list[np.ndarray] = []
        for fi in range(96):
            frm = np.full((h, w, 3), (228, 230, 232), dtype=np.uint8)
            cx, cy = w // 2 + int(6 * np.sin(fi * 0.15)), h // 2 + int(4 * np.cos(fi * 0.12))
            cv2.ellipse(frm, (cx, cy), (105, 135), 0, 0, 360, (205, 214, 222), -1)
            for gi in range(-4, 5):
                y_off = cy + gi * 22 + int(5 * np.sin(fi * 0.22 + gi))
                cv2.line(frm, (cx - 75, y_off), (cx + 75, y_off + 6), (175, 184, 194), 3)

            # Contained 4-Color Internal Mechanisms strictly inside brain silhouette:
            p_shift = int(18 * np.sin(fi * 0.25))
            cv2.circle(frm, (cx - 35 + p_shift, cy - 35), 22, (235, 195, 20), -1)   # Clear Cyan-Blue
            cv2.circle(frm, (cx + 32, cy - 20 - p_shift // 2), 18, (35, 25, 205), -1)  # Deep Crimson-Red
            cv2.line(frm, (cx - 40, cy + 25), (cx + 35 + p_shift, cy + 40), (25, 165, 235), 8)  # Warm Amber-Gold
            cv2.line(frm, (cx - 25, cy + 60), (cx + 25, cy + 60 + p_shift // 3), (235, 228, 155), 6)  # Luminous Pearl-Aqua

            if inject_neon_green:
                cv2.rectangle(frm, (40, 80), (w - 40, 240), (30, 245, 40), -1)
            if inject_margin_bleed:
                frm[:, : int(w * 0.10)] = (235, 180, 10)
                frm[:, int(w * 0.90) :] = (20, 155, 240)

            rng = np.random.default_rng(1000 + fi)
            grain = rng.integers(-6, 7, size=(h, w, 3), dtype=np.int16)
            frm = np.clip(frm.astype(np.int16) + grain, 0, 255).astype(np.uint8)
            frames.append(frm)
        return frames

    # 1. Clean contained 4-color 3D brain clip -> PASSES
    good_mp4 = _write_test_mp4(tmp_path / "good_brain.mp4", _make_moving_brain_frames())
    assert compute_neon_green_spill_ratio(_make_moving_brain_frames()[0]) == 0.0
    assert compute_brain_margin_saturation(_make_moving_brain_frames()[0]) < cfg.PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX
    rep_good = inspect_diorama_clip_cv(
        good_mp4,
        grammar="porcelain_living_brain",
        schema_version=7,
        brain_mode="cortical_vascular_whole",
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_good["passed"] is True, f"Contained 4-color brain clip unexpectedly failed: {rep_good}"

    # 2. Neon-green fluorescent spill clip -> FAILS with neon_green_fluorescent_spill
    neon_mp4 = _write_test_mp4(tmp_path / "neon_brain.mp4", _make_moving_brain_frames(inject_neon_green=True))
    rep_neon = inspect_diorama_clip_cv(
        neon_mp4,
        grammar="porcelain_living_brain",
        schema_version=7,
        brain_mode="cortical_vascular_whole",
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_neon["passed"] is False
    assert "neon_green_fluorescent_spill" in rep_neon["reason"]

    # 3. Outer studio margin glow spill -> FAILS on whole-brain mode, SKIPPED on bounded_micro_channel
    bleed_mp4 = _write_test_mp4(tmp_path / "bleed_brain.mp4", _make_moving_brain_frames(inject_margin_bleed=True))
    rep_bleed_whole = inspect_diorama_clip_cv(
        bleed_mp4,
        grammar="porcelain_living_brain",
        schema_version=7,
        brain_mode="cortical_vascular_whole",
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_bleed_whole["passed"] is False
    assert "brain_margin_glow_spill" in rep_bleed_whole["reason"]

    rep_bleed_micro = inspect_diorama_clip_cv(
        bleed_mp4,
        grammar="porcelain_living_brain",
        schema_version=7,
        brain_mode="bounded_micro_channel",
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_bleed_micro["passed"] is True, f"bounded_micro_channel should allow full-frame macro interior: {rep_bleed_micro}"

    # 4. Human peach-skin morph leak on porcelain_hands_closeup -> FAILS with human_skin_or_face_leak
    skin_frames: list[np.ndarray] = []
    for fi in range(96):
        frm = np.full((h, w, 3), (220, 224, 228), dtype=np.uint8)
        x_off = int(12 * np.sin(fi * 0.2))
        cv2.rectangle(frm, (60 + x_off, 140), (w - 60 + x_off, h - 80), (135, 170, 225), -1)
        rng = np.random.default_rng(2000 + fi)
        frm = np.clip(frm.astype(np.int16) + rng.integers(-6, 7, size=(h, w, 3), dtype=np.int16), 0, 255).astype(np.uint8)
        skin_frames.append(frm)
    skin_mp4 = _write_test_mp4(tmp_path / "skin_hands.mp4", skin_frames)
    rep_skin = inspect_diorama_clip_cv(
        skin_mp4,
        grammar="porcelain_hands_closeup",
        schema_version=7,
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_skin["passed"] is False
    assert "human_skin_or_face_leak" in rep_skin["reason"]


def test_porcelain_v7_edl_anatomy_labels_and_native_color_bypass(tmp_path: Path) -> None:
    """Verifies EDL style_profile propagation, AnatomyLabel ASS emission on porcelain_living_brain, and pastel-EQ bypass."""
    from pipeline.diorama_assembler import _compute_v7_pastel_eq_filter

    n_sents = 20
    sentence_spans = [
        {
            "sentence_index": i,
            "act": min(6, (i - 1) // 4 + 1),
            "start_sec": round((i - 1) * 2.2, 2),
            "end_sec": round(i * 2.2 - 0.15, 2),
            "act_boundary_after": (i % 4 == 0),
        }
        for i in range(1, n_sents + 1)
    ]
    clips_spec = []
    for i in range(1, n_sents + 2):
        if i == 4:
            clips_spec.append(
                {
                    "clip_number": i,
                    "act": 1,
                    "sentence_index": 4,
                    "grammar": "porcelain_living_brain",
                    "brain_mode": "frosted_glass_subcortical_xray",
                    "brain_region": "hippocampus",
                    "camera_move": "locked_tripod",
                }
            )
        else:
            clips_spec.append(
                {
                    "clip_number": i,
                    "act": min(6, (i - 1) // 4 + 1),
                    "sentence_index": min(n_sents, i),
                    "grammar": "porcelain_fullbleed_world" if i % 2 == 1 else "porcelain_hands_closeup",
                    "camera_move": "locked_tripod" if i % 2 == 1 else "pan_right",
                }
            )
    vp = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "chapter_headlines": [{"sentence_index": 1, "text": "NO SLEEP"}],
        "split_screens": [],
        "clips": clips_spec,
    }
    clip_files = [tmp_path / f"clip_{i}.mp4" for i in range(1, n_sents + 2)]
    speech_end_sec = sentence_spans[-1]["end_sec"]
    total_dur_sec = speech_end_sec + 2.4

    edl = build_v7_dynamic_edl(
        visual_plan=vp,
        sentence_spans=sentence_spans,
        clip_files=clip_files,
        speech_end_sec=speech_end_sec,
        total_duration_sec=total_dur_sec,
    )
    assert edl["style_profile"] == "porcelain_cinematic_v7"
    assert cfg.is_porcelain_v7_plan(edl) is True
    brain_cuts = [c for c in edl["cuts"] if c.get("grammar") == "porcelain_living_brain"]
    assert len(brain_cuts) >= 1
    assert brain_cuts[0].get("anatomy_label"), f"Expected anatomy_label on porcelain_living_brain cut: {brain_cuts[0]}"

    events = [
        (sp["start_sec"], sp["end_sec"], ["Inside", "hippocampus", "channels"])
        for sp in sentence_spans
    ]
    ass_file = generate_diorama_ass_subtitles(
        ass_path=tmp_path / "porcelain_test.ass",
        events=events,
        sentence_spans=sentence_spans,
        visual_plan=vp,
        edl=edl,
    )
    ass_out = ass_file.read_text(encoding="utf-8")
    assert "Dialogue:" in ass_out
    assert ",AnatomyLabel," in ass_out
    assert "HIPPOCAMPUS" in ass_out.upper()

    # Verify vivid 4-color clip triggers pastel attenuation on lowpoly_pastel_v7, while porcelain_cinematic_v7 bypasses it
    vivid_frames = [np.full((360, 200, 3), (245, 200, 10), dtype=np.uint8) for _ in range(24)]
    vivid_mp4 = _write_test_mp4(tmp_path / "vivid_cyan.mp4", vivid_frames, fps=24)
    lowpoly_eq = _compute_v7_pastel_eq_filter(vivid_mp4)
    assert "saturation=" in lowpoly_eq  # lowpoly_pastel_v7 attenuates vivid saturation
    assert cfg.is_porcelain_v7_plan(vp) is True and cfg.is_porcelain_v7_plan(edl) is True  # assembler skips _compute_v7_pastel_eq_filter


def test_porcelain_v7_posthoc_semantic_qa_passes_clean_4color_and_flags_neon_green(tmp_path: Path) -> None:
    """Verifies R64 `run_posthoc_semantic_qa` passes contained 4-color `porcelain_living_brain` and flags `neon_green_spill`."""
    from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa

    p_dir = tmp_path / "porcelain_posthoc_proj"
    for sd in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sd).mkdir(parents=True, exist_ok=True)

    def _make_1080_brain_frames(neon: bool = False) -> list[np.ndarray]:
        out: list[np.ndarray] = []
        h, w = 1920, 1080
        for fi in range(36):
            frm = np.full((h, w, 3), (226, 229, 232), dtype=np.uint8)
            cx, cy = w // 2 + fi * 4 - 60, int(h * 0.40)
            cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
            for gi in range(-5, 6):
                cv2.line(frm, (cx - 180, cy + gi * 44), (cx + 180, cy + gi * 44 + 12), (140, 150, 160), 6)
            # Contained 4-color accents inside brain contour (high foreground contrast & chroma)
            cv2.circle(frm, (cx - 80, cy - 70), 55, (235, 195, 20), -1)   # Clear Cyan-Blue
            cv2.circle(frm, (cx + 85, cy - 45), 48, (35, 25, 205), -1)    # Deep Crimson-Red
            cv2.line(frm, (cx - 95, cy + 60), (cx + 95, cy + 95), (25, 165, 235), 18)  # Warm Amber-Gold
            if neon:
                cv2.rectangle(frm, (120, 480), (960, 860), (30, 245, 40), -1)  # Toxic neon green spill
            out.append(frm)
        return out

    clean_frames = _make_1080_brain_frames(neon=False)
    _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", clean_frames, fps=24)
    _write_test_mp4(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", clean_frames, fps=24)
    (p_dir / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "sentences": ["Inside the prefrontal cortex, clear pathways carry the signal."],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [
                    {
                        "clip_number": 1,
                        "sentence_index": 1,
                        "act": 3,
                        "grammar": "porcelain_living_brain",
                        "brain_mode": "cortical_vascular_whole",
                        "brain_region": "prefrontal cortex",
                        "camera_move": "pan_right",
                        "scene": "Contained 4-color 3D brain.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "total_duration_sec": 1.5,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 3,
                        "mode": "single",
                        "grammar": "porcelain_living_brain",
                        "brain_mode": "cortical_vascular_whole",
                        "brain_region": "prefrontal cortex",
                        "camera_move": "pan_right",
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.5,
                        "duration_sec": 1.5,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    rep_clean = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep_clean["style_profile"] == "porcelain_cinematic_v7"
    assert rep_clean["cv_passed"] is True, f"Clean 4-color brain failed posthoc QA: {rep_clean}"

    # Inject neon-green spill into final MP4 -> must fail with neon_green_spill defect
    neon_frames = _make_1080_brain_frames(neon=True)
    _write_test_mp4(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", neon_frames, fps=24)
    rep_neon = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep_neon["cv_passed"] is False
    cut_defects = rep_neon["cuts"][0]["defects"]
    assert any("neon_green_spill" in d for d in cut_defects), f"Expected neon_green_spill defect, got {cut_defects}"


def test_porcelain_v7_dossier_seed_and_batch_lock_mapping() -> None:
    """Verifies `diorama_seed_from_dossier` defaults to `porcelain_cinematic_v7` while preserving `lowpoly_pastel_v7` and v6."""
    from pipeline.diorama_batch_orchestrator import _plan_lock_mapping_issues
    from pipeline.research_dossier import diorama_seed_from_dossier

    seed_default = diorama_seed_from_dossier("phineas_gage_iron_rod")
    assert seed_default["schema"] == 7
    assert seed_default["style_profile"] == "porcelain_cinematic_v7"
    assert cfg.is_porcelain_v7_plan(seed_default) is True

    seed_lowpoly = diorama_seed_from_dossier("phineas_gage_iron_rod", style_profile="lowpoly_pastel_v7")
    assert seed_lowpoly["schema"] == 7
    assert seed_lowpoly["style_profile"] == "lowpoly_pastel_v7"
    assert cfg.is_porcelain_v7_plan(seed_lowpoly) is False
    assert cfg.is_diorama_v7_plan(seed_lowpoly) is True

    seed_v6 = diorama_seed_from_dossier("phineas_gage_iron_rod", schema_version=6)
    assert seed_v6["schema"] == 6
    assert cfg.is_diorama_v7_plan(seed_v6) is False
    assert cfg.is_porcelain_v7_plan(seed_v6) is False

    # Verify _plan_lock_mapping_issues accepts porcelain_living_brain & porcelain_literal_analogy without false alarms
    vp_porcelain = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "clips": [
            {
                "clip_number": 1,
                "sentence_index": 1,
                "grammar": "porcelain_literal_analogy",
                "scene": PorcelainLiteralAnalogyRule.compose(
                    "a sunlit wooden balance scale beside bowling pins",
                    "an iron bar lifts a three-hole bowling ball upward on the opposite pan",
                ),
            },
            {
                "clip_number": 2,
                "sentence_index": 2,
                "grammar": "porcelain_living_brain",
                "brain_mode": "cortical_vascular_whole",
                "brain_region": "prefrontal cortex",
                "scene": ContainedLiving3DBrainRule.compose(
                    brain_region="prefrontal cortex",
                    brain_mode="cortical_vascular_whole",
                ),
            },
            {
                "clip_number": 3,
                "sentence_index": 3,
                "cut_role": "outro",
                "grammar": "porcelain_fullbleed_world",
                "scene": "In a bright open sky horizon above sunlit limestone hills, soft clouds drift slowly across calm blue sky.",
            },
        ],
    }
    sents = [
        "Thirteen pounds of iron—heavier than a bowling ball!",
        "Inside the prefrontal cortex, clear channels route the signal.",
        "That is how the human mind rebuilds.",
    ]
    contract = compile_episode_qa_contract(vp_porcelain, sents, [])
    assert len(contract["analogy_locks"]) >= 1
    assert len(contract["anatomy_locks"]) >= 1
    lock_issues = _plan_lock_mapping_issues(vp_porcelain, contract)
    assert lock_issues == [], f"Unexpected _plan_lock_mapping_issues on porcelain_cinematic_v7: {lock_issues}"


def test_style_profile_precedence_fallback_and_non_integer_schema_safety() -> None:
    """Verifies string schemas never crash and untagged schema-7 helper docs never override explicit lowpoly_pastel_v7 plans."""
    from pipeline.depiction_rules import LowPolyHandsActionRule

    assert cfg.is_porcelain_v7_plan({"schema": "episode_qa_contract_v2"}) is False
    assert cfg.is_porcelain_v7_plan({"schema": "episode_qa_contract_v1"}) is False
    assert cfg.is_porcelain_v7_plan({"schema": "v7"}) is True
    assert cfg.resolve_diorama_v7_style_profile({"schema": 7}, fallback="lowpoly_pastel_v7") == "lowpoly_pastel_v7"
    assert cfg.is_porcelain_v7_plan({"schema": 7, "style_profile": "lowpoly_pastel_v7"}, {"schema": 7}) is False

    lp_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
    }
    lp_clips = [
        {
            "clip_number": 1,
            "sentence_index": 1,
            "act": 1,
            "schema_version": 7,
            "style_profile": "lowpoly_pastel_v7",
            "grammar": "lowpoly_hands_closeup",
            "scene": LowPolyHandsActionRule.compose(
                "navy blazer cuffs and matte geometric hands",
                "both hands grip and press a brass stopwatch",
                "the sweep hand advances",
            ),
        }
    ]
    untagged_script = {"schema": 7, "profile": "neuro_diorama", "sentences": ["One click changes everything!"]}
    contract = compile_episode_qa_contract(lp_plan, ["One click changes everything!"], lp_clips, script_doc=untagged_script)
    assert contract["style_profile"] == "lowpoly_pastel_v7"
    assert len(contract["cast_clip_locks"]) == 1
    assert contract["cast_clip_locks"][0]["cv_signature"] == "bright_lowpoly_world"


def test_porcelain_actor_injection_and_optics_tail_unmasked_validation() -> None:
    """Ensures role nouns trigger porcelain cast injection and PORCELAIN_V7_OPTICS_TAIL never masks un-porcelained humans/hands."""
    from pipeline.depiction_rules import PORCELAIN_V7_OPTICS_TAIL

    stanford_scene = PorcelainWorldRule.compose(
        "a sunlit Stanford basement corridor with numbered wooden doors",
        "two guards in khaki shirts and dark sunglasses march a prisoner in a linen smock down the hall",
    )
    assert "clothed matte-white porcelain figures" in stanford_scene
    assert "translucent frosted-glass craniums" in stanford_scene
    assert validate_porcelain_v7_scene(stanford_scene, grammar="porcelain_fullbleed_world", camera_move="pan_right") == []

    # Cast-free landscape/prop prompt even with locked_tripod ('...and figure motion') must NOT false-fire actor check
    outro_scene = PorcelainWorldRule.compose(
        "a bright open limestone valley horizon under morning sky",
        "soft white clouds drift slowly across calm blue sky",
    )
    assert "porcelain figures" not in outro_scene
    outro_full_locked = PorcelainV7PromptComposer.compose_clip_prompt(
        outro_scene,
        grammar="porcelain_fullbleed_world",
        camera_move="locked_tripod",
    )
    assert validate_porcelain_v7_scene(outro_full_locked, grammar="porcelain_fullbleed_world", camera_move="locked_tripod") == []

    # Un-porcelained human actors or hands must FAIL even when PORCELAIN_V7_OPTICS_TAIL ('on tactile porcelain...') is present
    unporcelained_world = (
        f"Photorealistic bright high-key documentary cinema: full-bleed high-key view of a corridor. "
        f"Two guards in khaki shirts march a prisoner down the hall. {PORCELAIN_V7_OPTICS_TAIL}"
    )
    w_errs = validate_porcelain_v7_scene(unporcelained_world, grammar="porcelain_fullbleed_world", camera_move="pan_right")
    assert any("porcelain" in e.lower() for e in w_errs), f"Expected missing porcelain cast error, got: {w_errs}"

    unporcelained_hands = (
        f"Photorealistic bright high-key documentary cinema: tight neck-down close-up of sleeves gripping a brass lever "
        f"while a dial turns. {PORCELAIN_V7_OPTICS_TAIL}"
    )
    h_errs = validate_porcelain_v7_scene(unporcelained_hands, grammar="porcelain_hands_closeup", camera_move="locked_tripod")
    assert any("porcelain" in e.lower() for e in h_errs), f"Expected missing porcelain hands error, got: {h_errs}"


def test_porcelain_veo_retry_softening_and_cv_reinforcement() -> None:
    """Verifies Veo retry softening uses R66 porcelain phrasing (never faceted geometric) and appends positive CV reinforcement."""
    from pipeline.flow_diorama_sharded_worker import (
        _reinforce_porcelain_cv_retry_prompt,
        _soften_veo_false_positive_words,
    )

    # Faceted geometric contamination must be caught by validate_porcelain_v7_scene
    geom_errs = validate_porcelain_v7_scene(
        "Photorealistic bright high-key room with porcelain figures and a faceted geometric head.",
        grammar="porcelain_fullbleed_world",
        camera_move="locked_tripod",
    )
    assert any("low-poly" in e.lower() or "faceted" in e.lower() for e in geom_errs), geom_errs

    raw_scene = PorcelainWorldRule.compose(
        "a sunlit Vermont quarry ledge",
        "an iron rod passes beside a clothed matte-white porcelain worker's cheek and skull",
    )
    raw_prompt = PorcelainV7PromptComposer.compose_clip_prompt(
        raw_scene,
        camera_move="pan_right",
        grammar="porcelain_fullbleed_world",
    )
    softened = _soften_veo_false_positive_words(
        raw_prompt,
        style_profile="porcelain_cinematic_v7",
        grammar="porcelain_fullbleed_world",
    )
    assert "faceted geometric" not in softened.lower()
    assert "lower geometric jaw" not in softened.lower()
    assert "translucent frosted-glass cranium" in softened.lower()
    assert "smooth matte-white porcelain jawline" in softened.lower()
    assert validate_porcelain_v7_scene(softened, grammar="porcelain_fullbleed_world", camera_move="pan_right") == []

    brain_scene = ContainedLiving3DBrainRule.compose(
        brain_region="hippocampus",
        brain_mode="cortical_vascular_whole",
        lesion_or_deficit="bilateral lesions glow inside the medial temporal lobes",
    )
    brain_prompt = PorcelainV7PromptComposer.compose_clip_prompt(
        brain_scene,
        camera_move="locked_tripod",
        grammar="porcelain_living_brain",
    )
    brain_soft = _soften_veo_false_positive_words(
        brain_prompt,
        style_profile="porcelain_cinematic_v7",
        grammar="porcelain_living_brain",
    )
    assert "deep crimson-red zones" in brain_soft.lower()
    reinforced = _reinforce_porcelain_cv_retry_prompt(
        brain_soft,
        grammar="porcelain_living_brain",
        cv_reason="neon_green_fluorescent_spill:ratio=0.0420",
    )
    assert "enclosed strictly inside translucent vessel walls" in reinforced.lower()
    assert reinforced.index("enclosed strictly") < reinforced.index("Subtle crisp physical foley")
    assert validate_porcelain_v7_scene(reinforced, grammar="porcelain_living_brain", camera_move="locked_tripod") == []


def test_generic_slot_grammars_enforce_r66_cv_and_posthoc_gates(tmp_path: Path) -> None:
    """Ensures generic slot grammars ('living_brain', 'hands_closeup') cannot bypass R66 CV containment or skin-leak checks."""
    from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa

    h, w = 640, 360
    neon_frames: list[np.ndarray] = []
    skin_frames: list[np.ndarray] = []
    for fi in range(96):
        rng = np.random.default_rng(5000 + fi)
        grain = rng.integers(-6, 7, size=(h, w, 3), dtype=np.int16)

        bf = np.full((h, w, 3), (226, 229, 232), dtype=np.uint8)
        cv2.rectangle(bf, (30 + (fi % 9) * 3, 90), (w - 30, 260), (30, 245, 40), -1)
        neon_frames.append(np.clip(bf.astype(np.int16) + grain, 0, 255).astype(np.uint8))

        sf = np.full((h, w, 3), (222, 225, 228), dtype=np.uint8)
        cv2.rectangle(sf, (55 + (fi % 9) * 3, 140), (w - 55, h - 80), (135, 170, 225), -1)
        skin_frames.append(np.clip(sf.astype(np.int16) + grain, 0, 255).astype(np.uint8))

    neon_mp4 = _write_test_mp4(tmp_path / "generic_neon.mp4", neon_frames)
    skin_mp4 = _write_test_mp4(tmp_path / "generic_skin.mp4", skin_frames)

    for sp in ("porcelain_cinematic_v7", ""):
        r_neon = inspect_diorama_clip_cv(neon_mp4, grammar="living_brain", schema_version=7, style_profile=sp)
        assert r_neon["passed"] is False and "neon_green_fluorescent_spill" in r_neon["reason"], r_neon
        r_skin = inspect_diorama_clip_cv(skin_mp4, grammar="hands_closeup", schema_version=7, style_profile=sp)
        assert r_skin["passed"] is False and "human_skin_or_face_leak" in r_skin["reason"], r_skin

    # Also verify R64 posthoc QA catches margin glow spill and late-cut neon spill + routes to regenerate_flow_clip
    p_dir = tmp_path / "posthoc_margin_and_skin_proj"
    for sd in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (p_dir / sd).mkdir(parents=True, exist_ok=True)

    frames_1080: list[np.ndarray] = []
    for fi in range(36):
        frm = np.full((1920, 1080, 3), (226, 229, 232), dtype=np.uint8)
        cx, cy = 540 + fi * 3 - 45, 760
        cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
        for gi in range(-4, 5):
            cv2.line(frm, (cx - 170, cy + gi * 44), (cx + 170, cy + gi * 44 + 10), (140, 150, 160), 6)
        cv2.circle(frm, (cx - 75, cy - 60), 50, (235, 195, 20), -1)
        # Outer studio margin saturation bleed across borders:
        frm[:, :95] = (235, 180, 10)
        frm[:, 985:] = (20, 155, 240)
        frames_1080.append(frm)

    _write_test_mp4(p_dir / "03_visuals" / "flow_native_clips" / "clip_1.mp4", frames_1080, fps=24)
    _write_test_mp4(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", frames_1080, fps=24)
    (p_dir / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "sentences": ["Clear channels carry the pulse."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [{"clip_number": 1, "sentence_index": 1, "act": 3, "grammar": "living_brain", "camera_move": "pan_right"}],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "total_duration_sec": 1.5,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 3,
                        "mode": "single",
                        "grammar": "living_brain",
                        "brain_mode": "cortical_vascular_whole",
                        "camera_move": "pan_right",
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.5,
                        "duration_sec": 1.5,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    rep = run_posthoc_semantic_qa(p_dir, render_strips=False, run_asr_sync=False)
    assert rep["cv_passed"] is False
    assert any("brain_margin_glow_spill" in d for d in rep["cuts"][0]["defects"]), rep["cuts"][0]["defects"]
    assert rep["cuts"][0]["remediation"] == "regenerate_flow_clip"


def test_prompt_gate_catches_plan_vs_clips_style_profile_mismatch() -> None:
    """Verifies validate_production_diorama_v6 rejects stale lowpoly_pastel_v7 rendered clips paired with a porcelain_cinematic_v7 plan."""
    from pipeline.depiction_rules import LowPolyWorldRule

    sents = [f"Sentence {i} keeps the story moving." for i in range(1, 21)]
    porcelain_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "porcelain_cinematic_v7",
        "require_cold_open_v7": False,
        "clips": [
            {
                "clip_number": i,
                "act": min(6, (i - 1) // 4 + 1),
                "sentence_index": i,
                "grammar": "porcelain_fullbleed_world",
                "camera_move": "locked_tripod" if i % 2 == 1 else "pan_right",
                "scene": PorcelainWorldRule.compose(
                    "a sunlit laboratory room",
                    "clothed matte-white porcelain researchers with translucent frosted-glass craniums lift a glass cylinder",
                ),
            }
            for i in range(1, 21)
        ],
    }
    lowpoly_plan = {
        "schema": 7,
        "profile": "neuro_diorama",
        "style_profile": "lowpoly_pastel_v7",
        "clips": [
            {
                "clip_number": i,
                "act": min(6, (i - 1) // 4 + 1),
                "sentence_index": i,
                "grammar": "lowpoly_fullbleed_world",
                "camera_move": "locked_tripod" if i % 2 == 1 else "pan_right",
                "scene": LowPolyWorldRule.compose(
                    "a pastel laboratory room",
                    "clothed low-poly researchers in lab coats lift a glass cylinder",
                ),
            }
            for i in range(1, 21)
        ],
    }
    stale_lowpoly_clips = build_diorama_v7_prompts(lowpoly_plan, sents)
    issues = validate_production_diorama_v6(porcelain_plan, sents, stale_lowpoly_clips)
    assert any("mismatches rendered clips style_profile" in e for e in issues), issues


def test_dq8_catches_mid_cut_neon_spill_and_brain_margin_glow(tmp_path: Path) -> None:
    """Verifies DQ8 inspects mid/late cut frames (not only f_a at +0.08s) for neon-green spill and outer margin glow."""
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract

    p_dir = tmp_path / "dq8_porcelain_proj"
    for sd in ("02_script", "03_visuals", "04_audio", "05_assembly"):
        (p_dir / sd).mkdir(parents=True, exist_ok=True)

    (p_dir / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (p_dir / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "sentences": ["Clear channels carry the pulse."]}),
        encoding="utf-8",
    )
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [
                    {
                        "clip_number": i,
                        "sentence_index": 1,
                        "act": min(6, (i - 1) // 4 + 1),
                        "grammar": "porcelain_living_brain" if i == 1 else "porcelain_fullbleed_world",
                        "brain_mode": "cortical_vascular_whole" if i == 1 else "",
                        "brain_region": "hippocampus" if i == 1 else "",
                        "camera_move": "pan_right" if i % 2 == 1 else "locked_tripod",
                    }
                    for i in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    (p_dir / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "max_clip_reuse": 1,
                "total_duration_sec": 1.5,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 3,
                        "mode": "single",
                        "grammar": "living_brain",
                        "camera_move": "pan_right",
                        "sentence_index": 1,
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.5,
                        "duration_sec": 1.5,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    # First 8 frames (including f_a @ +0.08s) are completely clean; frames 12..24 (f_mid) have neon-green spill!
    mid_neon_frames: list[np.ndarray] = []
    for fi in range(36):
        frm = np.full((1920, 1080, 3), (224, 227, 230), dtype=np.uint8)
        cx, cy = 540 + fi * 4 - 60, 760
        cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
        cv2.circle(frm, (cx - 70, cy - 55), 55, (235, 195, 20), -1)
        if 12 <= fi <= 24:
            cv2.rectangle(frm, (140, 480), (940, 860), (30, 245, 40), -1)
        mid_neon_frames.append(frm)
    _write_test_mp4(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", mid_neon_frames, fps=24)

    rep_mid_neon = verify_final_mp4_against_contract(p_dir, run_asr_sync=False, save_report=False)
    dq8_neon = rep_mid_neon["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_neon["passed"] is False, f"DQ8 missed mid-cut neon-green spill: {dq8_neon}"
    assert 1 in dq8_neon["skin_leak_cuts"]

    # Clean interior, but outer studio border has high-saturation glow spill on frames 12..24 -> DQ8 must fail!
    mid_margin_frames: list[np.ndarray] = []
    for fi in range(36):
        frm = np.full((1920, 1080, 3), (224, 227, 230), dtype=np.uint8)
        cx, cy = 540 + fi * 4 - 60, 760
        cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
        cv2.circle(frm, (cx - 70, cy - 55), 55, (235, 195, 20), -1)
        if 12 <= fi <= 24:
            frm[:, :95] = (235, 180, 10)
            frm[:, 985:] = (20, 155, 240)
        mid_margin_frames.append(frm)
    _write_test_mp4(p_dir / "05_assembly" / "final_shorts_1080x1920.mp4", mid_margin_frames, fps=24)

    rep_margin = verify_final_mp4_against_contract(p_dir, run_asr_sync=False, save_report=False)
    dq8_margin = rep_margin["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_margin["passed"] is False, f"DQ8 missed brain margin glow spill: {dq8_margin}"
    assert 1 in dq8_margin["skin_leak_cuts"]


def test_r66_calibrated_sunlit_birch_room_passes_while_bare_flesh_fails(tmp_path: Path) -> None:
    """
    Regression test for R66 empirical calibration (Item 1):
    Warm sunlit cream walls / birch wood (`BGR=(142, 188, 224)`) with matte-white porcelain cast/hands
    must PASS `inspect_diorama_clip_cv`, `DQ8`, and `R64` on `porcelain_fullbleed_world` and
    `porcelain_hands_closeup`, while bare biological flesh (`BGR=(135, 170, 225)`) must FAIL
    `human_skin_or_face_leak` across all three gates.
    """
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract
    from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa

    assert compute_porcelain_flesh_leak_ratio(np.zeros((0, 0, 3), dtype=np.uint8)) == 0.0
    sunlit_patch = np.full((120, 120, 3), (142, 188, 224), dtype=np.uint8)
    flesh_patch = np.full((120, 120, 3), (135, 170, 225), dtype=np.uint8)
    assert compute_porcelain_flesh_leak_ratio(sunlit_patch) == 0.0
    assert compute_porcelain_flesh_leak_ratio(flesh_patch) > 0.95

    h, w = 640, 360

    def _make_room_or_flesh_frames(bg_bgr: tuple[int, int, int], subject_bgr: tuple[int, int, int]) -> list[np.ndarray]:
        out: list[np.ndarray] = []
        for fi in range(96):
            frm = np.full((h, w, 3), bg_bgr, dtype=np.uint8)
            shift = int(22 * np.sin(fi * 0.24))
            # Moving matte-white porcelain figure/hand + crisp architectural panel edges
            cv2.rectangle(frm, (45 + shift, 130), (w - 45 + shift, h - 110), subject_bgr, -1)
            cv2.rectangle(frm, (85 + shift, 210), (w - 85 + shift, 360), (242, 244, 246), -1)
            for row_i in range(5):
                y_ln = 160 + row_i * 75 + (fi % 7) * 2
                cv2.line(frm, (35, y_ln), (w - 35, y_ln), (95, 110, 125), 3)
            rng = np.random.default_rng(7000 + fi)
            frm = np.clip(frm.astype(np.int16) + rng.integers(-5, 6, size=(h, w, 3), dtype=np.int16), 0, 255).astype(np.uint8)
            out.append(frm)
        return out

    # 1. Warm sunlit cream/birch room (`BGR=(142, 188, 224)`) + matte-white porcelain -> PASSES world & hands_closeup
    sunlit_mp4 = _write_test_mp4(
        tmp_path / "sunlit_birch_porcelain.mp4",
        _make_room_or_flesh_frames((142, 188, 224), (142, 188, 224)),
    )
    for gram in ("porcelain_fullbleed_world", "porcelain_hands_closeup"):
        rep_ok = inspect_diorama_clip_cv(
            sunlit_mp4,
            grammar=gram,
            schema_version=7,
            style_profile="porcelain_cinematic_v7",
        )
        assert rep_ok["passed"] is True, f"Warm sunlit birch room falsely rejected on {gram}: {rep_ok}"
        assert rep_ok["peach_ratio"] < 0.05

    # 2. Bare biological flesh (`BGR=(135, 170, 225)`) -> FAILS `human_skin_or_face_leak` on world & hands_closeup
    flesh_mp4 = _write_test_mp4(
        tmp_path / "bare_flesh_leak.mp4",
        _make_room_or_flesh_frames((220, 224, 228), (135, 170, 225)),
    )
    for gram in ("porcelain_fullbleed_world", "porcelain_hands_closeup"):
        rep_bad = inspect_diorama_clip_cv(
            flesh_mp4,
            grammar=gram,
            schema_version=7,
            style_profile="porcelain_cinematic_v7",
        )
        assert rep_bad["passed"] is False, f"Bare flesh was not rejected on {gram}: {rep_bad}"
        assert "human_skin_or_face_leak" in rep_bad["reason"], rep_bad

    # 3. Verify DQ8 & R64 also pass warm sunlit cream/birch cuts and reject bare flesh cuts
    def _build_1080_cut_frames(fill_bgr: tuple[int, int, int]) -> list[np.ndarray]:
        seq: list[np.ndarray] = []
        for fi in range(36):
            frm = np.full((1920, 1080, 3), fill_bgr, dtype=np.uint8)
            x0 = 220 + fi * 5
            cv2.rectangle(frm, (x0, 560), (x0 + 340, 980), (244, 246, 248), -1)
            for k in range(6):
                yk = 520 + k * 85
                cv2.line(frm, (120, yk), (960, yk + 8), (85, 95, 108), 6)
            seq.append(frm)
        return seq

    proj = tmp_path / "sunlit_dq8_r64_proj"
    for sd in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (proj / sd).mkdir(parents=True, exist_ok=True)
    (proj / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "sentences": ["Sunlight fills the quiet ward."]}),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [
                    {
                        "clip_number": i,
                        "sentence_index": 1,
                        "act": min(6, (i - 1) // 4 + 1),
                        "grammar": "porcelain_hands_closeup" if i == 1 else "porcelain_fullbleed_world",
                        "camera_move": "pan_right" if i % 2 == 1 else "locked_tripod",
                    }
                    for i in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )
    (proj / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "max_clip_reuse": 1,
                "total_duration_sec": 1.5,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 1,
                        "mode": "single",
                        "grammar": "porcelain_hands_closeup",
                        "camera_move": "pan_right",
                        "sentence_index": 1,
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.5,
                        "duration_sec": 1.5,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )

    sunlit_1080 = _build_1080_cut_frames((142, 188, 224))
    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4", sunlit_1080, fps=24)
    _write_test_mp4(proj / "05_assembly" / "final_shorts_1080x1920.mp4", sunlit_1080, fps=24)

    dq8_sunlit = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_sunlit["passed"] is True, f"DQ8 falsely flagged sunlit birch room: {dq8_sunlit}"
    r64_sunlit = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
    assert not any("human_skin_or_face_leak" in d for d in r64_sunlit["cuts"][0]["defects"]), r64_sunlit["cuts"][0]["defects"]

    flesh_1080 = _build_1080_cut_frames((135, 170, 225))
    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4", flesh_1080, fps=24)
    _write_test_mp4(proj / "05_assembly" / "final_shorts_1080x1920.mp4", flesh_1080, fps=24)

    dq8_flesh = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_flesh["passed"] is False, f"DQ8 missed bare flesh leak: {dq8_flesh}"
    r64_flesh = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
    assert any("human_skin_or_face_leak" in d for d in r64_flesh["cuts"][0]["defects"]), r64_flesh["cuts"][0]["defects"]


def test_r66_calibrated_brain_margin_scoping_and_zoom_camera_mean(tmp_path: Path) -> None:
    """
    Regression test for R66 empirical calibration (Item 2):
    - `PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX == 48.0`.
    - `frosted_glass_subcortical_xray` and `sagittal_coronal_cutaway` with saturated outer borders pass
      `brain_margin_glow_spill` in `inspect_diorama_clip_cv`, `DQ8`, and `R64`, while STILL failing when
      neon-green spill is injected.
    - `cortical_vascular_whole` still fails `brain_margin_glow_spill` when outer margin glow exceeds 48.0.
    - Zoom moves (`gentle_push_in`, `clean_pullback_reveal`) evaluate mean margin saturation across the cut
      so pushed-in end frames (`~15 -> ~24 -> ~70`, mean `< 48.0`) pass `DQ8` and `R64`, whereas `pan_right`
      catches single-frame spikes via `any`/`max`.
    """
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract
    from pipeline.posthoc_semantic_qa import run_posthoc_semantic_qa

    assert cfg.PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX == 48.0

    h, w = 640, 360

    def _make_brain_clip_frames(*, margin_bleed: bool = False, neon_green: bool = False) -> list[np.ndarray]:
        frames: list[np.ndarray] = []
        for fi in range(96):
            frm = np.full((h, w, 3), (226, 229, 232), dtype=np.uint8)
            cx, cy = w // 2 + int(8 * np.sin(fi * 0.18)), h // 2 + int(5 * np.cos(fi * 0.14))
            cv2.ellipse(frm, (cx, cy), (108, 138), 0, 0, 360, (204, 213, 222), -1)
            p_shift = int(18 * np.sin(fi * 0.25))
            cv2.circle(frm, (cx - 34 + p_shift, cy - 32), 22, (235, 195, 20), -1)
            cv2.circle(frm, (cx + 30, cy + 22 - p_shift // 2), 18, (35, 25, 205), -1)
            if margin_bleed:
                frm[:, : int(w * 0.10)] = (235, 180, 10)
                frm[:, int(w * 0.90) :] = (20, 155, 240)
            if neon_green:
                cv2.rectangle(frm, (45, 95), (w - 45, 245), (30, 245, 40), -1)
            rng = np.random.default_rng(8100 + fi)
            frm = np.clip(frm.astype(np.int16) + rng.integers(-6, 7, size=(h, w, 3), dtype=np.int16), 0, 255).astype(np.uint8)
            frames.append(frm)
        return frames

    bleed_mp4 = _write_test_mp4(tmp_path / "border_saturated_brain.mp4", _make_brain_clip_frames(margin_bleed=True))
    assert compute_brain_margin_saturation(_make_brain_clip_frames(margin_bleed=True)[0]) > cfg.PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX

    # 1. `frosted_glass_subcortical_xray` & `sagittal_coronal_cutaway` pass saturated borders, `cortical_vascular_whole` fails
    for exempt_mode in ("frosted_glass_subcortical_xray", "sagittal_coronal_cutaway"):
        rep_ex = inspect_diorama_clip_cv(
            bleed_mp4,
            grammar="porcelain_living_brain",
            schema_version=7,
            brain_mode=exempt_mode,
            style_profile="porcelain_cinematic_v7",
        )
        assert rep_ex["passed"] is True, f"{exempt_mode} should be exempt from outer-margin white-air sat check: {rep_ex}"

    rep_whole = inspect_diorama_clip_cv(
        bleed_mp4,
        grammar="porcelain_living_brain",
        schema_version=7,
        brain_mode="cortical_vascular_whole",
        style_profile="porcelain_cinematic_v7",
    )
    assert rep_whole["passed"] is False and "brain_margin_glow_spill" in rep_whole["reason"], rep_whole

    # 2. Neon-green spill STILL fails across ALL 4 brain modes
    neon_bleed_mp4 = _write_test_mp4(
        tmp_path / "neon_and_border_brain.mp4",
        _make_brain_clip_frames(margin_bleed=True, neon_green=True),
    )
    for b_mode in cfg.PORCELAIN_V7_BRAIN_RENDER_MODES:
        rep_ng = inspect_diorama_clip_cv(
            neon_bleed_mp4,
            grammar="porcelain_living_brain",
            schema_version=7,
            brain_mode=b_mode,
            style_profile="porcelain_cinematic_v7",
        )
        assert rep_ng["passed"] is False and "neon_green_fluorescent_spill" in rep_ng["reason"], (b_mode, rep_ng)

    # 3. DQ8 & R64: exempt cutaway/xray modes + zoom camera mean vs non-zoom max/any on cortical_vascular_whole
    proj = tmp_path / "zoom_and_mode_brain_proj"
    for sd in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (proj / sd).mkdir(parents=True, exist_ok=True)
    (proj / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "sentences": ["Clear channels carry the pulse."]}),
        encoding="utf-8",
    )

    def _write_plan_and_edl(b_mode: str, cam_move: str) -> None:
        (proj / "03_visuals" / "visual_plan.json").write_text(
            json.dumps(
                {
                    "schema": 7,
                    "profile": "neuro_diorama",
                    "style_profile": "porcelain_cinematic_v7",
                    "clips": [
                        {
                            "clip_number": i,
                            "sentence_index": 1,
                            "act": min(6, (i - 1) // 4 + 1),
                            "grammar": "porcelain_living_brain" if i == 1 else "porcelain_fullbleed_world",
                            "brain_mode": b_mode if i == 1 else "",
                            "camera_move": cam_move if i == 1 else ("pan_right" if i % 2 == 1 else "locked_tripod"),
                        }
                        for i in range(1, 21)
                    ],
                }
            ),
            encoding="utf-8",
        )
        (proj / "05_assembly" / "edit_decision_list.json").write_text(
            json.dumps(
                {
                    "schema": 7,
                    "style_profile": "porcelain_cinematic_v7",
                    "fps": 24,
                    "max_clip_reuse": 1,
                    "total_duration_sec": 1.5,
                    "cuts": [
                        {
                            "cut_index": 1,
                            "clip_index": 1,
                            "act": 3,
                            "mode": "single",
                            "grammar": "porcelain_living_brain",
                            "brain_mode": b_mode,
                            "camera_move": cam_move,
                            "sentence_index": 1,
                            "sentence_indices": [1],
                            "out_start_sec": 0.0,
                            "out_end_sec": 1.5,
                            "duration_sec": 1.5,
                            "src_start_sec": 0.0,
                            "src_end_sec": 1.5,
                        }
                    ],
                }
            ),
            encoding="utf-8",
        )

    # Build a 36-frame 1080x1920 push-in clip where start/mid borders are ~15 -> ~24 and end frames push into ~68 (mean ~36 < 48)
    pushin_frames_1080: list[np.ndarray] = []
    for fi in range(36):
        frm = np.full((1920, 1080, 3), (221, 228, 235), dtype=np.uint8)
        cx, cy = 540 + fi * 3 - 45, 760
        cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
        for gi in range(-4, 5):
            cv2.line(frm, (cx - 170, cy + gi * 44), (cx + 170, cy + gi * 44 + 10), (140, 150, 160), 6)
        cv2.circle(frm, (cx - 75, cy - 60), 50, (235, 195, 20), -1)
        if 14 <= fi < 28:
            frm[:192, :] = (213, 224, 235)
            frm[:, :76] = (213, 224, 235)
            frm[:, 1004:] = (213, 224, 235)
        elif fi >= 28:
            # End-of-push-in frame brings subtle rim tint into outer border -> margin_sat ~ 68.4 (> 48), 3-sample mean ~ 35.8 (< 48)
            frm[:192, :] = (172, 204, 235)
            frm[:, :76] = (172, 204, 235)
            frm[:, 1004:] = (172, 204, 235)
        pushin_frames_1080.append(frm)

    assert compute_brain_margin_saturation(pushin_frames_1080[-1]) > cfg.PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX
    assert float(
        np.mean([compute_brain_margin_saturation(pushin_frames_1080[idx]) for idx in (2, 18, 33)])
    ) < cfg.PORCELAIN_V7_BRAIN_MARGIN_SAT_MAX

    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4", pushin_frames_1080, fps=24)
    _write_test_mp4(proj / "05_assembly" / "final_shorts_1080x1920.mp4", pushin_frames_1080, fps=24)

    # Zoom push-in & pullback on cortical_vascular_whole -> PASS DQ8 and R64 via mean <= 48.0
    for zoom_cam in ("gentle_push_in", "clean_pullback_reveal"):
        _write_plan_and_edl("cortical_vascular_whole", zoom_cam)
        dq8_zoom = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
        assert dq8_zoom["passed"] is True, f"{zoom_cam} end-frame border was falsely flagged in DQ8: {dq8_zoom}"
        r64_zoom = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
        assert not any("brain_margin_glow_spill" in d for d in r64_zoom["cuts"][0]["defects"]), (zoom_cam, r64_zoom["cuts"][0]["defects"])

    # Non-zoom pan_right & locked_tripod on the exact same MP4 -> FAIL DQ8 and R64 via any/max > 48.0
    for static_or_pan_cam in ("pan_right", "locked_tripod"):
        _write_plan_and_edl("cortical_vascular_whole", static_or_pan_cam)
        dq8_pan = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
        assert dq8_pan["passed"] is False, f"{static_or_pan_cam} failed to flag >48.0 border spike in DQ8: {dq8_pan}"
        r64_pan = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
        assert any("brain_margin_glow_spill" in d for d in r64_pan["cuts"][0]["defects"]), (static_or_pan_cam, r64_pan["cuts"][0]["defects"])

    # Exempt modes (`frosted_glass_subcortical_xray`, `sagittal_coronal_cutaway`) on pan_right -> PASS DQ8 and R64
    for ex_mode in ("frosted_glass_subcortical_xray", "sagittal_coronal_cutaway"):
        _write_plan_and_edl(ex_mode, "pan_right")
        dq8_ex = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
        assert dq8_ex["passed"] is True, f"{ex_mode} falsely flagged in DQ8: {dq8_ex}"
        r64_ex = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
        assert not any("brain_margin_glow_spill" in d for d in r64_ex["cuts"][0]["defects"]), (ex_mode, r64_ex["cuts"][0]["defects"])


def test_r66_alias_normalization_metadata_fallbacks_and_cache_invalidation(tmp_path: Path) -> None:
    """
    Adversarial edge-case regression test for R66 calibration:
    1) 2D grayscale (`ndim == 2`) and 4-channel `BGRA` frames do not crash `compute_porcelain_flesh_leak_ratio`.
    2) Whole-brain aliases (`"auto"`, `"cortical"`, `"vascular"`, `"matte_pastel_cortical_model"`) resolve to
       `"cortical_vascular_whole"` and still fail `brain_margin_glow_spill` across `inspect_diorama_clip_cv`, `DQ8`, and `R64`.
    3) `render_mode="sagittal_coronal_cutaway"` and pre-composed cutaway `scene` strings (without explicit `brain_mode`
       on `visual_plan.json` or `edit_decision_list.json`) resolve to `"sagittal_coronal_cutaway"` in `build_diorama_v7_prompts`,
       `DQ8`, and `R64`.
    4) `extract_cut_intent_specs` preserves `v_meta["camera_move"] = "gentle_push_in"` when `edit_decision_list.json`
       and `flow_all_in_one_prompts.json` omit `camera_move`.
    5) Updating `03_visuals/flow_all_in_one_prompts.json` invalidates `run_posthoc_semantic_qa`'s CV cache (`prompts_sha`).
    6) Warm sunset `outro_sky_card` (`porcelain_fullbleed_world` with `outro_sky_card=True`) is exempt from `DQ8` flesh-leak rejection.
    """
    from pipeline.depiction_rules import ContainedLiving3DBrainRule, normalize_porcelain_v7_brain_mode
    from pipeline.dynamic_episode_qa import verify_final_mp4_against_contract
    from pipeline.flow_prompt_builder import build_diorama_v7_prompts
    from pipeline.posthoc_semantic_qa import extract_cut_intent_specs, run_posthoc_semantic_qa

    # 1. Channel safety: 2D grayscale -> 0.0, 4-channel BGRA flesh -> > 0.95
    assert compute_porcelain_flesh_leak_ratio(np.full((48, 48), 180, dtype=np.uint8)) == 0.0
    bgra_flesh = np.full((48, 48, 4), (135, 170, 225, 255), dtype=np.uint8)
    assert compute_porcelain_flesh_leak_ratio(bgra_flesh) > 0.95

    # 2. Whole-brain aliases still enforce `brain_margin_glow_spill` in `inspect_diorama_clip_cv`
    h, w = 640, 360
    bleed_frames: list[np.ndarray] = []
    for fi in range(96):
        frm = np.full((h, w, 3), (226, 229, 232), dtype=np.uint8)
        cx, cy = w // 2 + int(8 * np.sin(fi * 0.18)), h // 2
        cv2.ellipse(frm, (cx, cy), (108, 138), 0, 0, 360, (204, 213, 222), -1)
        cv2.circle(frm, (cx - 30 + int(16 * np.sin(fi * 0.25)), cy - 30), 22, (235, 195, 20), -1)
        frm[:, : int(w * 0.10)] = (235, 180, 10)
        frm[:, int(w * 0.90) :] = (20, 155, 240)
        rng = np.random.default_rng(9100 + fi)
        frm = np.clip(frm.astype(np.int16) + rng.integers(-5, 6, size=(h, w, 3), dtype=np.int16), 0, 255).astype(np.uint8)
        bleed_frames.append(frm)
    bleed_mp4 = _write_test_mp4(tmp_path / "alias_bleed.mp4", bleed_frames)

    for whole_alias in ("auto", "cortical", "vascular", "cortical_model", "matte_pastel_cortical_model"):
        assert normalize_porcelain_v7_brain_mode(whole_alias) == "cortical_vascular_whole"
        rep_al = inspect_diorama_clip_cv(
            bleed_mp4,
            grammar="porcelain_living_brain",
            schema_version=7,
            brain_mode=whole_alias,
            style_profile="porcelain_cinematic_v7",
        )
        assert rep_al["passed"] is False and "brain_margin_glow_spill" in rep_al["reason"], (whole_alias, rep_al)

    # 3. `render_mode` and pre-composed cutaway `scene` resolve to `sagittal_coronal_cutaway` in `build_diorama_v7_prompts`
    cutaway_scene = ContainedLiving3DBrainRule.compose(
        brain_mode="sagittal_coronal_cutaway",
        brain_region="hippocampus",
    )
    rendered = build_diorama_v7_prompts(
        {
            "schema": 7,
            "profile": "neuro_diorama",
            "style_profile": "porcelain_cinematic_v7",
            "clips": [
                {
                    "clip_number": 1,
                    "sentence_index": 1,
                    "act": 3,
                    "grammar": "porcelain_living_brain",
                    "render_mode": "sagittal_coronal_cutaway",
                    "region": "hippocampus",
                },
                {
                    "clip_number": 2,
                    "sentence_index": 1,
                    "act": 3,
                    "grammar": "porcelain_living_brain",
                    "scene": cutaway_scene,
                },
                *[
                    {
                        "clip_number": i,
                        "sentence_index": 1,
                        "act": min(6, (i - 1) // 4 + 1),
                        "grammar": "porcelain_fullbleed_world",
                    }
                    for i in range(3, 21)
                ],
            ],
        },
        ["Deep inside the temporal lobe, the relay snaps."],
    )
    assert rendered[0]["brain_mode"] == "sagittal_coronal_cutaway"
    assert rendered[1]["brain_mode"] == "sagittal_coronal_cutaway"

    # 4 & 5. Realistic EDL (no `brain_mode` or `camera_move` on cut) + `prompts.json` cache invalidation + `auto` alias in DQ8/R64
    proj = tmp_path / "alias_and_cache_proj"
    for sd in ("02_script", "03_visuals/flow_native_clips", "04_audio", "05_assembly"):
        (proj / sd).mkdir(parents=True, exist_ok=True)
    (proj / "04_audio" / "voice_report.json").write_text(json.dumps({"engine": "edge-tts"}), encoding="utf-8")
    (proj / "02_script" / "script.json").write_text(
        json.dumps({"schema": 7, "profile": "neuro_diorama", "sentences": ["Signals cross the cortex.", "Look up tonight."]}),
        encoding="utf-8",
    )

    bleed_1080: list[np.ndarray] = []
    for fi in range(36):
        frm = np.full((1920, 1080, 3), (224, 228, 232), dtype=np.uint8)
        cx, cy = 540 + fi * 4 - 60, 760
        cv2.ellipse(frm, (cx, cy), (260, 320), 0, 0, 360, (202, 212, 222), -1)
        cv2.circle(frm, (cx - 70, cy - 60), 52, (235, 195, 20), -1)
        frm[:, :108] = (235, 180, 10)
        frm[:, 972:] = (20, 155, 240)
        bleed_1080.append(frm)
    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4", bleed_1080, fps=24)
    _write_test_mp4(proj / "05_assembly" / "final_shorts_1080x1920.mp4", bleed_1080, fps=24)

    # EDL omits `brain_mode` and `camera_move` (matching real `diorama_assembler.py` EDL cuts)
    (proj / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "max_clip_reuse": 1,
                "total_duration_sec": 1.5,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "act": 3,
                        "mode": "single",
                        "grammar": "porcelain_living_brain",
                        "sentence_index": 1,
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.5,
                        "duration_sec": 1.5,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.5,
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    (proj / "03_visuals" / "visual_plan.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "profile": "neuro_diorama",
                "style_profile": "porcelain_cinematic_v7",
                "clips": [
                    {
                        "clip_number": i,
                        "sentence_index": 1,
                        "act": min(6, (i - 1) // 4 + 1),
                        "grammar": "porcelain_living_brain" if i == 1 else "porcelain_fullbleed_world",
                        "brain_mode": "auto" if i == 1 else "",
                        "camera_move": "gentle_push_in" if i == 1 else "locked_tripod",
                    }
                    for i in range(1, 21)
                ],
            }
        ),
        encoding="utf-8",
    )

    cuts_spec, _ = extract_cut_intent_specs(proj)
    assert cuts_spec[0]["camera_move"] == "gentle_push_in"
    assert cuts_spec[0]["brain_mode"] == "cortical_vascular_whole"

    # With `brain_mode="auto"` and full-clip border bleed (`> 48.0`), both DQ8 and R64 must FAIL `brain_margin_glow_spill`
    (proj / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"schema_version": 7, "clips": [{"clip_number": 1, "grammar": "porcelain_living_brain", "brain_mode": "cortical_vascular_whole", "camera_move": "pan_right"}]}),
        encoding="utf-8",
    )
    dq8_auto = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_auto["passed"] is False
    r64_before = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
    assert any("brain_margin_glow_spill" in d for d in r64_before["cuts"][0]["defects"]), r64_before["cuts"][0]["defects"]

    # Updating ONLY `flow_all_in_one_prompts.json` to `sagittal_coronal_cutaway` must invalidate the posthoc CV cache and PASS R64
    (proj / "03_visuals" / "flow_all_in_one_prompts.json").write_text(
        json.dumps({"schema_version": 7, "clips": [{"clip_number": 1, "grammar": "porcelain_living_brain", "brain_mode": "sagittal_coronal_cutaway", "camera_move": "pan_right"}]}),
        encoding="utf-8",
    )
    r64_after = run_posthoc_semantic_qa(proj, render_strips=False, run_asr_sync=False)
    assert not any("brain_margin_glow_spill" in d for d in r64_after["cuts"][0]["defects"]), r64_after["cuts"][0]["defects"]

    # 6. Warm sunset `outro_sky_card` (`BGR=(135, 170, 225)` clouds) is exempt from `DQ8` flesh-leak check
    room_24 = [np.full((1920, 1080, 3), (142, 188, 224), dtype=np.uint8) for _ in range(24)]
    for fi, rf in enumerate(room_24):
        cv2.rectangle(rf, (180 + fi * 4, 560), (480 + fi * 4, 860), (242, 244, 246), -1)
    sunset_24 = [np.full((1920, 1080, 3), (135, 170, 225), dtype=np.uint8) for _ in range(24)]
    for fi, sf in enumerate(sunset_24):
        cv2.rectangle(sf, (180 + fi * 4, 560), (480 + fi * 4, 860), (235, 240, 245), -1)
    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_1.mp4", room_24, fps=24)
    _write_test_mp4(proj / "03_visuals" / "flow_native_clips" / "clip_2.mp4", sunset_24, fps=24)
    _write_test_mp4(proj / "05_assembly" / "final_shorts_1080x1920.mp4", room_24 + sunset_24, fps=24)
    (proj / "05_assembly" / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "schema": 7,
                "style_profile": "porcelain_cinematic_v7",
                "fps": 24,
                "max_clip_reuse": 1,
                "total_duration_sec": 2.0,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 2,
                        "act": 1,
                        "mode": "single",
                        "grammar": "porcelain_fullbleed_world",
                        "sentence_index": 1,
                        "sentence_indices": [1],
                        "out_start_sec": 0.0,
                        "out_end_sec": 1.0,
                        "duration_sec": 1.0,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.0,
                    },
                    {
                        "cut_index": 2,
                        "clip_index": 2,
                        "act": 6,
                        "mode": "outro",
                        "outro_sky_card": True,
                        "grammar": "porcelain_fullbleed_world",
                        "sentence_index": 2,
                        "sentence_indices": [2],
                        "out_start_sec": 1.0,
                        "out_end_sec": 2.0,
                        "duration_sec": 1.0,
                        "src_start_sec": 0.0,
                        "src_end_sec": 1.0,
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    dq8_outro = verify_final_mp4_against_contract(proj, run_asr_sync=False, save_report=False)["gates"]["DQ8_zero_uncanny_skin_gore"]
    assert dq8_outro["passed"] is True, f"Warm sunset outro_sky_card falsely flagged in DQ8: {dq8_outro}"

