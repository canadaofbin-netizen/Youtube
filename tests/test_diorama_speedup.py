"""
Unit & regression tests for the 5-part Diorama Production Speed-Up Plan:
  1. Pre-flight Prosody & Contract Lock Mapping (`evaluate_prosody_gates_on_audio`, `_plan_lock_mapping_issues`)
  2. Flow <-> Assembly Pipelining (`parse_pipeline_specs`, `diorama_pipeline_runner`)
  3. Fail-fast QA ordering & Script-level AutoHeal guard (`_collect_auto_heal_plan`)
  4. Early abort after 2 consecutive `render_timeout`s + shared work-stealing queue (`_run_shard_worker`)
"""

from __future__ import annotations

import asyncio
import collections
import json
from pathlib import Path
from typing import Any

import pytest

from pipeline.config import PROJECTS_DIR
from pipeline.diorama_assembler import load_diorama_script_sentences
from pipeline.diorama_batch_orchestrator import _collect_auto_heal_plan, _plan_lock_mapping_issues
from pipeline.diorama_pipeline_runner import parse_pipeline_specs
from pipeline.dynamic_episode_qa import compile_episode_qa_contract
from pipeline.flow_prompt_builder import build_flow_prompts
from pipeline.prosody import evaluate_prosody_gates, evaluate_prosody_gates_on_audio


def test_preflight_prosody_matches_postassembly() -> None:
    ep16_dir = Path(PROJECTS_DIR) / "diorama_16_rizzolatti_mirror_neuron_empathy"
    if not (ep16_dir / "05_assembly" / "final_shorts_1080x1920.mp4").exists():
        pytest.skip("diorama_16_rizzolatti_mirror_neuron_empathy not assembled on disk")

    pre = evaluate_prosody_gates_on_audio(
        ep16_dir,
        gates=("P1", "P2", "P3", "P4", "P5", "P6"),
        run_asr=True,
    )
    post = evaluate_prosody_gates(ep16_dir, run_asr=True, save_report=False)

    expected_keys = (
        "P1_first_onset",
        "P2_hook_timing",
        "P3_gear_tempo",
        "P4_rush_breathless",
        "P5_stamp_beat",
        "P6_asr_by_gear",
    )
    assert set(pre["gates"].keys()) == set(expected_keys)
    for k in expected_keys:
        assert pre["gates"][k]["passed"] == post["gates"][k]["passed"], (
            f"Mismatch on {k}: pre={pre['gates'][k]} vs post={post['gates'][k]}"
        )
    assert pre["passed"] is True


def test_plan_lock_mapping_detects_ep16_dq3() -> None:
    ep16_dir = Path(PROJECTS_DIR) / "diorama_16_rizzolatti_mirror_neuron_empathy"
    if not (ep16_dir / "03_visuals" / "visual_plan.json").exists():
        pytest.skip("diorama_16 visual_plan.json not present")

    sentences, script_doc = load_diorama_script_sentences(ep16_dir)
    visual_plan = json.loads((ep16_dir / "03_visuals" / "visual_plan.json").read_text(encoding="utf-8"))
    rendered = build_flow_prompts(visual_plan, sentences)

    clean_contract = compile_episode_qa_contract(visual_plan, sentences, rendered, script_doc=script_doc)
    assert _plan_lock_mapping_issues(visual_plan, clean_contract, rendered_clips=rendered) == []

    # Replay pre-fix EP16 S19/S34 anatomy leak on non-brain primary cuts
    bad_sentences = list(sentences)
    bad_sentences[18] = "A single premotor cortex cell fired identically during watching and grasping."
    bad_sentences[33] = "Inside the premotor cortex, action observation lit up the motor circuit."
    bad_contract = compile_episode_qa_contract(visual_plan, bad_sentences, rendered, script_doc=script_doc)
    issues = _plan_lock_mapping_issues(visual_plan, bad_contract, rendered_clips=rendered)
    dq3_issues = [i for i in issues if "DQ3_anatomy_to_brain_sync" in i]
    assert len(dq3_issues) >= 2
    assert any("sentence 19" in i for i in dq3_issues)
    assert any("sentence 34" in i for i in dq3_issues)


