"""Unit tests for credit-safe Google Flow routing, prompt lint, previs contact sheets, and ElevenLabs v4 TTS."""

from __future__ import annotations

import base64
import json
import subprocess
from pathlib import Path
from typing import Any
from unittest.mock import patch

import cv2
import imageio_ffmpeg
import numpy as np

from pipeline.config import (
    DIORAMA_VOICE_PRESETS,
    FLOW_OMNI_EPISODE_CREDIT_CAP,
    FLOW_OMNI_HERO_MAX_CLIPS,
    FLOW_OMNI_MAX_ATTEMPTS_PER_CLIP,
)
from pipeline.diorama_batch_orchestrator import render_keyframe_contact_sheet
from pipeline.elevenlabs_tts import (
    extract_word_timestamps_from_alignment,
    format_v4_tagged_sentence,
    is_episode_fully_cached,
    load_elevenlabs_api_key,
    synthesize_elevenlabs_v4_episode,
)
from pipeline.flow_diorama_sharded_worker import resolve_effective_clip_engine_mode
from pipeline.flow_prompt_builder import (
    assign_hero_omni_engines,
    normalize_clip_engine_tag,
    validate_flow_credit_safety_lint,
)


def _tiny_sine_mp3_bytes(duration_sec: float = 0.35, sr: int = 44100) -> bytes:
    t = np.linspace(0.0, duration_sec, int(sr * duration_sec), endpoint=False, dtype=np.float32)
    pcm = (0.15 * np.sin(2.0 * np.pi * 220.0 * t)).astype(np.float32)
    res = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "f32le",
            "-ar",
            str(sr),
            "-ac",
            "1",
            "-i",
            "pipe:0",
            "-c:a",
            "libmp3lame",
            "-b:a",
            "192k",
            "-f",
            "mp3",
            "pipe:1",
        ],
        input=pcm.tobytes(),
        capture_output=True,
        check=True,
        timeout=20,
    )
    return res.stdout


def test_task1_hero_omni_engine_assignment_and_caps() -> None:
    assert FLOW_OMNI_EPISODE_CREDIT_CAP == 200
    assert FLOW_OMNI_HERO_MAX_CLIPS == 8
    assert FLOW_OMNI_MAX_ATTEMPTS_PER_CLIP == 2
    assert normalize_clip_engine_tag("Veo-Lite") == "zero-credit"
    assert normalize_clip_engine_tag("OMNI") == "omni"
    assert normalize_clip_engine_tag("invalid_value") == "auto"

    plan = {
        "omni_tier": "hero",
        "clips": [
            {
                "clip_number": idx,
                "act": (1 if idx <= 2 else (6 if idx == 20 else 3)),
                "grammar": ("expressive_xray_brain" if idx in (7, 12, 16) else "expressive_vinyl_world"),
                "cameo_easter_egg": bool(idx == 10),
            }
            for idx in range(1, 21)
        ],
    }
    assigned = assign_hero_omni_engines(plan, max_hero_clips=8)
    omni_indices = [k for k, v in assigned.items() if v == "omni"]
    zero_indices = [k for k, v in assigned.items() if v == "zero-credit"]
    assert 1 <= len(omni_indices) <= 8
    assert len(omni_indices) + len(zero_indices) == 20
    assert 1 in omni_indices and 20 in omni_indices and 10 in omni_indices

    # Runtime retry + episode budget demotion
    mode0, reason0 = resolve_effective_clip_engine_mode(
        "auto", "omni", omni_attempts_for_clip=0, episode_omni_credits_spent=160
    )
    assert mode0 == "omni" and reason0 is None

    mode_retry_cap, reason_retry = resolve_effective_clip_engine_mode(
        "auto", "omni", omni_attempts_for_clip=2, episode_omni_credits_spent=40
    )
    assert mode_retry_cap == "zero-credit"
    assert reason_retry and "omni_retry_cap_reached" in reason_retry

    mode_ep_cap, reason_ep = resolve_effective_clip_engine_mode(
        "auto", "omni", omni_attempts_for_clip=0, episode_omni_credits_spent=200
    )
    assert mode_ep_cap == "zero-credit"
    assert reason_ep and "episode_omni_cap_reached" in reason_ep

    mode_zc, _ = resolve_effective_clip_engine_mode(
        "auto", "zero-credit", omni_attempts_for_clip=0, episode_omni_credits_spent=0
    )
    assert mode_zc == "zero-credit"


