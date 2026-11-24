"""
Regression Suite: Global Google Flow Omni 1.2 Flash Migration & Retired Model Purge
(`tests/test_omni12_global_migration.py`).

Verifies compliance with Official Google Flow Spec (`support.google.com/flow/answer/16352836`):
  - `Omni 1.1 Flash` (`abra`), `Omni 1.1 Quality`, `Veo 3.1 - Fast`, and `Veo 3.1 - Quality`
    are retired (`2026-12-05`) and must never be emitted or routed.
  - `Omni 1.2 Flash` (`macaron_cookie`, API `gemini-omni-1.2-flash`) is the sole paid Omni tier
    supporting BOTH `Ingredients` (`3s-15s`) and `Frames to Video` (`Start + End`, `3s-10s`).
  - `Veo 3.1 - Lite [Lower Priority]` (`0 credits`, `4s/6s/8s`, `Start + End` supported) remains
    the direct 0-credit fallback when `Omni 1.2 Flash` credits are exhausted in `auto` mode.
"""

from __future__ import annotations

import asyncio
import re
from pathlib import Path
from typing import Any

import pytest

from pipeline import config as cfg
from pipeline.flow_ingredients import _family_matches_model
from pipeline.prompt_builder import build_flow_prompts, normalize_clip_engine_tag


def test_omni12_config_constants_and_retired_models() -> None:
    assert cfg.FLOW_PRIMARY_VIDEO_MODEL == "Omni 1.2 Flash"
    assert cfg.FLOW_ACTIVE_VIDEO_MODEL == "Omni 1.2 Flash"
    assert cfg.FLOW_PRIMARY_OMNI_MODEL_KEY == "macaron_cookie"
    assert cfg.FLOW_SECONDARY_OMNI_MODEL is None

    for retired in ("Omni 1.1 Flash", "Omni 1.1 Quality", "Veo 3.1 - Fast", "Veo 3.1 - Quality"):
        assert retired in cfg.FLOW_RETIRED_VIDEO_MODELS
        assert retired not in cfg.ALLOWED_FLOW_MODELS
        assert retired not in cfg.FLOW_VIDEO_MODEL_PROFILES
        assert retired not in cfg.FLOW_MODELS

    assert cfg.ALLOWED_FLOW_MODELS == ["Omni 1.2 Flash", "Veo 3.1 - Lite [Lower Priority]"]
    assert "Veo 3.1 - Lite [Lower Priority]" in cfg.ALLOWED_FLOW_MODELS
    assert set(cfg.FLOW_MODELS.keys()) == set(cfg.ALLOWED_FLOW_MODELS)
    assert cfg.FLOW_MODEL_DESCRIPTIONS == cfg.FLOW_MODELS


def test_omni12_model_profile_capabilities() -> None:
    profile = cfg.FLOW_VIDEO_MODEL_PROFILES["Omni 1.2 Flash"]
    assert profile["supports_start_end_frames"] is True
    assert profile["first_and_last_max_sec"] == 10
    assert profile["api_model_id"] == "gemini-omni-1.2-flash"
    assert profile["model_family_id"] == "macaron_cookie"
    assert profile["zero_credit"] is False

    lite_profile = cfg.FLOW_VIDEO_MODEL_PROFILES["Veo 3.1 - Lite [Lower Priority]"]
    assert lite_profile["model_family_id"] == "veo_3_1_lite_low_priority"
    assert lite_profile["zero_credit"] is True
    assert lite_profile["supports_start_end_frames"] is True