def test_autoheal_skips_script_level_failures(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("pipeline.diorama_batch_orchestrator.PROJECTS_DIR", tmp_path)
    pid = "diorama_test_autoheal"
    asm_dir = tmp_path / pid / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)

    # Case 1: DQ3 failure must NOT trigger clip regeneration even if R64 also listed a clip
    (asm_dir / "dynamic_episode_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "gates": {
                    "DQ3_anatomy_to_brain_sync": {
                        "passed": False,
                        "failures": ["sentence 19 ('premotor cortex') mapped to lowpoly_macro_stage"],
                    },
                    "DQ8_zero_uncanny_skin_gore": {"passed": False, "skin_leak_cuts": [19]},
                },
            }
        ),
        encoding="utf-8",
    )
    (asm_dir / "posthoc_semantic_qa_report.json").write_text(
        json.dumps({"passed": False, "summary": {"regenerate_clip_indices": [19], "weak_cut_indices": [19]}, "cuts": []}),
        encoding="utf-8",
    )
    plan_dq3 = _collect_auto_heal_plan(pid)
    assert plan_dq3["script_fix_required"] is True
    assert plan_dq3["regenerate_clips"] == []

    # Case 2: Prosody failure must NOT trigger clip regeneration
    (asm_dir / "dynamic_episode_qa_report.json").unlink()
    (asm_dir / "prosody_qa_report.json").write_text(
        json.dumps({"passed": False, "gates": {"P6_asr_by_gear": {"passed": False}}}),
        encoding="utf-8",
    )
    plan_p6 = _collect_auto_heal_plan(pid)
    assert plan_p6["script_fix_required"] is True
    assert plan_p6["regenerate_clips"] == []

    # Case 3: Pure visual clip failure DOES trigger targeted clip regeneration
    (asm_dir / "prosody_qa_report.json").write_text(
        json.dumps({"passed": True, "gates": {"P6_asr_by_gear": {"passed": True}}}),
        encoding="utf-8",
    )
    plan_vis = _collect_auto_heal_plan(pid)
    assert plan_vis["script_fix_required"] is False
    assert plan_vis["regenerate_clips"] == [19]