def test_task2_flow_credit_safety_lint_catches_veo_and_yunet_traps() -> None:
    bad_clips = [
        {
            "clip_number": 4,
            "scene": "A small child waits alone behind a closed door inside an isolated room.",
            "engine": "omni",
        },
        {
            "clip_number": 13,
            "scene": "Warm afternoon sunbeams stream directly behind the porcelain head against a peach wall.",
            "engine": "zero-credit",
        },
    ]
    errs = validate_flow_credit_safety_lint({"clips": []}, clips=bad_clips)
    joined = "\n".join(errs)
    assert "minor_isolation_filter_risk" in joined
    assert "skin_tone_head_backdrop_risk" in joined

    clean_clips = [
        {
            "clip_number": 4,
            "scene": "Through a wide glass observation window, a vinyl figure sits calmly beside a bright hallway researcher.",
            "engine": "omni",
        },
        {
            "clip_number": 13,
            "scene": "Crisp cool slate-blue studio daylight frames the matte-white vinyl head cleanly.",
            "engine": "zero-credit",
        },
    ]
    assert validate_flow_credit_safety_lint({"clips": []}, clips=clean_clips) == []


def test_task3_stop_after_cli_and_keyframe_contact_sheet(tmp_path: Path) -> None:
    cli_src = Path("pipeline/cli.py").read_text(encoding="utf-8")
    assert '"--stop-after"' in cli_src
    assert 'choices=["audio", "keyframes"]' in cli_src

    proj = tmp_path / "proj_kf"
    ref_dir = proj / "03_visuals" / "reference_images"
    ref_dir.mkdir(parents=True)
    for idx in range(1, 5):
        img = np.full((320, 180, 3), 235, dtype=np.uint8)
        cv2.imwrite(str(ref_dir / f"kf_{idx:02d}_start_9x16.png"), img)
    sheet_path = render_keyframe_contact_sheet(proj)
    assert sheet_path is not None and sheet_path.exists()
    assert sheet_path.name == "keyframe_contact_sheet.jpg"
    assert sheet_path.stat().st_size > 1000