def test_build_flow_prompts_routes_single_anchor_and_start_end_to_omni12() -> None:
    clips: list[dict[str, Any]] = []
    for i in range(1, 19):
        if i == 1:
            clips.append(
                {
                    "clip_number": i,
                    "grammar": "expressive_exterior_establishing",
                    "camera_move": "drone_aerial_approach",
                    "reference_image": "03_visuals/reference_images/kf_c01.png",
                    "action": "Sweeps high over sunlit campus dome and tree canopy",
                }
            )
        elif i == 2:
            clips.append(
                {
                    "clip_number": i,
                    "grammar": "spatial_3d_arrow_diorama",
                    "camera_move": "topdown_3d_route_glide",
                    "arrow_3d_mode": "doorway_boundary_sever",
                    "flow_input_mode": "VIDEO_FRAMES",
                    "reference_image": "03_visuals/reference_images/kf_c02_start.png",
                    "end_reference_image": "03_visuals/reference_images/kf_c02_end.png",
                    "action": "3D crimson arrow halts cleanly across the doorway threshold",
                }
            )
        elif i == 3:
            clips.append(
                {
                    "clip_number": i,
                    "grammar": "expressive_reaction_closeup",
                    "camera_move": "gentle_push_in",
                    "reference_image": "03_visuals/reference_images/kf_c03.png",
                    "preferred_flow_model": "Omni 1.1 Flash",  # Legacy retired tag must auto-upgrade!
                    "action": "The researcher lifts an unmarked glass bottle to eye level",
                }
            )
        elif i == 4:
            clips.append(
                {
                    "clip_number": i,
                    "grammar": "expressive_vinyl_world",
                    "camera_move": "locked_tripod",
                    "reference_image": "03_visuals/reference_images/kf_c04.png",
                    "preferred_flow_model": "Veo 3.1 - Fast",  # Legacy retired Veo Fast must auto-upgrade!
                    "action": "The student sets a ceramic mug beside a paper notebook",
                }
            )
        else:
            clips.append(
                {
                    "clip_number": i,
                    "grammar": "expressive_xray_brain" if i == 10 else "expressive_vinyl_world",
                    "camera_move": "gentle_push_in",
                    "brain_region": "hippocampus" if i == 10 else None,
                    "viewpoint": "midsagittal_cutaway" if i == 10 else None,
                    "reference_image": f"03_visuals/reference_images/kf_c{i:02d}.png",
                    "action": (
                        "Translucent cutaway reveals glowing cyan hippocampus fold"
                        if i == 10
                        else "The character turns a paper page on the sunlit wooden desk"
                    ),
                }
            )

    v8_plan = {
        "schema": 8,
        "project_id": "v8_omni12_migration_unit",
        "style_profile": "expressive_25d_v8",
        "r85_mode": True,
        "skip_r85_stamp_count_in_unit_test": True,
        "clips": clips,
    }
    narrations = [f"Clear narration line {i} for Omni 1.2 migration check." for i in range(1, 19)]
    built = build_flow_prompts(v8_plan, narrations=narrations)

    assert len(built) == 18
    # Single-anchor clip (Clip 1), Start+End VIDEO_FRAMES clip (Clip 2), legacy-tagged closeups (Clip 3 & 4):
    assert built[0]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert built[1]["flow_input_mode"] == "VIDEO_FRAMES"
    assert built[1]["end_reference_image"] == "03_visuals/reference_images/kf_c02_end.png"
    assert built[1]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert built[2]["flow_input_mode"] == "VIDEO_FRAMES"
    assert built[2]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert built[3]["preferred_flow_model"] == "Omni 1.2 Flash"
    assert all(c["preferred_flow_model"] == "Omni 1.2 Flash" for c in built)
    assert all(c["preferred_flow_model"] != "Omni 1.1 Flash" for c in built)

    # CLI engine tag normalization routes legacy aliases cleanly to 'omni' (Omni 1.2 Flash tier)
    assert normalize_clip_engine_tag("omni-1.2-flash") == "omni"
    assert normalize_clip_engine_tag("gemini-omni-1.2-flash") == "omni"
    assert normalize_clip_engine_tag("omni-1.1-flash") == "omni"