def test_render_timeout_early_abort(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    import pipeline.flow_diorama_sharded_worker as sw

    fake_clock = {"t": 1000.0}

    def _fake_monotonic() -> float:
        return fake_clock["t"]

    async def _fast_sleep(sec: float) -> None:
        # Advance virtual monotonic clock on render polling sleep (4.5s) so 240s deadline expires immediately
        if sec >= 4.0:
            fake_clock["t"] += 250.0
        else:
            fake_clock["t"] += sec

    class _DummyCDPClient:
        def __init__(self, ws_url: str) -> None:
            self.ws_url = ws_url
            self.poll_mode = "timeout"

        async def __aenter__(self) -> "_DummyCDPClient":
            return self

        async def __aexit__(self, *args: Any) -> None:
            return None

        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

        async def eval(self, expr: str) -> Any:
            if "classifyTile" in expr and "hasNewSrc" in expr:
                c_mode = active_clip_mode["mode"]
                if c_mode == "timeout":
                    return {"ready": 0, "rendering": 1, "hasNewSrc": False, "topKey": "", "hadErr": False}
                return {"ready": 1, "rendering": 0, "hasNewSrc": True, "topKey": f"https://v/{fake_clock['t']}", "hadErr": False}
            if "classifyTile" in expr:
                return {"ready": 0, "rendering": 0, "srcs": [], "topKey": ""}
            return {}

    active_clip_mode = {"mode": "timeout"}
    submissions_by_clip: dict[int, int] = collections.Counter()

    async def _fake_alloc_tab(**kwargs: Any) -> dict[str, Any]:
        return {"tab_id": "tab12345678", "project_url": "https://labs.google/fx/project/test", "ws_url": "ws://dummy"}

    async def _fake_cfg_engine(*args: Any, **kwargs: Any) -> dict[str, Any]:
        return {"flow_model": "Veo 3.1 - Lite", "credit_tier": "zero_credit_fallback", "settings_summary": "ok"}

    async def _fake_submit(client: Any, prompt: str, *args: Any, **kwargs: Any) -> bool:
        c_num = 10 if "CLIP10" in prompt else 11
        submissions_by_clip[c_num] += 1
        active_clip_mode["mode"] = "timeout" if c_num == 10 else "ready"
        if kwargs.get("submission_meta_out") is not None:
            kwargs["submission_meta_out"]["flow_model"] = "Veo 3.1 - Lite"
            kwargs["submission_meta_out"]["credit_tier"] = "zero_credit_fallback"
        return True

    async def _fake_download(dst_mp4: Path, **kwargs: Any) -> dict[str, Any]:
        dst_mp4.write_bytes(b"0" * 400_000)
        return {"sha256": "abc123", "file_size_bytes": 400_000, "source_download_filename": dst_mp4.name}

    cv_calls = {"n": 0}

    def _fake_cv(path: Path, grammar: str, schema_ver: int) -> dict[str, Any]:
        cv_calls["n"] += 1
        # Fail CV 3 times on Clip 11, pass on try 4 -> proves CV retry budget (5 tries) is preserved!
        if cv_calls["n"] <= 3:
            return {"passed": False, "reason": "peach_ratio_exceeded"}
        return {"passed": True, "max_frame_diff": 8.0, "mean_luma": 180.0, "plaque_glyph_run": 0}

    monkeypatch.setattr(sw.time, "monotonic", _fake_monotonic)
    monkeypatch.setattr(sw.asyncio, "sleep", _fast_sleep)
    monkeypatch.setattr(sw, "DirectCDPClient", _DummyCDPClient)
    monkeypatch.setattr(sw, "allocate_dedicated_flow_project_tab", _fake_alloc_tab)
    monkeypatch.setattr(sw, "_configure_diorama_tab_engine", _fake_cfg_engine)
    monkeypatch.setattr(sw, "_submit_diorama_prompt_zero_credit", _fake_submit)
    monkeypatch.setattr(sw, "_download_newest_ready_tile", _fake_download)
    monkeypatch.setattr(sw, "inspect_diorama_clip_cv", _fake_cv)
    monkeypatch.setattr(sw, "_ensure_min_clip_size_if_needed", lambda p: None)

    q: collections.deque[dict[str, Any]] = collections.deque(
        [
            {"clip_number": 10, "grammar": "lowpoly_macro_stage", "prompt": "CLIP10 filter trigger", "schema_version": 7},
            {"clip_number": 11, "grammar": "lowpoly_macro_stage", "prompt": "CLIP11 healthy prompt", "schema_version": 7},
        ]
    )

    with pytest.raises(RuntimeError) as exc_info:
        asyncio.run(
            sw._run_shard_worker(
                shard_idx=1,
                shard_clips=[],
                project_id="test_proj",
                project_dir=tmp_path,
                short_ref_map={},
                tab_open_lock=asyncio.Lock(),
                opened_tabs=[],
                seen_global_shas=set(),
                shared_clip_queue=q,
            )
        )

    err_txt = str(exc_info.value)
    assert "Clip 10" in err_txt
    assert "prompt_rewrite_needed" in err_txt
    # Clip 10 aborted after 2 consecutive render_timeouts (not 5!)
    assert submissions_by_clip[10] == sw.MAX_CONSECUTIVE_RENDER_TIMEOUTS == 2
    # Clip 11 behind Clip 10 STILL ran, survived 3 CV failures, and succeeded on try 4!
    assert submissions_by_clip[11] == 4
    assert (tmp_path / "03_visuals" / "flow_native_clips" / "clip_11.mp4").exists()


def test_parse_pipeline_specs() -> None:
    specs = parse_pipeline_specs(
        "diorama_18_greene_trolley_dilemma_dual_process,"
        "delgado_stimoceiver_bull_stop:diorama_21_delgado_stimoceiver_bull:bci_tech"
    )
    assert len(specs) == 2
    assert specs[0]["slug"] == "greene_trolley_dilemma_dual_process"
    assert specs[0]["pillar"] == "bci_ethics"
    assert specs[1]["project_id"] == "diorama_21_delgado_stimoceiver_bull"
    assert specs[1]["slug"] == "delgado_stimoceiver_bull_stop"
    assert specs[1]["pillar"] == "bci_tech"