def test_task4_elevenlabs_v4_cache_stitching_and_alignment(tmp_path: Path) -> None:
    assert "elevenlabs_v4" in DIORAMA_VOICE_PRESETS
    assert "elevenlabs_v4_male" in DIORAMA_VOICE_PRESETS

    env_file = tmp_path / "elevenlabs.env"
    env_file.write_text('XI_API_KEY="test_dummy_key_value"\n', encoding="utf-8")
    with patch.dict("os.environ", {"XI_API_KEY": "", "ELEVENLABS_API_KEY": ""}, clear=False):
        assert load_elevenlabs_api_key(env_path=env_file) == "test_dummy_key_value"

    tagged_rush = format_v4_tagged_sentence("Wait right there!", gear="rush")
    assert tagged_rush.startswith("[brisk, urgent voice]")
    tagged_stamp = format_v4_tagged_sentence("Trust wired the brake.", gear="stamp")
    assert tagged_stamp.startswith("[measured, deliberate voice]")

    sample_text = "[brisk, urgent voice] Brain brake!"
    fake_align = {
        "characters": list(sample_text),
        "character_start_times_seconds": [round(i * 0.03, 3) for i in range(len(sample_text))],
        "character_end_times_seconds": [round((i + 1) * 0.03, 3) for i in range(len(sample_text))],
    }
    words = extract_word_timestamps_from_alignment(fake_align)
    assert [w for _, _, w in words] == ["Brain", "brake!"]

    mp3_b64 = base64.b64encode(_tiny_sine_mp3_bytes()).decode("ascii")
    http_calls: list[tuple[str, dict[str, Any] | None]] = []

    class _FakeResp:
        def __init__(self, body_obj: dict[str, Any], headers: dict[str, str] | None = None) -> None:
            self._raw = json.dumps(body_obj).encode("utf-8")
            self.headers = headers or {}

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: float = 30.0) -> _FakeResp:
        url = req.full_url
        payload = json.loads(req.data.decode("utf-8")) if req.data else None
        http_calls.append((url, payload))
        if "/v1/user/subscription" in url:
            return _FakeResp(
                {
                    "tier": "creator",
                    "status": "active",
                    "character_count": 300,
                    "character_limit": 131000,
                }
            )
        req_idx = sum(1 for u, _ in http_calls if "/with-timestamps" in u)
        txt = str((payload or {}).get("text") or "Hello world.")
        al = {
            "characters": list(txt),
            "character_start_times_seconds": [round(i * 0.02, 3) for i in range(len(txt))],
            "character_end_times_seconds": [round((i + 1) * 0.02, 3) for i in range(len(txt))],
        }
        return _FakeResp(
            {"audio_base64": mp3_b64, "normalized_alignment": al},
            headers={"request-id": f"req_{req_idx}", "character-cost": str(len(txt))},
        )

    cache_dir = tmp_path / "el_cache"
    sents = ["One marshmallow sits on the tray!", "Yet half the kids grab it fast.", "Trust changes the circuit."]
    gears = ["rush", "steady", "stamp"]

    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        res1 = synthesize_elevenlabs_v4_episode(
            sents,
            gears=gears,
            cache_dir=cache_dir,
            env_path=env_file,
        )
        assert res1["characters_used"] > 0
        assert len(res1["pcms"]) == 3
        assert is_episode_fully_cached(
            sents,
            voice_id=DIORAMA_VOICE_PRESETS["elevenlabs_v4"]["elevenlabs_voice_id"],
            gears=gears,
            cache_dir=cache_dir,
        )

        calls_after_first = len(http_calls)
        # Second call: 100% cache hit -> 0 HTTP requests, 0 credits billed
        res2 = synthesize_elevenlabs_v4_episode(
            sents,
            gears=gears,
            cache_dir=cache_dir,
            env_path=env_file,
        )
        assert res2["characters_used"] == 0
        assert len(http_calls) == calls_after_first

        # Surgical single-sentence regen of middle sentence (#2): passes both previous_request_ids and next_request_ids!
        res3 = synthesize_elevenlabs_v4_episode(
            sents,
            gears=gears,
            force_refresh_indices={2},
            cache_dir=cache_dir,
            env_path=env_file,
        )
        assert res3["characters_used"] > 0
        tts_payloads = [p for u, p in http_calls[calls_after_first:] if "/with-timestamps" in u and p]
        assert len(tts_payloads) == 1
        assert tts_payloads[0].get("previous_request_ids") == ["req_1"]
        assert tts_payloads[0].get("next_request_ids") == ["req_3"]


