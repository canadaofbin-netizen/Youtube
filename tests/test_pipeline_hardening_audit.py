"""
Hermetic Regression Suite for W1–W6 Full-Pipeline Hardening & Credit-Aware Dual-Tier Flow Engine.
Zero live CDP port 9222 connections and zero mutations under BCI_Shorts_Channel/projects/.
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import subprocess
from datetime import date
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

from pipeline import config as cfg


# ==============================================================================
# 1. Credit-Aware Dual-Tier Flow Engine (`Omni 1.1 Flash` -> `0-Credit` Fallback)
# ==============================================================================
def test_dual_tier_flow_engine_auto_fallback_and_zero_credit_safety(monkeypatch) -> None:
    from pipeline import flow_diorama_sharded_worker as fdsw
    from pipeline.flow_browser import (
        CHECK_CREDIT_EXHAUSTION_JS,
        DISMISS_CREDIT_DIALOG_JS,
        FLOW_TILE_CLASSIFIER_JS,
        FlowCircuitBreakerError,
    )

    assert cfg.FLOW_PRIMARY_VIDEO_MODEL == "Omni 1.1 Flash"
    assert cfg.FLOW_ZERO_CREDIT_MODEL == "Veo 3.1 - Lite [Lower Priority]"
    assert cfg.DEFAULT_FLOW_ENGINE_MODE == "auto"
    assert set(cfg.FLOW_ENGINE_MODES) == {"auto", "omni", "zero-credit"}

    # Guardrail: DISMISS_CREDIT_DIALOG_JS must NEVER auto-click top-up / billing links
    assert "add ai credits" in DISMISS_CREDIT_DIALOG_JS.lower()
    assert "__bci_flow_forbid_credit_approve" in DISMISS_CREDIT_DIALOG_JS
    assert "prompt-warning-button" in CHECK_CREDIT_EXHAUSTION_JS
    assert len(FLOW_TILE_CLASSIFIER_JS) > 100

    class _FakeCDPClient:
        def __init__(self, credits_exhausted: bool = False):
            self.credits_exhausted = credits_exhausted
            self.eval_log: list[str] = []
            self.active_family = "omni"

        async def eval(self, js: str) -> Any:
            self.eval_log.append(js)
            if "CHECK_CREDIT_EXHAUSTION" in js or "has_warning_btn" in js:
                return {"exhausted": self.credits_exhausted, "has_warning_btn": self.credits_exhausted}
            if "Boolean(document.querySelector('button.prompt-warning-button'))" in js:
                return False
            return {}

        async def send(self, method: str, params: dict[str, Any] | None = None) -> dict[str, Any]:
            return {}

    async def _fake_ensure_916(client, target_duration="8s", engine_mode="auto", credit_exhausted_event=None, force_recheck=False):
        if engine_mode == "zero-credit" or (credit_exhausted_event and credit_exhausted_event.is_set()):
            client.active_family = "veo_3_1_lite_low_priority"
            return {"flow_model": cfg.FLOW_ZERO_CREDIT_MODEL, "credit_tier": "zero_credit_fallback"}
        return {"flow_model": cfg.FLOW_PRIMARY_VIDEO_MODEL, "credit_tier": "omni_monthly_credit"}

    async def _fake_zero_lite(client, force=False):
        client.active_family = "veo_3_1_lite_low_priority"
        return "Veo 3.1 - Lite [Lower Priority] 0 credits"

    async def _fake_read_fam(client):
        return client.active_family

    monkeypatch.setattr(fdsw, "ensure_manual_video_916_mode", _fake_ensure_916)
    monkeypatch.setattr(fdsw, "_configure_zero_credit_veo_lite", _fake_zero_lite)
    monkeypatch.setattr(fdsw, "read_active_flow_model_family", _fake_read_fam)

    async def _exercise_modes() -> None:
        ev = asyncio.Event()
        # Case A: Credits available -> selects Omni 1.1 Flash
        c_ok = _FakeCDPClient(credits_exhausted=False)
        res_omni = await fdsw._configure_diorama_tab_engine(c_ok, engine_mode="auto", credit_exhausted_event=ev)
        assert res_omni["flow_model"] == cfg.FLOW_PRIMARY_VIDEO_MODEL
        assert res_omni["credit_tier"] == "omni_monthly_credit"
        assert not ev.is_set()

        # Case B: Credits exhausted mid-episode -> sets shared event & falls back to 0-credit Veo Lite
        c_low = _FakeCDPClient(credits_exhausted=True)
        res_fb = await fdsw._configure_diorama_tab_engine(c_low, engine_mode="auto", credit_exhausted_event=ev)
        assert res_fb["flow_model"] == cfg.FLOW_ZERO_CREDIT_MODEL
        assert res_fb["credit_tier"] == "zero_credit_fallback"
        assert res_fb["zero_credit_verified"] is True
        assert ev.is_set()

        # Case C: Sibling shard sees credit_exhausted_event already set -> immediately uses 0-credit Veo Lite
        c_sibling = _FakeCDPClient(credits_exhausted=False)
        res_sib = await fdsw._configure_diorama_tab_engine(c_sibling, engine_mode="auto", credit_exhausted_event=ev)
        assert res_sib["flow_model"] == cfg.FLOW_ZERO_CREDIT_MODEL
        assert res_sib["credit_tier"] == "zero_credit_fallback"

        # Case D: Strict --engine omni fails closed if credits are exhausted
        c_strict = _FakeCDPClient(credits_exhausted=True)
        with pytest.raises(FlowCircuitBreakerError):
            await fdsw._configure_diorama_tab_engine(
                c_strict, engine_mode="omni", credit_exhausted_event=asyncio.Event()
            )

    asyncio.run(_exercise_modes())


# ==============================================================================
# 2. Flow Browser Regex Import, Docker Bridge Safety & Async Harvest Lock
# ==============================================================================
def test_flow_browser_verify_v5_regex_and_async_harvest_lock(tmp_path: Path, monkeypatch) -> None:
    from pipeline import flow_browser as fb

    fake_projects = tmp_path / "projects"
    pid = "flow_v5_verify_smoke"
    clips_dir = fake_projects / pid / "03_visuals" / "flow_native_clips"
    clips_dir.mkdir(parents=True)
    monkeypatch.setattr(fb, "PROJECTS_DIR", fake_projects)

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    for idx in range(1, 6):
        out_mp4 = clips_dir / f"clip_{idx}.mp4"
        subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "testsrc=size=360x640:rate=24:duration=1.2",
                "-c:v", "libx264", "-preset", "ultrafast", "-b:v", "900k", "-minrate", "900k",
                "-pix_fmt", "yuv420p", str(out_mp4),
            ],
            check=True,
        )
        if out_mp4.stat().st_size < cfg.MIN_CLIP_SIZE_BYTES:
            with open(out_mp4, "ab") as fh:
                fh.write(b"\x00" * (cfg.MIN_CLIP_SIZE_BYTES - out_mp4.stat().st_size + 1024))

    rep = fb.GoogleFlowWhaleController.verify_flow_native_clips_v5(pid, deep_probe=False)
    assert rep["passed"] is True
    assert rep["valid_clips_count"] == 5

    # Concurrent async harvest lock must serialize cleanly via `async with` without deadlocking
    lock_file = tmp_path / "harvest.lock"
    order: list[str] = []

    async def _run_locks() -> None:
        async def _worker(tag: str) -> None:
            async with fb.FlowDownloadHarvestLock(lock_path=lock_file, timeout_sec=5.0):
                order.append(f"{tag}_in")
                await asyncio.sleep(0.04)
                order.append(f"{tag}_out")

        await asyncio.gather(_worker("A"), _worker("B"))

    asyncio.run(_run_locks())
    assert order in (["A_in", "A_out", "B_in", "B_out"], ["B_in", "B_out", "A_in", "A_out"])


# ==============================================================================
# 3. VideoAutopsyEngine v2 Audio Harshness Tear, LUFS & Dedup Time Import
# ==============================================================================
def test_video_autopsy_audio_harshness_lufs_and_dedup_time_import(tmp_path: Path) -> None:
    import wave

    from pipeline.video_autopsy import VideoAutopsyEngine

    sr = 48000
    t = np.arange(int(2.4 * sr), dtype=np.float32) / float(sr)
    # Speech-like syllable cadence (350ms voiced / 150ms breath gap) so dynamic range >= 15 dB
    gate = ((np.mod(t, 0.50) < 0.35)).astype(np.float32)
    clean_pcm = gate * (0.24 * np.sin(2.0 * np.pi * 165.0 * t) + 0.12 * np.sin(2.0 * np.pi * 330.0 * t))
    harsh_pcm = gate * (0.06 * np.sin(2.0 * np.pi * 165.0 * t) + 0.58 * np.sin(2.0 * np.pi * 6800.0 * t))

    ff = imageio_ffmpeg.get_ffmpeg_exe()
    for name, pcm_arr in (("clean", clean_pcm), ("harsh", harsh_pcm)):
        wav_p = tmp_path / f"{name}.wav"
        mp4_p = tmp_path / f"{name}.mp4"
        with wave.open(str(wav_p), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes((np.clip(pcm_arr, -0.98, 0.98) * 32767.0).astype(np.int16).tobytes())
        subprocess.run(
            [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-f", "lavfi", "-i", "color=c=#b8c9d9:s=360x640:r=24:d=2.4",
                "-i", str(wav_p),
                "-c:v", "libx264", "-preset", "ultrafast", "-pix_fmt", "yuv420p",
                "-c:a", "aac", "-b:a", "192k", str(mp4_p),
            ],
            check=True,
        )

    clean_aud = VideoAutopsyEngine.inspect_audio_stream(tmp_path / "clean.mp4")
    assert clean_aud["sibilance_tear_detected"] is False
    assert clean_aud["integrated_lufs"] is not None

    harsh_aud = VideoAutopsyEngine.inspect_audio_stream(tmp_path / "harsh.mp4")
    assert harsh_aud["sibilance_tear_detected"] is True
    assert harsh_aud["sibilance_to_body_rms_ratio"] > cfg.AUDIO_MAX_SIBILANCE_ENERGY_RATIO

    # Verify inspect_thumbnails_and_dedup runs cleanly with `import time` (including cross-project scan)
    p_dir = tmp_path / "dedup_proj"
    (p_dir / "06_publish").mkdir(parents=True)
    for i, nm in enumerate(("thumbnail_var_A.png", "thumbnail_var_B.png", "thumbnail_var_C.png")):
        img = np.full((320, 180, 3), 30 + 85 * i, dtype=np.uint8)
        cv2.imwrite(str(p_dir / "06_publish" / nm), img)
    dedup_rep = VideoAutopsyEngine.inspect_thumbnails_and_dedup(p_dir)
    assert dedup_rep["thumbnails_distinct"] is True


# ==============================================================================
# 4. Pre-Upload QA Bundle & R64 Semantic Review Lock (`uploader` & `qa_gates`)
# ==============================================================================
def test_publish_ready_qa_bundle_and_r64_upload_lock(tmp_path: Path) -> None:
    from pipeline.qa_gates import verify_publish_ready_qa_bundle as qg_verify
    from pipeline.storage import ProjectStorage
    from pipeline.studio.uploader import verify_publish_ready_qa_bundle as up_verify

    projects_root = tmp_path / "projects"
    storage = ProjectStorage("diorama_upload_gate_case", title="Upload Gate Test", pillar="brain_history", projects_dir=projects_root)
    p_dir = storage.project_dir

    vp_file = storage.get_stage_dir("03_visuals") / "visual_plan.json"
    vp_file.write_text(json.dumps({"schema": 7, "profile": "neuro_diorama", "style_profile": "lowpoly_pastel_v7"}), encoding="utf-8")
    storage.record_artifact("03_visuals", "visual_plan.json", vp_file)

    asm_dir = storage.get_stage_dir("05_assembly")
    final_mp4 = asm_dir / "final_shorts_1080x1920.mp4"
    final_mp4.write_bytes(b"MP4DATA" * 350_000)  # > 2MB
    mp4_sha = hashlib.sha256(final_mp4.read_bytes()).hexdigest()

    edl_path = asm_dir / "edit_decision_list.json"
    edl_path.write_text(json.dumps({"schema": 7, "cuts": [{"cut_index": 1, "clip_index": 1}]}), encoding="utf-8")
    edl_sha = hashlib.sha256(edl_path.read_bytes()).hexdigest()

    autopsy_path = asm_dir / "video_autopsy_report.json"
    autopsy_path.write_text(json.dumps({"passed": True, "final_mp4_sha256": mp4_sha}), encoding="utf-8")

    dq_path = asm_dir / "dynamic_episode_qa_report.json"
    dq_path.write_text(json.dumps({"passed": True, "final_mp4_sha256": mp4_sha}), encoding="utf-8")

    ph_path = asm_dir / cfg.POSTHOC_SEMANTIC_QA_REPORT_FILENAME
    ph_path.write_text(
        json.dumps({"passed": True, "final_mp4_sha256": mp4_sha, "edl_sha256": edl_sha, "cut_count": 1, "cuts": [{"cut_index": 1}]}),
        encoding="utf-8",
    )
    for fn in (
        "final_shorts_1080x1920.mp4",
        "edit_decision_list.json",
        "video_autopsy_report.json",
        "dynamic_episode_qa_report.json",
        cfg.POSTHOC_SEMANTIC_QA_REPORT_FILENAME,
    ):
        storage.record_artifact("05_assembly", fn, asm_dir / fn)

    # Without posthoc_semantic_review.json -> MUST block when require_semantic_review=True, pass when False
    res_no_rev = up_verify(p_dir, require_semantic_review=True)
    assert res_no_rev["passed"] is False
    assert any("posthoc_semantic_review" in x for x in res_no_rev["issues"])
    assert up_verify(p_dir, require_semantic_review=False)["passed"] is True

    # Write valid R64 SHA-bound posthoc_semantic_review.json -> BOTH verifiers pass!
    rev_path = asm_dir / cfg.POSTHOC_SEMANTIC_REVIEW_FILENAME
    rev_path.write_text(
        json.dumps(
            {
                "project_id": p_dir.name,
                "schema": "R64_posthoc_semantic_review_v1",
                "review_origin": "manual_or_vlm_template",
                "final_mp4_sha256": mp4_sha,
                "edl_sha256": edl_sha,
                "cut_count": 1,
                "cuts": [
                    {
                        "cut_index": 1,
                        "clip_index": 1,
                        "auto_populated": False,
                        "expresses_intended_meaning": True,
                        "action_needed": "none",
                        "observed_visual_summary": "Low-poly railroad workers lift heavy iron rail cleanly in daylight.",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    storage.record_artifact("05_assembly", cfg.POSTHOC_SEMANTIC_REVIEW_FILENAME, rev_path)

    assert up_verify(p_dir, require_semantic_review=True)["passed"] is True
    assert qg_verify(p_dir, require_r64_review=True)["passed"] is True

    # Mutating MP4 invalidates SHA-256 -> MUST fail closed immediately
    final_mp4.write_bytes(b"MUTATED" * 350_000)
    assert up_verify(p_dir, require_semantic_review=True)["passed"] is False
    assert qg_verify(p_dir, require_r64_review=True)["passed"] is False


# ==============================================================================
# 5. Slot 4 `19:30 ET` Unification & US DST (`EDT` vs `EST`) KST Conversion
# ==============================================================================
def test_slot_4_2000_et_and_us_dst_kst_conversion() -> None:
    from pipeline.studio.config import SLOT_TIMETABLE, slot_time_kst_label, slot_time_kst_parts

    assert SLOT_TIMETABLE[4]["hour_et"] == 19
    assert SLOT_TIMETABLE[4]["minute_et"] == 30
    assert SLOT_TIMETABLE[4]["time_et"] == "19:30"
    assert SLOT_TIMETABLE[4]["time_et_12h"] == "7:30 PM"

    # Oct 30, 2026 is US EDT (UTC-4) -> +13h to KST (UTC+9): 19:30 ET == 08:30 KST (+1d)
    assert slot_time_kst_parts(19, 30, ref_date=date(2026, 10, 30)) == ("08:30", 1)
    assert slot_time_kst_label(19, 30, ref_date=date(2026, 10, 30)) == "08:30 KST (+1d)"

    # Nov 2, 2026 is US EST (UTC-5 after Nov 1 DST fallback) -> +14h to KST: 19:30 ET == 09:30 KST (+1d)
    assert slot_time_kst_parts(19, 30, ref_date=date(2026, 11, 2)) == ("09:30", 1)
    assert slot_time_kst_label(19, 30, ref_date=date(2026, 11, 2)) == "09:30 KST (+1d)"


# ==============================================================================
# 6. Voice Fallback Mapping, `0.0 Hz` F0 Detection & Linux FUSE Atomic Storage
# ==============================================================================
def test_voice_fallback_kokoro_mapping_f0_zero_and_fuse_atomic_storage(tmp_path: Path) -> None:
    from pipeline.storage import ProjectStorage
    from pipeline.voice_consistency import evaluate_f0_series
    from pipeline.voice_fallback import _resolve_kokoro_voice

    assert _resolve_kokoro_voice("en-US-AndrewMultilingualNeural") == cfg.VOICE_FALLBACK_VOICE
    assert _resolve_kokoro_voice("") == cfg.VOICE_FALLBACK_VOICE
    assert _resolve_kokoro_voice("am_fenrir") == "am_fenrir"

    f0_rep = evaluate_f0_series([132.0, 0.0, 134.5, 131.0])
    assert f0_rep["passed"] is False
    assert 2 in f0_rep["regenerate_clips"]
    assert 2 in f0_rep["unvoiced_outliers"]

    st = ProjectStorage("fuse_atomic_case", title="FUSE Atomic", pillar="bci_tech", projects_dir=tmp_path / "projects")
    p_json = st.save_json("02_script", "script.json", {"hello": "world", "count": 42})
    assert p_json.exists()
    assert not list(p_json.parent.glob(".tmp_*"))
    assert st.verify_integrity()["all_intact"] is True


# ==============================================================================
# 7. Gear 1–2 DOI/Vault Word Boundaries, Display Numerals, Punctuation & ABTest
# ==============================================================================
def test_gear12_doi_integrity_word_boundaries_display_numerals_and_studio_guards(tmp_path: Path) -> None:
    from pipeline.depiction_rules import DioramaV7PromptComposer, LowPolyWorldRule
    from pipeline.plain_language import to_display_text
    from pipeline.researcher import TopicResearcher
    from pipeline.storage import ProjectStorage
    from pipeline.studio.ab_tester import ThumbnailABTester

    researcher = TopicResearcher()
    # "rubber hand illusion" shares only the generic word "hand" with "alien hand" in split_brain_1962 -> must NOT match split_brain_1962
    vault_hit = researcher.match_historical_vault("rubber hand illusion body ownership")
    assert vault_hit is None or vault_hit["id"] != "split_brain_1962"

    # Single-digit measurement units convert cleanly to compact subtitle numerals
    disp = to_display_text("The rod flew six feet in three seconds across two rooms.")
    assert "6 feet" in disp
    assert "3 seconds" in disp

    # DioramaV7PromptComposer preserves clean sentence periods without '..' or ', .'
    world_sc = LowPolyWorldRule.compose(
        "a sunlit Vermont granite cut.",
        "clothed low-poly workers lift iron rails.",
    )
    composed = DioramaV7PromptComposer.compose_clip_prompt(world_sc, "lowpoly_fullbleed_world", "locked_tripod")
    assert ".." not in composed
    assert ", ." not in composed

    # Live-mode ThumbnailABTester must return awaiting_real_metrics when impressions == 0 (never fake demo clicks)
    projects_root = tmp_path / "projects"
    st = ProjectStorage("ab_live_guard", title="AB Guard", pillar="brain_health", projects_dir=projects_root)
    st.save_json(
        "06_publish",
        "ab_test_manifest.json",
        {
            "project_id": "ab_live_guard",
            "current_active_variant": "A",
            "variants": {
                "A": {"impressions": 0, "clicks": 0},
                "B": {"impressions": 0, "clicks": 0},
                "C": {"impressions": 0, "clicks": 0},
            },
        },
    )
    tester = ThumbnailABTester(cdp_port=9222, projects_dir=projects_root)
    live_res = tester.evaluate_significance("ab_live_guard", dry_run=False)
    assert live_res["status"] == "awaiting_real_metrics"
    assert live_res["winner_variant"] is None


# ==============================================================================
# 8. Batch Orchestrator Smart Auto-Heal (`shift_edl_source_window` vs Regen)
# ==============================================================================
def test_batch_orchestrator_smart_auto_heal_plan_separates_edl_vs_regen(tmp_path: Path, monkeypatch) -> None:
    from pipeline import diorama_batch_orchestrator as dbo

    fake_projects = tmp_path / "projects"
    pid = "diorama_heal_case"
    asm_dir = fake_projects / pid / "05_assembly"
    asm_dir.mkdir(parents=True)
    monkeypatch.setattr(dbo, "PROJECTS_DIR", fake_projects)

    (asm_dir / "edit_decision_list.json").write_text(
        json.dumps(
            {
                "cuts": [
                    {"cut_index": 1, "clip_index": 4, "mode": "single"},
                    {"cut_index": 2, "clip_index": 9, "right_clip_index": 10, "mode": "split_hstack"},
                ]
            }
        ),
        encoding="utf-8",
    )

    # Case 1: Only `shift_edl_source_window` needed -> preserve Flow clips (`rebuild_only == True`, `regenerate_clips == []`)
    (asm_dir / "dynamic_episode_qa_report.json").write_text(json.dumps({"passed": True, "gates": {}}), encoding="utf-8")
    (asm_dir / "posthoc_semantic_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "summary": {
                    "weak_cut_indices": [1],
                    "regenerate_clip_indices": [],
                },
                "cuts": [
                    {
                        "cut_index": 1,
                        "passed": False,
                        "remediation_action": "shift_edl_source_window",
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_edl = dbo._collect_auto_heal_plan(pid)
    assert plan_edl["rebuild_only"] is True
    assert plan_edl["regenerate_clips"] == []
    assert plan_edl["edl_only_cuts"] == [1]

    # Case 2: DQ5 impact defect + single-pane split_hstack regeneration -> regenerates only offending clips
    (asm_dir / "dynamic_episode_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "gates": {
                    "DQ5_cold_open_and_impact": {
                        "passed": False,
                        "failed_locks": [{"clip_number": 2}],
                    }
                },
            }
        ),
        encoding="utf-8",
    )
    (asm_dir / "posthoc_semantic_qa_report.json").write_text(
        json.dumps(
            {
                "passed": False,
                "summary": {
                    "weak_cut_indices": [2],
                    "regenerate_clip_indices": [],
                },
                "cuts": [
                    {
                        "cut_index": 2,
                        "passed": False,
                        "remediation_action": "regenerate_flow_clip",
                        "source_clip_attribution": {
                            "regenerate_clip_indices": [10],
                        },
                    }
                ],
            }
        ),
        encoding="utf-8",
    )
    plan_regen = dbo._collect_auto_heal_plan(pid)
    assert plan_regen["rebuild_only"] is False
    assert plan_regen["regenerate_clips"] == [2, 10]
