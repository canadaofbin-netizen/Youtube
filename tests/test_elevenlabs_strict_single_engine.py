"""Strict ElevenLabs `eleven_v4` Single-Engine Lock & `v8` Atmospheric Dark-Lighting Tests."""

from __future__ import annotations

import base64
import importlib.util
import io
import json
import math
import subprocess
import urllib.error
import wave
from pathlib import Path
from typing import Any

import cv2
import imageio_ffmpeg
import numpy as np
import pytest

import pipeline.config as cfg
import pipeline.elevenlabs_tts as el_mod
import pipeline.voice_fallback as vf_mod
from pipeline.elevenlabs_tts import ElevenLabsUnavailableError, synthesize_elevenlabs_v4_sentence
from pipeline.flow_diorama_sharded_worker import (
    _reinforce_porcelain_cv_retry_prompt,
    inspect_diorama_clip_cv,
)
from pipeline.voice_fallback import resolve_diorama_voice_preset, synthesize_continuous_diorama_track


def _make_valid_mp3_bytes(sr: int = 44100, dur_sec: float = 0.6) -> bytes:
    t = np.linspace(0.0, dur_sec, int(sr * dur_sec), endpoint=False, dtype=np.float32)
    pcm = (0.25 * np.sin(2.0 * math.pi * 180.0 * t) * 32767.0).astype(np.int16)
    buf = io.BytesIO()
    with wave.open(buf, "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm.tobytes())
    res = subprocess.run(
        [
            imageio_ffmpeg.get_ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-f",
            "wav",
            "-i",
            "pipe:0",
            "-f",
            "mp3",
            "-b:a",
            "128k",
            "pipe:1",
        ],
        input=buf.getvalue(),
        capture_output=True,
        check=True,
        timeout=20,
    )
    return res.stdout


def test_clean_venv_and_repo_legacy_tts_purge() -> None:
    for pkg in ("kokoro_onnx", "edge_tts", "espeakng_loader", "phonemizer"):
        assert importlib.util.find_spec(pkg) is None, f"Legacy package {pkg} must be uninstalled"
    assert importlib.util.find_spec("onnxruntime") is not None
    assert not (Path(cfg.WORKSPACE_ROOT) / "pipeline" / "voice_consistency.py").exists()
    assert not (Path.home() / ".cache" / "aab_tts").exists()
    assert cfg.DIORAMA_TTS_ENGINE == "eleven_v4"
    assert set(cfg.DIORAMA_VOICE_PRESETS.keys()) == {
        "elevenlabs_v4",
        "el_siren_v4",
        "el_researcher_v4",
        "el_minicortex_v4",
        "elevenlabs_v4_female",
        "elevenlabs_v4_male",
    }
    for spec in cfg.DIORAMA_VOICE_PRESETS.values():
        assert "kokoro_voice" not in spec
        assert "fallback_preset" not in spec
        assert spec["elevenlabs_voice_id"]


def test_elevenlabs_strict_fail_fast_zero_legacy_downgrade(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    p_dir = tmp_path / "strict_fail_proj"
    for sub in ("03_visuals", "04_audio"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"}),
        encoding="utf-8",
    )

    with pytest.raises(ElevenLabsUnavailableError, match="Legacy TTS engine"):
        synthesize_continuous_diorama_track(
            p_dir,
            ["In 2011 at Iowa, researchers tested a fearless woman."],
            engine="kokoro-onnx",
            allow_test_stub=False,
        )

    def _boom(*_a: Any, **_kw: Any) -> dict[str, Any]:
        raise ElevenLabsUnavailableError("ElevenLabs quota exhausted")

    monkeypatch.setattr(el_mod, "synthesize_elevenlabs_v4_episode", _boom)
    with pytest.raises(ElevenLabsUnavailableError, match="quota exhausted"):
        synthesize_continuous_diorama_track(
            p_dir,
            ["In 2011 at Iowa, researchers tested a fearless woman."],
            voice_preset="elevenlabs_v4",
            allow_test_stub=False,
        )


def test_elevenlabs_v4_sentence_3x_transient_retry_and_auth_quota_fail_fast(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    mp3_b64 = base64.b64encode(_make_valid_mp3_bytes()).decode("ascii")
    sleeps: list[float] = []
    _real_sleep = el_mod.time.sleep

    def _fake_sleep(s: float) -> None:
        val = float(s)
        if val >= 0.5:
            sleeps.append(val)
        else:
            _real_sleep(val)

    monkeypatch.setattr(el_mod.time, "sleep", _fake_sleep)

    # 1. Transient 503 -> 429 rate-limit -> 200 recovery
    attempts = {"n": 0}

    class _FakeResp:
        headers = {"request-id": "req_ok_123"}

        def __enter__(self):
            return self

        def __exit__(self, *_exc):
            return False

        def read(self) -> bytes:
            return json.dumps(
                {
                    "audio_base64": mp3_b64,
                    "alignment": {
                        "characters": list("Hello!"),
                        "character_start_times_seconds": [0.0, 0.05, 0.1, 0.15, 0.2, 0.25],
                        "character_end_times_seconds": [0.05, 0.1, 0.15, 0.2, 0.25, 0.3],
                    },
                }
            ).encode("utf-8")

    def _flaky_urlopen(req: urllib.request.Request, timeout: float = 45.0):
        attempts["n"] += 1
        if attempts["n"] == 1:
            raise urllib.error.HTTPError(req.full_url, 503, "Service Unavailable", {}, io.BytesIO(b"busy"))
        if attempts["n"] == 2:
            raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"rate_limit"))
        return _FakeResp()

    monkeypatch.setattr(el_mod.urllib.request, "urlopen", _flaky_urlopen)
    out = synthesize_elevenlabs_v4_sentence(
        "Hello!",
        voice_id="CwhRBWXzGAHq8TQ4Fs17",
        fallback_voice_id=None,
        cache_dir=tmp_path / "cache_ok",
        api_key="test_key",
    )
    assert attempts["n"] == 3
    assert sleeps == [1.5, 3.0]
    assert out["request_id"] == "req_ok_123"
    assert len(out["pcm"]) > 1000

    # 2. HTTP 401 unauthorized fails fast immediately with 0 sleeps
    sleeps.clear()

    def _auth_fail(req: urllib.request.Request, timeout: float = 45.0):
        raise urllib.error.HTTPError(req.full_url, 401, "Unauthorized", {}, io.BytesIO(b"invalid_api_key"))

    monkeypatch.setattr(el_mod.urllib.request, "urlopen", _auth_fail)
    with pytest.raises(ElevenLabsUnavailableError, match="HTTP 401"):
        synthesize_elevenlabs_v4_sentence(
            "Auth test.",
            voice_id="CwhRBWXzGAHq8TQ4Fs17",
            fallback_voice_id=None,
            cache_dir=tmp_path / "cache_401",
            api_key="bad_key",
        )
    assert sleeps == []

    # 3. HTTP 429 explicit quota_exceeded fails fast immediately with 0 sleeps
    def _quota_fail(req: urllib.request.Request, timeout: float = 45.0):
        raise urllib.error.HTTPError(req.full_url, 429, "Too Many Requests", {}, io.BytesIO(b"quota_exceeded"))

    monkeypatch.setattr(el_mod.urllib.request, "urlopen", _quota_fail)
    with pytest.raises(ElevenLabsUnavailableError, match="quota_exceeded"):
        synthesize_elevenlabs_v4_sentence(
            "Quota test.",
            voice_id="CwhRBWXzGAHq8TQ4Fs17",
            fallback_voice_id=None,
            cache_dir=tmp_path / "cache_quota",
            api_key="test_key",
        )
    assert sleeps == []


def test_offline_test_stub_and_v8_two_word_subtitle_chunking(tmp_path: Path) -> None:
    p_dir = tmp_path / "v8_sub_chunk_proj"
    for sub in ("03_visuals", "04_audio"):
        (p_dir / sub).mkdir(parents=True, exist_ok=True)
    (p_dir / "03_visuals" / "visual_plan.json").write_text(
        json.dumps({"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"}),
        encoding="utf-8",
    )
    sents = [
        "In 2011 at Waverly Hills, researchers led one woman through a dark corridor!",
        "Yet her heart rate never jumped once inside that haunted room.",
    ] + [f"Sentence {idx} adds measured clinical detail to the timeline." for idx in range(3, 15)]

    res = synthesize_continuous_diorama_track(
        p_dir,
        sents,
        align_whisper=False,
        script_doc={"style_profile": "expressive_25d_v8", "format_profile": "shorts_expressive_v8"},
        prosody_mode="expressive_us_v8",
        allow_test_stub=True,
    )
    assert res["report"]["engine"] == "test_stub"
    events = res["events"]
    assert len(events) > 10
    assert all(len(ev[2]) <= cfg.EXPRESSIVE_V8_SUBTITLE_MAX_WORDS for ev in events)
    p_fem, _ = resolve_diorama_voice_preset("emma_v7", {"style_profile": "expressive_25d_v8"})
    assert p_fem == "elevenlabs_v4_female"
    p_male, _ = resolve_diorama_voice_preset("andrew_v8", {"style_profile": "expressive_25d_v8"})
    assert p_male == "elevenlabs_v4"


def test_v8_atmospheric_dark_lighting_passes_cv_without_lighting_mode_and_blocks_blackout(tmp_path: Path) -> None:
    assert cfg.EXPRESSIVE_V8_MIN_LUMA == 28.0

    # Retry prompt on v8 NEVER injects high-key studio daylight
    retry_v8 = _reinforce_porcelain_cv_retry_prompt(
        "Gentle push-in through a dark haunted hallway. Subtle crisp physical foley.",
        grammar="expressive_vinyl_world",
        cv_reason="dark_void_leak_v7:mean_luma=21.0",
    )
    assert "bright high-key studio daylight" not in retry_v8.lower()
    assert "intended atmospheric lighting" in retry_v8.lower()

    retry_v7 = _reinforce_porcelain_cv_retry_prompt(
        "Locked shot in a lab. Subtle crisp physical foley.",
        grammar="porcelain_fullbleed_world",
        cv_reason="dark_void_leak_v7:mean_luma=65.0",
    )
    assert "bright high-key studio daylight" in retry_v7.lower()

    def _encode_test_clip(mp4_path: Path, frames: list[np.ndarray]) -> None:
        proc = subprocess.Popen(
            [
                imageio_ffmpeg.get_ffmpeg_exe(),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-f",
                "rawvideo",
                "-pix_fmt",
                "bgr24",
                "-s",
                "720x1280",
                "-r",
                "24",
                "-i",
                "pipe:0",
                "-c:v",
                "libx264",
                "-preset",
                "ultrafast",
                "-crf",
                "12",
                "-pix_fmt",
                "yuv420p",
                str(mp4_path),
            ],
            stdin=subprocess.PIPE,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.PIPE,
        )
        assert proc.stdin is not None
        for f in frames:
            proc.stdin.write(f.tobytes())
        proc.stdin.close()
        proc.wait(timeout=30)
        assert proc.returncode == 0

    # 1. Atmospheric haunted-house v8 clip (mean_luma ~ 44, dark_v35 ~ 0.52, warm amber glow, NO lighting_mode) -> PASSES!
    rng = np.random.default_rng(77)
    base_noise = rng.integers(14, 32, size=(1280, 720, 3), dtype=np.uint8)
    haunted_frames: list[np.ndarray] = []
    for k in range(144):
        frm = np.roll(base_noise, shift=(k * 3) % 64, axis=0).copy()
        x0 = 160 + int(4.5 * k) % 240
        cv2.rectangle(frm, (90, 220), (630, 1080), (32, 62, 96), -1)  # warm dark amber hall
        cv2.circle(frm, (x0 + 100, 560), 92, (225, 235, 242), -1)     # cream-white vinyl head
        cv2.circle(frm, (x0 + 70, 548), 11, (18, 18, 18), -1)         # 2D ink eye
        cv2.circle(frm, (x0 + 130, 548), 11, (18, 18, 18), -1)        # 2D ink eye
        cv2.line(frm, (x0 + 70, 594), (x0 + 130, 594), (18, 18, 18), 6)
        haunted_frames.append(frm)
    haunted_mp4 = tmp_path / "haunted_v8.mp4"
    _encode_test_clip(haunted_mp4, haunted_frames)
    if haunted_mp4.stat().st_size < 165_000:
        with haunted_mp4.open("ab") as fh:
            fh.write(b"\x00" * (165_000 - haunted_mp4.stat().st_size))

    cv_ok = inspect_diorama_clip_cv(
        haunted_mp4,
        grammar="expressive_vinyl_world",
        schema_version=8,
        style_profile="expressive_25d_v8",
        lighting_mode="",  # NO manual lighting_mode tag!
    )
    assert cv_ok["passed"] is True, f"Atmospheric dark v8 clip must pass CV without lighting_mode: {cv_ok}"
    assert 28.0 <= float(cv_ok["mean_luma"]) <= 60.0

    # Same dark clip under porcelain_cinematic_v7 MUST still be rejected (v7 high-key lock preserved)
    cv_v7_reject = inspect_diorama_clip_cv(
        haunted_mp4,
        grammar="porcelain_fullbleed_world",
        schema_version=7,
        style_profile="porcelain_cinematic_v7",
    )
    assert cv_v7_reject["passed"] is False
    assert "dark_void_leak_v7" in str(cv_v7_reject["reason"])

    # 2. Pitch-black broken render (< 26.0 luma) on v8 MUST still fail
    black_noise = rng.integers(0, 16, size=(1280, 720, 3), dtype=np.uint8)
    blackout_frames: list[np.ndarray] = []
    for k in range(144):
        bf = np.roll(black_noise, shift=(k * 3) % 64, axis=0).copy()
        cv2.circle(bf, (180 + (k * 4) % 240, 640), 48, (42, 48, 58), -1)
        blackout_frames.append(bf)
    blackout_mp4 = tmp_path / "blackout_v8.mp4"
    _encode_test_clip(blackout_mp4, blackout_frames)
    if blackout_mp4.stat().st_size < 165_000:
        with blackout_mp4.open("ab") as fh:
            fh.write(b"\x00" * (165_000 - blackout_mp4.stat().st_size))
    cv_black = inspect_diorama_clip_cv(
        blackout_mp4,
        grammar="expressive_vinyl_world",
        schema_version=8,
        style_profile="expressive_25d_v8",
    )
    assert cv_black["passed"] is False
    assert "dark_void_leak_v7" in str(cv_black["reason"])
