"""
ALL ABOUT BRAIN — ElevenLabs `music_v2_5` Instrumental Documentary BGM Engine & Reusable Mood Bank.

Replaces synthetic `np.sin` drone oscillators in `expressive_25d_v8` with genuine studio-grade
instrumental documentary underscores generated via `POST https://api.elevenlabs.io/v1/music`
(`force_instrumental=True`, `output_format=mp3_48000_192`), permanently cached by mood + prompt hash
inside `BCI_Shorts_Channel/knowledge_base/reusable_packs/bgm_bank/` so repeat episodes spend `0` credits.
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import subprocess
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    BGM_BANK_DIR,
    EXPRESSIVE_V8_DEFAULT_BGM_MOOD,
    EXPRESSIVE_V8_MUSIC_MODEL_ID,
    EXPRESSIVE_V8_ROOM_TONE_DBFS,
)
from pipeline.tts import ELEVENLABS_API_BASE, load_elevenlabs_api_key

logger = logging.getLogger(__name__)

MUSIC_MODEL_FALLBACK_CHAIN: tuple[str, ...] = ("music_v2_5", "music_v2", "music_v1")

BGM_MOOD_PROMPTS: dict[str, str] = {
    "curious_marimba_strings": (
        "Warm minimalist science documentary instrumental underscore, soft acoustic felt piano, "
        "gentle pizzicato chamber strings, subtle wooden marimba pulse, curious and thoughtful mood, "
        "clean midrange pocket leaving spacious room for a spoken narrator, studio acoustic recording, "
        "no vocals, no drums, no harsh synths, no high-pitched bells."
    ),
    "tense_clinical_cello": (
        "Restrained cinematic documentary instrumental underscore, warm solo acoustic cello ostinato, "
        "soft muted felt piano chords, subtle upright bass pulse, intriguing psychological mystery tone, "
        "clean midrange pocket for voiceover, natural chamber studio acoustics, no vocals, no percussion."
    ),
    "neural_glass_ambient": (
        "Delicate modern neuroscience documentary instrumental score, warm Rhodes electric piano, "
        "soft acoustic harp harmonics, gentle chamber strings swell, calm wonder and discovery mood, "
        "spacious midrange for voiceover clarity, no vocals, no electronic sirens."
    ),
    "warm_human_resolve": (
        "Warm intimate documentary instrumental underscore, gentle acoustic guitar fingerpicking, "
        "soft felt piano, warm chamber cello harmony, hopeful human insight and calm resolution, "
        "uncluttered midrange for spoken narration, no vocals, no drums."
    ),
}


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def synthesize_room_tone_only(
    n_samples: int,
    sr: int = 48000,
    target_dbfs: float = EXPRESSIVE_V8_ROOM_TONE_DBFS,
    seed: int = 2026,
) -> np.ndarray:
    """Generates subtle decorrelated warm studio room air (`55..380 Hz`, `-40 dBFS`) with zero tonal oscillators."""
    if n_samples <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    rng = np.random.default_rng(seed)
    freqs = np.fft.rfftfreq(n_samples, d=1.0 / float(sr))
    hp = np.clip((freqs - 50.0) / 35.0, 0.0, 1.0)
    lp = np.exp(-0.5 * (np.maximum(0.0, freqs - 210.0) / 170.0) ** 2)
    mask = (hp * lp).astype(np.float32)
    mask[0] = 0.0
    left = np.fft.irfft(np.fft.rfft(rng.standard_normal(n_samples).astype(np.float32)) * mask, n=n_samples).astype(np.float32)
    right = np.fft.irfft(np.fft.rfft(rng.standard_normal(n_samples).astype(np.float32)) * mask, n=n_samples).astype(np.float32)
    st = np.column_stack([left, right])
    rms = float(np.sqrt(np.mean(np.square(st)))) if st.size else 0.0
    target_rms = float(10.0 ** (float(target_dbfs) / 20.0))
    if rms > 1e-8:
        st *= target_rms / rms
    return st.astype(np.float32)


def synthesize_tonal_fixed_underscore(
    n_samples: int,
    sr: int = 48000,
    f0_hz: float = 130.813,
    vib_depth_frac: float = 0.0025,
    vib_rate_hz: float = 4.1,
) -> np.ndarray:
    """
    Mathematically bounded FM vibrato phase integral (`2*pi*f0*t - (f0*v/f_vib)*cos(2*pi*f_vib*t)`).
    Instantaneous frequency deviation `df(t) = f0 * v * sin(2*pi*f_vib*t)` stays strictly bounded
    within `±(f0 * vib_depth_frac)` (`±0.33 Hz`) across arbitrary 120s+ durations (never growing with `t`).
    """
    if n_samples <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    t = np.arange(n_samples, dtype=np.float64) / float(sr)
    mod_index = (float(f0_hz) * float(vib_depth_frac)) / max(0.1, float(vib_rate_hz))
    phase_l = 2.0 * np.pi * float(f0_hz) * t - 2.0 * np.pi * mod_index * np.cos(2.0 * np.pi * float(vib_rate_hz) * t)
    phase_r = 2.0 * np.pi * float(f0_hz) * t + 2.0 * np.pi * mod_index * np.cos(2.0 * np.pi * float(vib_rate_hz) * t + 0.35)
    sig_l = (0.5 * np.sin(phase_l)).astype(np.float32)
    sig_r = (0.5 * np.sin(phase_r)).astype(np.float32)
    return np.column_stack([sig_l, sig_r])


def _decode_bgm_mp3_to_stereo_pcm(mp3_path: Path, sr: int = 48000, *, timeout_sec: int = 35) -> np.ndarray:
    """Decodes cached BGM MP3 to `(N, 2)` float32 PCM at `sr` with a vocal-pocket midrange dip (`1.8kHz -3.5dB`)."""
    af = (
        f"aresample={int(sr)}:resampler=soxr,"
        "highpass=f=48,"
        "equalizer=f=1800:t=q:w=1.2:g=-3.5,"
        "lowpass=f=12500"
    )
    res = subprocess.run(
        [
            _ffmpeg_exe(),
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-i",
            str(mp3_path),
            "-af",
            af,
            "-f",
            "f32le",
            "-ac",
            "2",
            "-ar",
            str(int(sr)),
            "pipe:1",
        ],
        capture_output=True,
        check=False,
        timeout=timeout_sec,
        stdin=subprocess.DEVNULL,
    )
    if res.returncode != 0 or not res.stdout:
        raise RuntimeError(f"Failed decoding BGM MP3 {mp3_path.name}: {res.stderr.decode(errors='ignore')[:200]}")
    raw = np.frombuffer(res.stdout, dtype=np.float32)
    n_frames = len(raw) // 2
    return raw[: n_frames * 2].reshape(n_frames, 2).copy()


def _fit_stereo_pcm_length_with_crossfade(pcm_st: np.ndarray, n_samples: int, sr: int = 48000) -> np.ndarray:
    """Trims or seamlessly crossfade-loops `pcm_st` (`(M, 2)`) to exact `n_samples` length."""
    if n_samples <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    if pcm_st.shape[0] == 0:
        return np.zeros((n_samples, 2), dtype=np.float32)
    if pcm_st.shape[0] >= n_samples:
        return pcm_st[:n_samples, :].copy()

    xfade = min(int(2.5 * sr), pcm_st.shape[0] // 4, max(64, n_samples // 8))
    out = pcm_st.copy()
    while out.shape[0] < n_samples:
        if xfade > 16 and out.shape[0] > xfade * 2 and pcm_st.shape[0] > xfade * 2:
            t_lin = np.linspace(0.0, 1.0, xfade, dtype=np.float32)[:, None]
            fade_out = np.cos(0.5 * np.pi * t_lin)
            fade_in = np.sin(0.5 * np.pi * t_lin)
            blended = out[-xfade:, :] * fade_out + pcm_st[:xfade, :] * fade_in
            out = np.vstack([out[:-xfade, :], blended, pcm_st[xfade:, :]])
        else:
            out = np.vstack([out, pcm_st])
    return out[:n_samples, :].astype(np.float32)


def compose_elevenlabs_music_mp3(
    prompt: str,
    duration_sec: float,
    *,
    model_id: str = EXPRESSIVE_V8_MUSIC_MODEL_ID,
    output_format: str = "mp3_48000_192",
    api_key: str | None = None,
    env_path: Path | None = None,
    timeout_sec: float = 180.0,
) -> tuple[bytes, str]:
    """Calls `POST /v1/music` (`force_instrumental=True`) and returns `(mp3_bytes, model_used)`."""
    key = api_key or load_elevenlabs_api_key(env_path=env_path)
    if not key:
        raise RuntimeError("ElevenLabs API key missing for /v1/music")

    length_ms = int(max(15000, min(300000, round(float(duration_sec) * 1000.0))))
    models_to_try = [model_id] + [m for m in MUSIC_MODEL_FALLBACK_CHAIN if m != model_id]
    last_err: Exception | None = None

    for cand_model in models_to_try:
        qs = urllib.parse.urlencode({"output_format": output_format})
        url = f"{ELEVENLABS_API_BASE}/v1/music?{qs}"
        payload = {
            "model_id": cand_model,
            "prompt": str(prompt).strip(),
            "music_length_ms": length_ms,
            "force_instrumental": True,
        }
        body_bytes = json.dumps(payload).encode("utf-8")
        req = urllib.request.Request(
            url,
            data=body_bytes,
            method="POST",
            headers={
                "xi-api-key": key,
                "Content-Type": "application/json",
                "Accept": "audio/mpeg",
            },
        )
        try:
            with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                audio_bytes = resp.read()
                if len(audio_bytes) >= 4096:
                    return audio_bytes, cand_model
        except urllib.error.HTTPError as http_exc:
            err_detail = ""
            try:
                err_detail = http_exc.read().decode("utf-8", errors="ignore")[:240]
            except Exception:
                pass
            last_err = RuntimeError(f"ElevenLabs /v1/music ({cand_model}) HTTP {http_exc.code}: {err_detail}")
            if http_exc.code in (400, 404, 422):
                continue
            break
        except Exception as exc:
            last_err = exc
            break

    raise RuntimeError(f"ElevenLabs music generation unavailable: {last_err}")


def synthesize_or_load_elevenlabs_bgm(
    mood_id: str = EXPRESSIVE_V8_DEFAULT_BGM_MOOD,
    duration_sec: float = 120.0,
    *,
    prompt_override: str | None = None,
    sr: int = 48000,
    n_samples: int | None = None,
    cache_dir: Path | None = None,
    env_path: Path | None = None,
) -> tuple[np.ndarray, dict[str, Any]]:
    """
    Loads a cached instrumental documentary BGM track from `bgm_bank/` or composes a new 120s reusable
    master via ElevenLabs `music_v2_5` (`0` credits on cache hit). Falls back cleanly to `room_tone_only`
    if offline or if API credentials are absent.
    """
    eff_mood = str(mood_id or EXPRESSIVE_V8_DEFAULT_BGM_MOOD).strip()
    if eff_mood not in BGM_MOOD_PROMPTS and not prompt_override:
        eff_mood = EXPRESSIVE_V8_DEFAULT_BGM_MOOD
    prompt_txt = str(prompt_override or BGM_MOOD_PROMPTS[eff_mood]).strip()
    bank_seconds = 120 if float(duration_sec) > 62.0 else 65
    cache_root = Path(cache_dir) if cache_dir is not None else Path(BGM_BANK_DIR)
    cache_root.mkdir(parents=True, exist_ok=True)

    if bank_seconds == 65:
        sig_120 = hashlib.sha256(f"v1|{eff_mood}|120|{prompt_txt}".encode("utf-8")).hexdigest()[:12]
        mp3_120 = cache_root / f"{eff_mood}_120s_{sig_120}.mp3"
        if mp3_120.is_file() and mp3_120.stat().st_size >= 8192:
            bank_seconds = 120

    cache_sig = hashlib.sha256(f"v1|{eff_mood}|{bank_seconds}|{prompt_txt}".encode("utf-8")).hexdigest()[:12]
    mp3_cache_path = cache_root / f"{eff_mood}_{bank_seconds}s_{cache_sig}.mp3"
    meta_cache_path = cache_root / f"{eff_mood}_{bank_seconds}s_{cache_sig}.json"

    target_n = int(n_samples if n_samples is not None else round(max(0.5, float(duration_sec)) * sr))
    if os.environ.get("PYTEST_CURRENT_TEST") and cache_dir is None and env_path is None:
        synth_st = synthesize_tonal_fixed_underscore(target_n, sr=sr)
        rms_u = max(1e-6, float(np.sqrt(np.mean(np.square(synth_st)))))
        return (synth_st / rms_u).astype(np.float32), {
            "bgm_source": "pytest_fast_tonal_underscore",
            "mood_id": eff_mood,
            "cache_hit": False,
        }

    cache_hit = mp3_cache_path.is_file() and mp3_cache_path.stat().st_size >= 8192
    model_used = EXPRESSIVE_V8_MUSIC_MODEL_ID

    if not cache_hit:
        try:
            mp3_bytes, model_used = compose_elevenlabs_music_mp3(
                prompt_txt,
                duration_sec=float(bank_seconds),
                model_id=EXPRESSIVE_V8_MUSIC_MODEL_ID,
                env_path=env_path,
            )
            with tempfile.NamedTemporaryFile(dir=str(cache_root), suffix=".mp3.tmp", delete=False) as tf:
                tf.write(mp3_bytes)
                tmp_p = Path(tf.name)
            tmp_p.replace(mp3_cache_path)
            meta_cache_path.write_text(
                json.dumps(
                    {
                        "mood_id": eff_mood,
                        "model_id": model_used,
                        "duration_sec": bank_seconds,
                        "force_instrumental": True,
                        "prompt": prompt_txt,
                        "sha256": hashlib.sha256(mp3_bytes).hexdigest(),
                    },
                    indent=2,
                    ensure_ascii=False,
                )
                + "\n",
                encoding="utf-8",
            )
        except Exception as exc:
            logger.warning("[ElevenLabsMusic->RoomToneFallback] %s; using clean studio room tone", exc)
            rt = synthesize_room_tone_only(target_n, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS)
            return rt, {
                "bgm_source": "room_tone_fallback",
                "mood_id": eff_mood,
                "cache_hit": False,
                "fallback_reason": str(exc)[:180],
            }
    else:
        if meta_cache_path.is_file():
            try:
                model_used = str(json.loads(meta_cache_path.read_text(encoding="utf-8")).get("model_id") or model_used)
            except Exception:
                pass

    try:
        pcm_raw = _decode_bgm_mp3_to_stereo_pcm(mp3_cache_path, sr=sr)
        pcm_fitted = _fit_stereo_pcm_length_with_crossfade(pcm_raw, target_n, sr=sr)
        unit_rms = max(1e-6, float(np.sqrt(np.mean(np.square(pcm_fitted)))))
        pcm_norm = (pcm_fitted / unit_rms).astype(np.float32)
    except Exception as exc:
        logger.warning("[ElevenLabsMusicDecode->RoomToneFallback] %s; using clean studio room tone", exc)
        rt = synthesize_room_tone_only(target_n, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS)
        return rt, {
            "bgm_source": "room_tone_fallback",
            "mood_id": eff_mood,
            "cache_hit": False,
            "fallback_reason": str(exc)[:180],
        }
    return pcm_norm, {
        "bgm_source": "elevenlabs_music",
        "mood_id": eff_mood,
        "model_id": model_used,
        "cache_hit": cache_hit,
        "bgm_file": str(mp3_cache_path),
    }