def test_family_matches_model_rejects_retired_abra_and_omni11() -> None:
    # Retired Omni 1.1 family IDs MUST fail verification against Omni 1.2 Flash
    assert _family_matches_model("Omni 1.2 Flash", "abra") is False
    assert _family_matches_model("Omni 1.2 Flash", "omni_1_1_flash") is False
    assert _family_matches_model("Omni 1.2 Flash", "omni_1_1") is False
    assert _family_matches_model("Omni 1.2 Flash", "veo_3_1_fast") is False
    assert _family_matches_model("Omni 1.2 Flash", "veo_3_1_lite_low_priority") is False
    assert _family_matches_model("Omni 1.2 Flash", "") is False

    # Valid Omni 1.2 Flash family IDs MUST pass
    assert _family_matches_model("Omni 1.2 Flash", "macaron_cookie") is True
    assert _family_matches_model("Omni 1.2 Flash", "omni_1_2_flash") is True
    assert _family_matches_model("Omni 1.2 Flash", "omni_1_2") is True
    assert _family_matches_model("Omni 1.2 Flash", "gemini-omni-1.2-flash") is True

    # Zero-credit Veo 3.1 Lite MUST remain intact and reject Omni families
    assert _family_matches_model("Veo 3.1 - Lite [Lower Priority]", "veo_3_1_lite_low_priority") is True
    assert _family_matches_model("Veo 3.1 - Lite [Lower Priority]", "macaron_cookie") is False
    assert _family_matches_model("Veo 3.1 - Lite [Lower Priority]", "abra") is False

    # Retired model names MUST never match
    assert _family_matches_model("Omni 1.1 Flash", "abra") is False
    assert _family_matches_model("Veo 3.1 - Fast", "veo_3_1_fast") is False


def test_source_guard_zero_active_omni11_or_abra_routing_in_flow_modules() -> None:
    repo_root = Path(__file__).resolve().parents[1]
    guarded_files = (
        repo_root / "pipeline" / "prompt_builder.py",
        repo_root / "pipeline" / "flow_worker.py",
        repo_root / "pipeline" / "flow_single_worker.py",
        repo_root / "pipeline" / "flow_ingredients.py",
    )
    banned_patterns = (
        ("Omni 1.1 Flash", re.compile(r"Omni\s*1\.1\s*Flash", re.IGNORECASE)),
        ("abra family token", re.compile(r"\babra\b", re.IGNORECASE)),
        ("omni_1_1_flash token", re.compile(r"\bomni_1_1_flash\b", re.IGNORECASE)),
    )
    violations: list[str] = []
    for path in guarded_files:
        text = path.read_text(encoding="utf-8")
        for label, rx in banned_patterns:
            for m in rx.finditer(text):
                line_no = text.count("\n", 0, m.start()) + 1
                line_txt = text.splitlines()[line_no - 1].strip()
                violations.append(f"{path.name}:{line_no} [{label}] -> {line_txt}")
    assert violations == [], "Found retired Omni 1.1 / abra references:\n" + "\n".join(violations)