def test_task5_three_voice_repertory_cast_routing_and_per_speaker_continuity(tmp_path: Path) -> None:
    from pipeline.elevenlabs_tts import load_cast_registry

    reg = load_cast_registry()
    cast = reg["cast"]
    assert cast["narrator"]["elevenlabs_voice_id"] == "eXpIbVcVbLo8ZJQDlDnl"
    assert cast["researcher"]["elevenlabs_voice_id"] == "tnSpp4vdxKPjI9w0GnoV"
    assert cast["mini_cortex"]["elevenlabs_voice_id"] == "FGY2WhTYpPnrIDTdsKH5"

    env_file = tmp_path / "elevenlabs.env"
    env_file.write_text('XI_API_KEY="test_dummy_key_value"\n', encoding="utf-8")
    mp3_b64 = base64.b64encode(_tiny_sine_mp3_bytes()).decode("ascii")
    calls: list[tuple[str, dict[str, Any] | None]] = []

    class _FakeResp:
        def __init__(self, body_obj: dict[str, Any], headers: dict[str, str] | None = None) -> None:
            self._raw = json.dumps(body_obj).encode("utf-8")
            self.headers = headers or {}

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> "_FakeResp":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def _fake_urlopen(req: Any, timeout: float = 30.0) -> _FakeResp:
        url = req.full_url
        payload = json.loads(req.data.decode("utf-8")) if req.data else None
        calls.append((url, payload))
        if "/v1/user/subscription" in url:
            return _FakeResp({"tier": "creator", "status": "active", "character_count": 100, "character_limit": 131000})
        idx = sum(1 for u, _ in calls if "/with-timestamps" in u)
        txt = str((payload or {}).get("text") or "Hi.")
        al = {
            "characters": list(txt),
            "character_start_times_seconds": [round(i * 0.02, 3) for i in range(len(txt))],
            "character_end_times_seconds": [round((i + 1) * 0.02, 3) for i in range(len(txt))],
        }
        return _FakeResp(
            {"audio_base64": mp3_b64, "normalized_alignment": al},
            headers={"request-id": f"r_{idx}", "character-cost": str(len(txt))},
        )

    sents = [
        "Narrator sets the scene.",
        "If you wait fifteen minutes, you get two.",
        "Hold on! Could the adult be untrustworthy?",
        "Narrator reveals the fourfold jump.",
    ]
    speaker_voice_by_idx = {
        1: cast["narrator"]["elevenlabs_voice_id"],
        2: cast["researcher"]["elevenlabs_voice_id"],
        3: cast["mini_cortex"]["elevenlabs_voice_id"],
        4: cast["narrator"]["elevenlabs_voice_id"],
    }
    cache_dir = tmp_path / "cast_cache"
    with patch("urllib.request.urlopen", side_effect=_fake_urlopen):
        out = synthesize_elevenlabs_v4_episode(
            sents,
            gears=["brisk", "brisk", "rush", "stamp"],
            speaker_voice_by_idx=speaker_voice_by_idx,
            cache_dir=cache_dir,
            env_path=env_file,
        )
        assert out["used_voices_by_idx"] == speaker_voice_by_idx
        tts_calls = [(u, p) for u, p in calls if "/with-timestamps" in u and p]
        assert len(tts_calls) == 4
        assert cast["narrator"]["elevenlabs_voice_id"] in tts_calls[0][0]
        assert cast["researcher"]["elevenlabs_voice_id"] in tts_calls[1][0]
        assert cast["mini_cortex"]["elevenlabs_voice_id"] in tts_calls[2][0]
        # Sentence 4 (Narrator) must continue from Sentence 1's narrator request_id (r_1), NOT Laura's r_3!
        assert tts_calls[3][1].get("previous_request_ids") == ["r_1"]
        assert is_episode_fully_cached(
            sents,
            gears=["brisk", "brisk", "rush", "stamp"],
            speaker_voice_by_idx=speaker_voice_by_idx,
            cache_dir=cache_dir,
        )


def test_task6_prompt_diet_strips_ui_boilerplate() -> None:
    from pipeline.config import EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    from pipeline.depiction_rules import ExpressiveV8PromptComposer, FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD

    prompt = ExpressiveV8PromptComposer.compose_clip_prompt(
        scene_body=(
            "swings open the oak door and spreads two empty four-fingered matte-white palms above the bare table, "
            "and the seated figure's charcoal-black 2D ink eyebrows drop in startled disappointment"
        ),
        grammar="expressive_vinyl_world",
        camera_move="dolly_zoom_vertigo",
        transition_out="dissolve_8f",
        keyframe_bridge_clause="Bridges opening eye level medium frame smoothly into closing high angle 3q frame",
        context_split=True,
    )
    assert "8s vertical video" not in prompt
    assert "Bridges opening" not in prompt
    assert "Settles smoothly" not in prompt
    prompt_core = prompt.replace(FLOW_CAMERA_HARDWARE_NEGATIVE_GUARD, "").strip()
    assert prompt_core.endswith("Silent voice track.")
    wc = len(prompt_core.split())
    lo, hi = EXPRESSIVE_V8_CONTEXT_SPLIT_WORDS_RANGE
    assert lo <= wc <= hi, f"Prompt Diet word count {wc} outside {(lo, hi)}: {prompt_core}"


def test_task7_r70_data_stamp_validation_and_rgba_rendering() -> None:
    from pipeline.data_stamp_overlay import render_data_stamp_rgba_frame, validate_data_stamps

    sents = [
        "In 2013 at the University of Rochester, researchers broke a promise to four-year-olds right before the Marshmallow Test!",
        "In the real Rochester study, children who trusted the adult waited four times longer — jumping from three minutes to twelve full minutes!",
    ]
    valid_stamp = [
        {
            "sentence_index": 2,
            "chart": "bar_compare",
            "title": "AVERAGE WAIT TIME",
            "bars": [
                {"label": "Broken Promise", "value": 3, "unit": "min"},
                {"label": "Kept Promise", "value": 12, "unit": "min"},
            ],
            "multiplier_badge": "×4 LONGER",
            "source_citation": "Kidd et al., 2013 · n=28",
            "doi": "10.1016/j.cognition.2012.08.004",
        }
    ]
    assert validate_data_stamps({"data_stamps": valid_stamp}, sentences=sents) == []

    # Missing DOI or mismatched number -> flagged
    bad_stamp = [dict(valid_stamp[0], doi="")]
    assert any("DOI" in x or "doi" in x for x in validate_data_stamps({"data_stamps": bad_stamp}, sentences=sents))
    mismatch_stamp = [
        dict(
            valid_stamp[0],
            bars=[
                {"label": "Broken Promise", "value": 98, "unit": "min"},
                {"label": "Kept Promise", "value": 99, "unit": "min"},
            ],
        )
    ]
    assert any("match" in x.lower() or "98" in x or "99" in x for x in validate_data_stamps({"data_stamps": mismatch_stamp}, sentences=sents))

    frame = np.asarray(render_data_stamp_rgba_frame(valid_stamp[0], 1.8, 2.5, width=1080, height=1920))
    assert frame.shape == (1920, 1080, 4)
    # HERO v2 spans Y=10..62% with zero bleed into bottom subtitle zone Y >= 65%
    assert int(frame[int(1920 * 0.12) : int(1920 * 0.58), :, 3].max()) > 200
    assert int(frame[int(1920 * 0.65) :, :, 3].max()) == 0


def test_task8_previs_refinements_e1_to_e8(tmp_path: Path) -> None:
    from pipeline.previs_blender import (
        CAMERA_MOVE_PREVIS_PRESETS,
        auto_synthesize_plan_previs_specs,
        load_location_registry,
        previs_conformance_qa,
    )

    assert len(CAMERA_MOVE_PREVIS_PRESETS) >= 12
    assert "dolly_zoom_vertigo" in CAMERA_MOVE_PREVIS_PRESETS
    assert "crane_swoop_dive" in CAMERA_MOVE_PREVIS_PRESETS
    loc_reg = load_location_registry()
    assert "university_playroom" in loc_reg.get("locations", loc_reg)

    plan = {
        "clips": [
            {
                "clip_number": 1,
                "scene_id": "S01",
                "grammar": "expressive_vinyl_world",
                "camera_move": "dolly_zoom_vertigo",
                "location_id": "university_playroom",
                "cast": "a child in a yellow sweater sitting at the table and a researcher standing",
                "action": "reaches toward the marshmallow on the plate",
            },
            {
                "clip_number": 2,
                "scene_id": "S02",
                "grammar": "expressive_hands_closeup",
                "camera_move": "crane_swoop_dive",
                "location_id": "university_playroom",
                "cast": "a child reaching across the oak table",
                "action": "nudges broken crayon stubs on the saucer",
            },
        ]
    }
    auto_plan = auto_synthesize_plan_previs_specs(plan)
    p1 = auto_plan["clips"][0]["previs"]
    p2 = auto_plan["clips"][1]["previs"]
    # Same location_id reuses identical room_blocks layout
    assert p1["room_blocks"] == p2["room_blocks"]
    # Child actor gets child archetype height (~1.05m) & seated/reaching pose
    assert any(float(a.get("height_m", 1.72)) <= 1.20 for a in p1["actors"])

    # E7 conformance QA check on matching vs mismatched silhouettes
    previs_png = tmp_path / "previs.png"
    good_kf = tmp_path / "good_kf.png"
    bad_kf = tmp_path / "bad_kf.png"
    bg = np.full((320, 180, 3), 130, dtype=np.uint8)
    img_prev = bg.copy()
    img_prev[100:220, 50:120] = (191, 44, 123)  # BGR for #7B2CBF Royal Violet
    cv2.imwrite(str(previs_png), img_prev)

    img_good = np.full((320, 180, 3), 235, dtype=np.uint8)
    img_good[102:218, 52:118] = (40, 40, 40)
    cv2.imwrite(str(good_kf), img_good)

    img_bad = np.full((320, 180, 3), 235, dtype=np.uint8)
    img_bad[10:50, 130:175] = (40, 40, 40)
    cv2.imwrite(str(bad_kf), img_bad)

    qa_good = previs_conformance_qa(previs_png, good_kf)
    qa_bad = previs_conformance_qa(previs_png, bad_kf)
    assert qa_good["passed"] is True and qa_good["iou"] >= 0.35
    assert qa_bad["passed"] is False and qa_bad["iou"] < 0.35