def test_sharded_worker_routes_start_end_frames_on_omni12_and_reselects_if_abra(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    import pipeline.flow_worker as worker_mod

    start_png = tmp_path / "start.png"
    end_png = tmp_path / "end.png"
    start_png.write_bytes(b"\x89PNG\r\n\x1a\nstart")
    end_png.write_bytes(b"\x89PNG\r\n\x1a\nend")

    state: dict[str, Any] = {
        "family": "abra",  # Simulate stale retired tab family before attach
        "chips": 0,
        "selected_models": [],
        "ed_len": 0,
    }

    class _FakeClient:
        async def eval(self, expr: str) -> Any:
            if "exhausted" in expr:
                return {"exhausted": False, "has_warning_btn": False}
            if "cdk-overlay-pane" in expr:
                return False
            if "flow-generate-icon-button" in expr and "ProseMirror" in expr:
                return True
            if "ed.focus()" in expr and "InputEvent" not in expr:
                return True
            if "InputEvent" in expr:
                state["ed_len"] = 30
                return True
            if "listener_invoked" in expr:
                state["ed_len"] = 0
                return {"action": "listener_invoked", "x": 100, "y": 100}
            if ".trim().length" in expr:
                return state["ed_len"]
            return None

        async def send(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
            return {}

    async def _fast_sleep(_s: float) -> None:
        return None

    async def _fake_cfg_engine(_c: Any, **_kw: Any) -> dict[str, Any]:
        return {"flow_model": "Omni 1.2 Flash", "credit_tier": "omni_monthly_credit"}

    async def _fake_select_model(_c: Any, model: str) -> bool:
        state["selected_models"].append(model)
        if model == "Omni 1.2 Flash":
            state["family"] = "macaron_cookie"
        return True

    async def _fake_read_fam(_c: Any) -> str:
        return str(state["family"])

    async def _fake_upload_start_end(_c: Any, start_frame: Path, end_frame: Path | None = None, **_kw: Any) -> dict[str, Any]:
        state["chips"] = 2 if end_frame else 1
        return {
            "start_attached": True,
            "end_attached": bool(end_frame),
            "chip_count": state["chips"],
            "input_mode": "VIDEO_FRAMES",
        }

    async def _fake_count_chips(_c: Any) -> int:
        return int(state["chips"])

    async def _noop_async(*_a: Any, **_kw: Any) -> bool:
        return True

    monkeypatch.setattr(worker_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(worker_mod, "_configure_diorama_tab_engine", _fake_cfg_engine)
    monkeypatch.setattr(worker_mod, "select_flow_video_model", _fake_select_model)
    monkeypatch.setattr(worker_mod, "read_active_flow_model_family", _fake_read_fam)
    monkeypatch.setattr(worker_mod, "upload_start_end_frames_to_flow", _fake_upload_start_end)
    monkeypatch.setattr(worker_mod, "count_chips", _fake_count_chips)
    monkeypatch.setattr(worker_mod, "clear_prompt_ingredients", _noop_async)
    monkeypatch.setattr(worker_mod, "enable_background_focus_emulation", _noop_async)
    monkeypatch.setattr(worker_mod, "press_escape", _noop_async)

    sub_meta: dict[str, Any] = {}
    ok = asyncio.run(
        worker_mod._submit_diorama_prompt_zero_credit(
            _FakeClient(),
            "Smooth 2.5D vinyl motion from start to end frame.",
            short_ref_path=start_png,
            ref_state={},
            engine_mode="auto",
            submission_meta_out=sub_meta,
            end_ref_path=end_png,
            end_ref_is_secondary_ingredient=False,
        )
    )
    assert ok is True
    assert state["selected_models"] == ["Omni 1.2 Flash"]
    assert "Omni 1.1 Flash" not in state["selected_models"]
    assert sub_meta["flow_model"] == "Omni 1.2 Flash"
    assert sub_meta["input_mode"] == "VIDEO_FRAMES"
    assert sub_meta["end_reference_attached"] is True


def test_live_single_worker_falls_back_directly_from_omni12_to_veo_lite(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import pipeline.flow_ingredients as fi_mod
    import pipeline.flow_single_worker as lsw_mod

    selected_models: list[str] = []

    class _FakeClient:
        async def eval(self, expr: str) -> Any:
            if "has_warning_btn" in expr or "exhausted" in expr:
                # Omni 1.2 Flash reports exhausted; Veo Lite reports 0-credit clean
                if selected_models and selected_models[-1] == cfg.FLOW_ZERO_CREDIT_MODEL:
                    return {"exhausted": False, "has_warning_btn": False}
                return {"exhausted": True, "has_warning_btn": True}
            if "Generating will use 0 credits" in expr:
                return {"has_zero_credit": True, "text": "Veo 3.1 - Lite [Lower Priority] Generating will use 0 credits"}
            if "settings-trigger-button" in expr and "innerText" in expr and "getBoundingClientRect" not in expr:
                return "Video 9:16 8s x1"
            return None

        async def send(self, *_a: Any, **_kw: Any) -> dict[str, Any]:
            return {}

    async def _fast_sleep(_s: float) -> None:
        return None

    async def _fake_select(_c: Any, model: str) -> bool:
        selected_models.append(model)
        return True

    async def _fake_read_fam(_c: Any) -> str:
        if selected_models and selected_models[-1] == cfg.FLOW_ZERO_CREDIT_MODEL:
            return "veo_3_1_lite_low_priority"
        return "macaron_cookie"

    async def _noop_async(*_a: Any, **_kw: Any) -> bool:
        return True

    monkeypatch.setattr(lsw_mod.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(lsw_mod, "record_flow_credit_exhausted", lambda **_kw: {})
    monkeypatch.setattr(fi_mod, "select_flow_video_model", _fake_select)
    monkeypatch.setattr(fi_mod, "read_active_flow_model_family", _fake_read_fam)
    monkeypatch.setattr(fi_mod, "press_escape", _noop_async)
    monkeypatch.setattr(fi_mod, "trusted_click", _noop_async)

    ev = asyncio.Event()
    res = asyncio.run(
        lsw_mod.ensure_manual_video_916_mode(
            _FakeClient(),
            target_duration="8s",
            engine_mode="auto",
            credit_exhausted_event=ev,
            force_recheck=True,
        )
    )
    assert "Omni 1.1 Flash" not in selected_models
    assert selected_models[0] == "Omni 1.2 Flash"
    assert cfg.FLOW_ZERO_CREDIT_MODEL in selected_models
    assert ev.is_set() is True
    assert res["flow_model"] == cfg.FLOW_ZERO_CREDIT_MODEL
    assert res["credit_tier"] == "zero_credit_fallback"


# --- Merged from test_v8_3_omni12_master_upgrade.py ---
import numpy as np  # noqa: E402
from pipeline.assembler import (  # noqa: E402
    build_dual_harvest_edl_windows,
    lock_audio_durations_onto_visual_plan,
    resolve_spatial_metric_stamps,
    split_sentences_at_keyword_beats,
    verify_state_swap_hist_corr,
)
from pipeline.depiction_rules import (  # noqa: E402
    ExpressiveReactionCloseupRule,
    ExpressiveRigidPhysicsRule,
    format_expression_acting_clause,
    load_expression_acting_lexicon,
)
from pipeline.flow_workspace import (  # noqa: E402
    FLOW_OMNI_CREDIT_COST_NO_REF as WS_NO_REF,
    FLOW_OMNI_CREDIT_COST_WITH_REF as WS_WITH_REF,
)
from pipeline.prompt_builder import validate_v83_camera_and_acting_balance  # noqa: E402
from pipeline.reference_pack import (  # noqa: E402
    EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES,
    populate_expressive_v8_reference_contract,
)
from pipeline.studio.uploader import StudioUploader  # noqa: E402


def test_component0_translucent_brain_6pack_staged() -> None:
    ref_dir = cfg.WORKSPACE_ROOT / "BCI_Shorts_Channel" / "reference_style_anchors" / cfg.TRANSLUCENT_BRAIN_V8_REFS_DIRNAME
    assert ref_dir.is_dir()
    assert len(cfg.TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES) == 6
    for fn in cfg.TRANSLUCENT_BRAIN_V8_CANDIDATE_FILENAMES:
        p = ref_dir / fn
        assert p.is_file(), f"Missing staged translucent brain ref: {p}"
        assert p.stat().st_size > 50_000


def test_component1_omni12_and_dynamic_budget_parity() -> None:
    assert cfg.FLOW_PRIMARY_OMNI_MODEL_KEY == "macaron_cookie"
    assert cfg.FLOW_PRIMARY_OMNI_MODEL_LABEL == "Omni 1.2 Flash"
    assert WS_NO_REF == 24
    assert WS_WITH_REF == cfg.FLOW_OMNI_CREDIT_COST_WITH_REF == 24
    assert cfg.FLOW_ENABLE_720P_LANCZOS_UNSHARP is False

    b_full = cfg.compute_dynamic_omni_episode_budget(1000, clip_count=20)
    assert b_full["all_omni_possible"] is True
    assert b_full["max_omni_clips"] == 20

    b_mid = cfg.compute_dynamic_omni_episode_budget(260, clip_count=20)
    assert b_mid["max_omni_clips"] == 10
    assert b_mid["zero_credit_fallback_clips"] == 10

    b_low = cfg.compute_dynamic_omni_episode_budget(16, clip_count=20)
    assert b_low["max_omni_clips"] == 0
    assert b_low["zero_credit_fallback_clips"] == 20


def test_component2_single_start_frame_default_and_previs_nodal_orbit() -> None:
    assert cfg.EXPRESSIVE_V8_SINGLE_START_FRAME_DEFAULT is True
    assert "object_portal_macro" not in EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES
    assert "fpv_aperture_wide" in EXPRESSIVE_V8_PREVIS_CAMERA_ANGLES

    dummy_plan = {
        "style_profile": "expressive_25d_v8",
        "v8_3_mode": True,
        "clips": [
            {"clip_number": i, "grammar": ("expressive_xray_brain" if i == 12 else "expressive_vinyl_world"), "portal_to_brain": (i == 12)}
            for i in range(1, 19)
        ],
    }
    populated = populate_expressive_v8_reference_contract(dummy_plan, daisy_chain_keyframes=False)
    for c in populated["clips"]:
        if c.get("portal_to_brain"):
            assert c.get("end_reference_image"), "Portal clip must retain End frame"
        else:
            assert c.get("end_reference_image") is None
            assert c.get("single_start_frame_lock") is True


def test_component3_acting_lexicon_and_rigid_physics_grammars() -> None:
    assert cfg.EXPRESSIVE_ACTING_LEXICON_PATH.is_file()
    lex = load_expression_acting_lexicon()
    archetypes = lex.get("expressions", lex.get("archetypes", lex))
    assert len(archetypes) == 12
    assert "expressive_reaction_closeup" in cfg.EXPRESSIVE_V8_VISUAL_GRAMMARS

    first_expr_id = next(iter(archetypes.keys()))
    clause = format_expression_acting_clause(first_expr_id, speaker_role="narrator", compact=True)
    assert "2D ink" in clause or "ink" in clause.lower()

    react_scene = ExpressiveReactionCloseupRule.compose(
        expression_id=first_expr_id,
        speaker_role="mini_cortex",
        compact=True,
    )
    assert "Bust-up close-up" in react_scene

    for rg in cfg.EXPRESSIVE_V8_RIGID_PHYSICS_GRAMMARS:
        phys_txt = ExpressiveRigidPhysicsRule.compose(rg, subject_or_structure="Subject", compact=True)
        assert len(phys_txt.split()) >= 8


def test_component3_camera_balance_and_edl_helpers() -> None:
    good_clips = []
    for idx in range(1, 21):
        if idx in (1, 2, 3, 4):
            cam = "fpv_dive_glide"
        elif idx in (5, 6, 7, 8):
            cam = "orbital_3d_arc_sweep"
        elif idx in (9, 10, 11, 12):
            cam = "locked_tripod"
        else:
            cam = "gentle_push_in"
        good_clips.append(
            {
                "clip_number": idx,
                "camera_move": cam,
                "grammar": "expressive_reaction_closeup" if idx == 9 else "expressive_vinyl_world",
                "portal_to_brain": (idx == 4),
            }
        )
    assert validate_v83_camera_and_acting_balance(good_clips) == []

    bad_clips = [dict(c) for c in good_clips]
    bad_clips[4]["portal_to_brain"] = True
    errs = validate_v83_camera_and_acting_balance(bad_clips)
    assert any("orbital_3d_arc_sweep" in e and "portal_to_brain" in e for e in errs)

    spans = [(0.0, 3.2), (3.2, 7.1), (7.1, 11.8)]
    vp = {"clips": [{"sentence_index": 1, "end_sentence_index": 1}, {"sentence_index": 2, "end_sentence_index": 3}]}
    locked_vp = lock_audio_durations_onto_visual_plan(vp, spans, enable_extended_durations=True)
    assert locked_vp["audio_before_flow_locked"] is True
    assert locked_vp["clips"][0]["render_sec"] == 4
    assert locked_vp["clips"][1]["render_sec"] == 10
    assert locked_vp["clips"][0]["forbid_slowmo_stretch"] is True

    beats = split_sentences_at_keyword_beats(
        [(0.0, 5.4)],
        ["The researcher promised a second marshmallow, but walked out and broke that promise."],
        target_beat_sec=2.0,
    )
    assert len(beats) >= 2
    w1, w2 = build_dual_harvest_edl_windows(8.0)
    assert w1[1] < w2[0]

    grad = np.linspace(20, 220, 64, dtype=np.uint8)
    img_a = np.dstack([np.tile(grad, (64, 1)), np.tile(grad[:, None], (1, 64)), np.full((64, 64), 110, dtype=np.uint8)])
    img_b = np.clip(img_a.astype(np.int16) + 2, 0, 255).astype(np.uint8)
    swap_res = verify_state_swap_hist_corr(img_a, img_b)
    assert swap_res["passed"] is True
    stamps = resolve_spatial_metric_stamps(
        {"spatial_metric_stamps": [{"label": "4x longer", "sentence_index": 2}]},
        spans,
    )
    assert stamps[0]["label"] == "4X LONGER"
    assert stamps[0]["start_sec"] == 3.2


def test_component3_studio_inventory_120s_fields() -> None:
    rep = StudioUploader.audit_v8_channel_readiness()
    inv = rep["format_inventory_audit"]
    assert "shorts_le_89_5s_count" in inv
    assert "v8_shorts_le_120s_count" in inv
    assert "legacy_gt_120s_count" in inv