def test_bgm_vibrato_phase_bounded_and_elevenlabs_music_v25_payload_and_bank_cache(tmp_path: Path) -> None:
    from pipeline.elevenlabs_music import (
        synthesize_or_load_elevenlabs_bgm,
        synthesize_tonal_fixed_underscore,
    )

    # 1. Verify phase-integral vibrato has bounded <= 1.0 Hz instantaneous deviation even at t = 120s
    f0 = 130.813
    vib_depth = 0.0022
    vib_rate = 4.1
    t = np.linspace(118.0, 120.0, 96000, dtype=np.float64)
    phase = 2.0 * np.pi * f0 * t - (f0 * vib_depth / vib_rate) * np.cos(2.0 * np.pi * vib_rate * t)
    inst_freq = np.diff(phase) * 48000.0 / (2.0 * np.pi)
    assert float(np.max(np.abs(inst_freq - f0))) <= 1.0

    st_pcm = synthesize_tonal_fixed_underscore(48000 * 4, sr=48000)
    assert st_pcm.shape == (48000 * 4, 2)
    assert float(np.max(np.abs(st_pcm))) <= 0.501

    # 2. Mock ElevenLabs /v1/music -> verify music_v2_5, force_instrumental=True, and 0 calls on bgm_bank cache hit
    env_file = tmp_path / "el_music.env"
    env_file.write_text('XI_API_KEY="test_music_key"\n', encoding="utf-8")
    mp3_sample = _tiny_sine_mp3_bytes() * 32  # >= 8192 bytes for bank cache threshold
    music_calls: list[tuple[str, dict[str, Any]]] = []

    class _FakeMusicResp:
        def __init__(self, raw_bytes: bytes) -> None:
            self._raw = raw_bytes

        def read(self) -> bytes:
            return self._raw

        def __enter__(self) -> "_FakeMusicResp":
            return self

        def __exit__(self, *_: Any) -> None:
            return None

    def _fake_music_urlopen(req: Any, timeout: float = 90.0) -> _FakeMusicResp:
        payload = json.loads(req.data.decode("utf-8"))
        music_calls.append((req.full_url, payload))
        return _FakeMusicResp(mp3_sample)

    bank_dir = tmp_path / "bgm_bank"
    with patch("urllib.request.urlopen", side_effect=_fake_music_urlopen):
        st1, meta1 = synthesize_or_load_elevenlabs_bgm(
            "curious_marimba_strings",
            duration_sec=10.0,
            sr=48000,
            cache_dir=bank_dir,
            env_path=env_file,
        )
        assert len(music_calls) == 1
        assert "/v1/music" in music_calls[0][0]
        assert music_calls[0][1]["model_id"] == "music_v2_5"
        assert music_calls[0][1]["force_instrumental"] is True
        assert meta1["cache_hit"] is False
        assert st1.shape == (48000 * 10, 2)

        # Second invocation hits bgm_bank SHA-256 disk cache -> 0 API calls!
        st2, meta2 = synthesize_or_load_elevenlabs_bgm(
            "curious_marimba_strings",
            duration_sec=10.0,
            sr=48000,
            cache_dir=bank_dir,
            env_path=env_file,
        )
        assert len(music_calls) == 1
        assert meta2["cache_hit"] is True
        assert st2.shape == (48000 * 10, 2)


def test_no_framerate_blend_in_v8_filtergraph() -> None:
    import inspect

    from pipeline import config as cfg
    from pipeline.diorama_assembler import _render_cut_segment, build_v7_dynamic_edl

    assert cfg.EXPRESSIVE_V8_CURVE_RAMP is False
    render_code_lines = [l for l in inspect.getsource(_render_cut_segment).splitlines() if not l.strip().startswith("#")]
    assert not any("interp_start=0:interp_end=255" in l for l in render_code_lines)
    edl_src = inspect.getsource(build_v7_dynamic_edl)
    assert "allow_alpha_dissolves" in edl_src


def test_data_stamp_hero_progressive_strokes_and_arrow_natural_stroke() -> None:
    from pipeline.data_stamp_overlay import compute_natural_arrow_geometry, render_data_stamp_rgba_frame

    stamp = {
        "sentence_index": 13,
        "chart": "bar_compare",
        "style": "crayon",
        "title": "ROCHESTER MARSHMALLOW WAIT TIME",
        "bars": [
            {"label": "Broken Promise", "value": 3, "unit": "min"},
            {"label": "Kept Promise", "value": 12, "unit": "min"},
        ],
        "multiplier_badge": "×4 LONGER",
        "source_citation": "Kidd et al. (2013) · n=28",
        "doi": "10.1016/j.cognition.2012.08.004",
    }
    f_early = np.asarray(render_data_stamp_rgba_frame(stamp, 0.35, 3.0, width=1080, height=1920))
    f_mid = np.asarray(render_data_stamp_rgba_frame(stamp, 1.15, 3.0, width=1080, height=1920))
    f_full = np.asarray(render_data_stamp_rgba_frame(stamp, 2.30, 3.0, width=1080, height=1920))

    a_early = int(np.sum(f_early[:, :, 3] > 32))
    a_mid = int(np.sum(f_mid[:, :, 3] > 32))
    a_full = int(np.sum(f_full[:, :, 3] > 32))
    assert a_early < a_mid < a_full
    # Zero rectangular UI card background at outer top-left margin inside HERO band
    assert int(f_full[210, 62, 3]) == 0

    geo = compute_natural_arrow_geometry((380.0, 520.0), (760.0, 760.0), scale=1.0, seed=101)
    widths = geo["shaft_widths"]
    assert float(np.std(widths)) > 0.4
    wl = geo["left_wing_points"]
    wr = geo["right_wing_points"]
    len_left = float(np.linalg.norm(wl[-1] - wl[0]))
    len_right = float(np.linalg.norm(wr[-1] - wr[0]))
    assert (len_left - len_right) / max(1e-6, len_left) >= 0.15

    # Verify shaft is an organic asymmetric curve, NOT a constant-curvature circular arc (circle-fit RMSE >= 2px)
    pts = geo["shaft_points"].astype(np.float64)
    A = np.column_stack([2.0 * pts[:, 0], 2.0 * pts[:, 1], np.ones(len(pts))])
    b = pts[:, 0] ** 2 + pts[:, 1] ** 2
    cx, cy, c0 = np.linalg.lstsq(A, b, rcond=None)[0]
    rad = float(np.sqrt(max(1.0, c0 + cx * cx + cy * cy)))
    dists = np.hypot(pts[:, 0] - cx, pts[:, 1] - cy)
    circle_rmse = float(np.sqrt(np.mean((dists - rad) ** 2)))
    assert circle_rmse >= 2.0, f"Expected non-circular organic Bézier curve (RMSE>=2px), got {circle_rmse:.3f}px"


def test_anatomy_label_anchor_resolves() -> None:
    from pipeline.anatomy_label_overlay import render_anatomy_callout_rgba_frame
    from pipeline.anatomy_map import resolve_anatomy_screen_anchor

    na = resolve_anatomy_screen_anchor("nucleus accumbens")
    pfc = resolve_anatomy_screen_anchor("ventromedial prefrontal cortex and dorsolateral prefrontal cortex")
    assert na is not None and "Nucleus Accumbens" in na["display_title"]
    assert pfc is not None and "Prefrontal" in pfc["display_title"]

    callout = {
        "cut_index": 13,
        "clip_index": 13,
        "start_sec": 78.0,
        "end_sec": 84.0,
        "duration_sec": 6.0,
        **na,
    }
    im_line = np.asarray(render_anatomy_callout_rgba_frame(callout, 0.30, 6.0, width=1080, height=1920))
    im_full = np.asarray(render_anatomy_callout_rgba_frame(callout, 1.20, 6.0, width=1080, height=1920))
    assert int(np.sum(im_full[:, :, 3] > 32)) > int(np.sum(im_line[:, :, 3] > 32)) > 200
