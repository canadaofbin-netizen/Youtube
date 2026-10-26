"""
ALL ABOUT BRAIN - Voice track resolver with local TTS fallback (R49, decision 2026-10-24 option B).

Order of preference per project:
  1. Native Google Flow narration, when the per-clip F0 series passes the semitone gate (voice_consistency).
     (Gear 3 already regenerated outlier clips up to VOICE_REGEN_MAX_ROUNDS.)
  2. Local, free Kokoro TTS (kokoro-onnx, Apache-2.0) with ONE fixed voice / speed for every clip, when the native
     narration stays inconsistent. Flow video is kept; each clip's video speed is fitted to its TTS line.
  3. Otherwise assembly is blocked (no pitch shifting, ever).

Override: 04_audio/voice_source.json {"force": "native" | "tts_fallback"}.
Outputs: 04_audio/voice_report.json, 04_audio/tts_fallback/clip_N.wav (cached by text+voice+speed hash).
"""

from __future__ import annotations

import hashlib
import json
import re
import subprocess
import tempfile
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    AV_SPEEDUP_FACTOR,
    CLIP_PRE_PIVOT_HOLD_SEC,
    CLIP_VISUAL_HOLD_SEC,
    FINAL_TAIL_SEC,
    SUBTITLE_MAX_WORDS_PER_EVENT,
    VIDEO_FPS,
    VOICE_FALLBACK_ENABLED,
    VOICE_FALLBACK_MODEL_DIR,
    VOICE_FALLBACK_SPEED,
    VOICE_FALLBACK_VIDEO_SPEED_RANGE,
    VOICE_FALLBACK_VOICE,
    pivot_clip_index,
)
from pipeline.plain_language import to_display_text, to_tts_text
from pipeline.voice_consistency import evaluate_f0_series

TTS_LEAD_SEC = 0.12          # silence before each TTS line inside its clip window
TTS_TARGET_ACTIVE_DB = -13.5  # same active-speech level as the native vocal chain
TTS_BROADCAST_FILTER = (
    "highpass=f=85,"
    "equalizer=f=155:t=q:w=1.1:g=2.0,"
    "equalizer=f=380:t=q:w=1.4:g=-2.2,"
    "equalizer=f=3200:t=q:w=1.2:g=2.8,"
    "equalizer=f=7500:t=q:w=1.5:g=1.4,"
    "acompressor=threshold=-19dB:ratio=3.5:attack=4:release=70:makeup=2.2,"
    "alimiter=limit=0.95:level=disabled"
)
_KOKORO = None
_WHISPER_MODEL = None


def _kokoro():
    global _KOKORO
    if _KOKORO is None:
        from kokoro_onnx import Kokoro  # type: ignore

        model = Path(VOICE_FALLBACK_MODEL_DIR) / "kokoro-v1.0.onnx"
        voices = Path(VOICE_FALLBACK_MODEL_DIR) / "voices-v1.0.bin"
        if not model.exists() or not voices.exists():
            raise RuntimeError(
                f"Kokoro model files missing in {VOICE_FALLBACK_MODEL_DIR} (kokoro-v1.0.onnx, voices-v1.0.bin); "
                "download from github.com/thewh1teagle/kokoro-onnx releases 'model-files-v1.0'."
            )
        _KOKORO = Kokoro(str(model), str(voices))
    return _KOKORO


def _ffmpeg() -> str:
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def _resample(pcm: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return pcm.astype(np.float32)
    with tempfile.TemporaryDirectory(prefix="aab_tts_") as td:
        src = Path(td) / "in.f32"
        src.write_bytes(pcm.astype(np.float32).tobytes())
        res = subprocess.run(
            [_ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", str(src),
             "-af", f"aresample={sr_out}:resampler=soxr", "-f", "f32le", "-ac", "1", "pipe:1"],
            capture_output=True, check=False, timeout=120, stdin=subprocess.DEVNULL,
        )
    if res.returncode != 0 or not res.stdout:
        x_old = np.linspace(0.0, 1.0, len(pcm), endpoint=False)
        x_new = np.linspace(0.0, 1.0, int(len(pcm) * sr_out / sr_in), endpoint=False)
        return np.interp(x_new, x_old, pcm).astype(np.float32)
    return np.frombuffer(res.stdout, dtype=np.float32).copy()


def _master_broadcast_vocal(pcm: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Resamples and applies the R41 Broadcast Vocal Chain (highpass, 3-band EQ, 3.5:1 compressor, limiter)."""
    with tempfile.TemporaryDirectory(prefix="aab_tts_master_") as td:
        src = Path(td) / "in.f32"
        src.write_bytes(pcm.astype(np.float32).tobytes())
        af = f"aresample={sr_out}:resampler=soxr,{TTS_BROADCAST_FILTER}"
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "f32le", "-ar", str(sr_in), "-ac", "1", "-i", str(src),
                "-af", af, "-f", "f32le", "-ac", "1", "pipe:1",
            ],
            capture_output=True, check=False, timeout=120, stdin=subprocess.DEVNULL,
        )
    if res.returncode != 0 or not res.stdout:
        return _resample(pcm, sr_in, sr_out)
    return np.frombuffer(res.stdout, dtype=np.float32).copy()


def synthesize_line(
    text: str,
    sr: int = 48000,
    cache_dir: Path | None = None,
    clip_no: int = 0,
    voice: str | None = None,
    speed: float | None = None,
) -> np.ndarray:
    """One narration line -> mono float32 PCM at sr, fixed channel voice / speed, R41 broadcast chain + active level normalized."""
    use_voice = str(voice or VOICE_FALLBACK_VOICE)
    use_speed = float(speed if speed is not None else VOICE_FALLBACK_SPEED)
    spoken = to_tts_text(text)
    key = hashlib.sha256(f"{spoken}|{use_voice}|{use_speed}|r41_v2|{sr}".encode()).hexdigest()[:16]
    cached = Path(cache_dir) / f"clip_{clip_no}_{key}.f32" if cache_dir else None
    if cached and cached.exists():
        return np.frombuffer(cached.read_bytes(), dtype=np.float32).copy()
    audio, sr_in = _kokoro().create(spoken, voice=use_voice, speed=use_speed, lang="en-us")
    pcm = _master_broadcast_vocal(np.asarray(audio, dtype=np.float32), int(sr_in), sr)
    # trim leading / trailing silence
    env = np.abs(pcm) > 0.01
    if env.any():
        first = max(0, int(np.argmax(env)) - int(0.02 * sr))
        last = min(len(pcm), len(pcm) - int(np.argmax(env[::-1])) + int(0.06 * sr))
        pcm = pcm[first:last]
    active = pcm[np.abs(pcm) > 0.02]
    rms = float(np.sqrt(np.mean(np.square(active)))) if active.size else float(np.sqrt(np.mean(np.square(pcm)) + 1e-9))
    gain = min((10.0 ** (TTS_TARGET_ACTIVE_DB / 20.0)) / max(rms, 1e-4), 4.0)
    pcm = np.clip(pcm * gain, -0.95, 0.95).astype(np.float32)
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(pcm.tobytes())
    return pcm


def _clip_duration(path: Path) -> float:
    res = subprocess.run([_ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path)], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
    m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", res.stderr or "")
    if not m:
        return 8.0
    return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))


def _whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel  # type: ignore

        _WHISPER_MODEL = WhisperModel("base.en", device="cpu", compute_type="int8")
    return _WHISPER_MODEL


def _word_times(pcm: np.ndarray, sr: int, text: str) -> list[tuple[float, float, str]]:
    """
    Display words (after full-sentence to_display_text normalization) with strictly monotonic
    [start, end] inside the TTS stem (faster-whisper alignment + bounded gap interpolation).
    """
    from pipeline.plain_language import count_syllables

    disp_words = to_display_text(text).split()
    if not disp_words:
        return []

    spoken_words: list[str] = []
    disp_spans: list[tuple[int, int, str]] = []
    for dw in disp_words:
        sub = to_tts_text(dw).split()
        if not sub:
            sub = [dw]
        s0 = len(spoken_words)
        spoken_words.extend(sub)
        disp_spans.append((s0, len(spoken_words), dw))

    n_sp = len(spoken_words)
    times: list[tuple[float, float] | None] = [None] * n_sp
    dur = max(0.1, len(pcm) / float(sr))

    try:
        pcm16 = _resample(pcm, sr, 16000)
        segs, _ = _whisper_model().transcribe(pcm16, word_timestamps=True, language="en")
        asr_raw = [(float(w.start), float(w.end), str(w.word).strip()) for s in segs for w in (s.words or []) if str(w.word).strip()]
        # Expand any numeric ASR token into spoken words so SequenceMatcher matches 1:1 with spoken_words
        asr: list[tuple[float, float, str]] = []
        for a0, a1, aw in asr_raw:
            sub_asr = to_tts_text(aw).split() or [aw]
            m_len = len(sub_asr)
            span = max(0.02, a1 - a0)
            for idx, sw in enumerate(sub_asr):
                asr.append((a0 + span * (idx / m_len), a0 + span * ((idx + 1) / m_len), sw))

        def _n(w: str) -> str:
            return re.sub(r"[^a-z0-9]", "", w.lower())

        sm = SequenceMatcher(a=[_n(w) for w in spoken_words], b=[_n(w[2]) for w in asr], autojunk=False)
        for blk in sm.get_matching_blocks():
            for k in range(blk.size):
                a0, a1, _ = asr[blk.b + k]
                times[blk.a + k] = (float(a0), float(a1))
    except Exception:  # noqa: BLE001
        pass

    weights = [max(1, count_syllables(w)) for w in spoken_words]

    # Interpolate any unmatched spans [i..j) strictly between neighboring matched anchors [left_end, right_start]
    i = 0
    while i < n_sp:
        if times[i] is not None:
            i += 1
            continue
        j = i
        while j < n_sp and times[j] is None:
            j += 1
        left_t = times[i - 1][1] if i > 0 and times[i - 1] is not None else 0.0
        right_t = times[j][0] if j < n_sp and times[j] is not None else dur
        if right_t <= left_t + 0.04 * (j - i):
            right_t = min(dur, left_t + 0.06 * (j - i))
        span_w = float(sum(weights[i:j])) or 1.0
        cum = 0.0
        for k in range(i, j):
            w_k = weights[k]
            t0 = left_t + (right_t - left_t) * (cum / span_w)
            t1 = left_t + (right_t - left_t) * ((cum + w_k) / span_w)
            times[k] = (t0, max(t0 + 0.04, t1))
            cum += w_k
        i = j

    # Enforce strict monotonic non-overlapping spoken word times
    mono_spoken: list[tuple[float, float]] = []
    cursor_t = 0.0
    for k in range(n_sp):
        t0, t1 = times[k] or (cursor_t, cursor_t + 0.05)
        t0 = max(cursor_t, min(t0, dur - 0.04))
        t1 = max(t0 + 0.04, min(t1, dur))
        mono_spoken.append((t0, t1))
        cursor_t = t1

    out: list[tuple[float, float, str]] = []
    for s0, s1, dw in disp_spans:
        w_start = mono_spoken[s0][0]
        w_end = mono_spoken[s1 - 1][1]
        out.append((round(w_start, 3), round(max(w_end, w_start + 0.05), 3), dw))
    return out


def _phrases(words: list[tuple[float, float, str]], max_words: int) -> list[tuple[float, float, list[str]]]:
    out: list[tuple[float, float, list[str]]] = []
    cur: list[tuple[float, float, str]] = []
    for w in words:
        cur.append(w)
        if len(cur) >= max_words or re.search(r"[.,]$", w[2]):
            out.append((cur[0][0], cur[-1][1], [x[2] for x in cur]))
            cur = []
    if cur:
        out.append((cur[0][0], cur[-1][1], [x[2] for x in cur]))
    return out


def synthesize_tts_track(
    project_dir: Path,
    clip_files: list[Path],
    clip_scripts: list[str],
    native_windows: list[dict[str, Any]] | None = None,
    sr: int = 48000,
    voice: str | None = None,
    speed: float | None = None,
) -> tuple[np.ndarray, list[dict[str, Any]], list[tuple[float, float, list[str]]]]:
    """Returns (concatenated voice pcm, per-clip windows compatible with assembly, subtitle events)."""
    use_voice = str(voice or VOICE_FALLBACK_VOICE)
    use_speed = float(speed if speed is not None else VOICE_FALLBACK_SPEED)
    n = len(clip_scripts)
    piv = pivot_clip_index(n)
    fps = int(VIDEO_FPS)
    cache = Path(project_dir) / "04_audio" / "tts_fallback"
    lo_spd, hi_spd = VOICE_FALLBACK_VIDEO_SPEED_RANGE
    segments: list[np.ndarray] = []
    windows: list[dict[str, Any]] = []
    events: list[tuple[float, float, list[str]]] = []
    cursor = 0.0
    prev_ev_end = 0.0
    for i, (cf, text) in enumerate(zip(clip_files[:n], clip_scripts)):
        line = synthesize_line(text, sr=sr, cache_dir=cache, clip_no=i + 1, voice=use_voice, speed=use_speed)
        tts_dur = len(line) / float(sr)
        hold = FINAL_TAIL_SEC if i == n - 1 else (CLIP_PRE_PIVOT_HOLD_SEC if i == piv - 1 else CLIP_VISUAL_HOLD_SEC)
        out_dur = TTS_LEAD_SEC + tts_dur + hold
        c_frames = max(30, int(round(out_dur * fps)))
        out_dur = c_frames / float(fps)
        clip_dur = _clip_duration(Path(cf))
        start = float((native_windows[i] or {}).get("trim_start", 0.0)) if native_windows and i < len(native_windows) else 0.0
        clip_speed = AV_SPEEDUP_FACTOR
        if start + out_dur * clip_speed > clip_dur - 0.05:
            start = max(0.0, clip_dur - 0.05 - out_dur * clip_speed)
        if start + out_dur * clip_speed > clip_dur - 0.05:
            start = 0.0
            clip_speed = (clip_dur - 0.05) / out_dur  # always fits the source: never clone frames
        clip_speed = min(hi_spd, clip_speed)
        seg = np.zeros(int(round(out_dur * sr)), dtype=np.float32)
        a0 = int(round(TTS_LEAD_SEC * sr))
        seg[a0 : a0 + len(line)] = line[: max(0, len(seg) - a0)]
        fade = int(0.04 * sr)
        if i == n - 1 and len(seg) > fade * 3:
            seg[-fade * 2 :] *= np.linspace(1.0, 0.0, fade * 2, dtype=np.float32)
        segments.append(seg)
        windows.append(
            {
                "trim_start": round(start, 4),
                "trim_end": round(start + out_dur * clip_speed, 4),
                "trimmed_dur": round(out_dur, 4),
                "speedup_factor": round(clip_speed, 4),
                "speech_start": round(start + TTS_LEAD_SEC * clip_speed, 4),
                "speech_end": round(start + (TTS_LEAD_SEC + tts_dur) * clip_speed, 4),
                "has_speech": True,
                "voice_source": "tts_fallback",
                "voice_name": use_voice,
                "video_speed_warning": clip_speed < lo_spd,
                "pivot_clip_idx": piv,
            }
        )
        raw_phrases = _phrases(_word_times(line, sr, text), SUBTITLE_MAX_WORDS_PER_EVENT)
        clip_max_t = round(cursor + out_dur - 0.02, 2)
        for p_idx, (t0, t1, disp_words) in enumerate(raw_phrases):
            ev_s = round(max(prev_ev_end + 0.01 if prev_ev_end > 0 else 0.0, cursor + TTS_LEAD_SEC + t0), 2)
            # Clamp end time before the next phrase's start time so two events can never overlap
            if p_idx + 1 < len(raw_phrases):
                next_s = round(cursor + TTS_LEAD_SEC + raw_phrases[p_idx + 1][0], 2)
                ev_e = round(min(clip_max_t, cursor + TTS_LEAD_SEC + t1, max(ev_s + 0.06, next_s - 0.01)), 2)
            else:
                ev_e = round(min(clip_max_t, max(ev_s + 0.08, cursor + TTS_LEAD_SEC + t1)), 2)
            if ev_e <= ev_s:
                ev_e = round(ev_s + 0.06, 2)
            events.append((ev_s, ev_e, disp_words))
            prev_ev_end = ev_e
        cursor += out_dur
    return np.concatenate(segments), windows, events


def resolve_voice_track(
    project_dir: Path,
    clip_files: list[Path],
    clip_scripts: list[str],
    native_res: tuple[np.ndarray, list[dict[str, Any]]] | None,
    sr: int = 48000,
) -> dict[str, Any]:
    """
    Decides the narration source for assembly. Returns
    {'source': 'native'|'tts_fallback', 'res': (pcm, windows), 'events': [...] | None, 'report': {...}}.
    Raises RuntimeError when the native voice fails and the fallback is disabled.
    """
    project_dir = Path(project_dir)
    audio_dir = project_dir / "04_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    force = None
    override_voice = None
    override_speed = None
    vs = audio_dir / "voice_source.json"
    if vs.exists():
        try:
            vs_data = json.loads(vs.read_text(encoding="utf-8"))
            force = vs_data.get("force")
            override_voice = vs_data.get("voice")
            override_speed = vs_data.get("speed")
        except Exception:  # noqa: BLE001
            force = None
    use_voice = str(override_voice or VOICE_FALLBACK_VOICE)
    use_speed = float(override_speed if override_speed is not None else VOICE_FALLBACK_SPEED)
    if force == "tts_fallback":
        f0_report = {"passed": False, "reason": "forced_tts_fallback", "regenerate_clips": []}
    else:
        try:
            from pipeline.flow_live_single_worker import analyze_flow_clip_candidate

            f0s = [float(analyze_flow_clip_candidate(cf).get("f0_median_hz", 0.0)) for cf in clip_files[: len(clip_scripts)]]
            f0_report = evaluate_f0_series(f0s)
        except Exception as exc:  # noqa: BLE001
            f0_report = {"passed": False, "reason": f"F0 analysis failed: {exc}", "regenerate_clips": []}

    use_native = native_res is not None and f0_report.get("passed") and force != "tts_fallback"
    if force == "native" and native_res is not None:
        use_native = True
    report: dict[str, Any] = {"native_f0": f0_report, "forced": force}
    if use_native:
        report["source"] = "native"
        (audio_dir / "voice_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
        return {"source": "native", "res": native_res, "events": None, "report": report}
    if not VOICE_FALLBACK_ENABLED:
        raise RuntimeError(
            f"Native Flow narration is inconsistent ({f0_report}); regenerate clips "
            f"{f0_report.get('regenerate_clips')} or enable VOICE_FALLBACK_ENABLED. Pitch shifting is never applied."
        )
    pcm, windows, events = synthesize_tts_track(
        project_dir,
        clip_files,
        clip_scripts,
        native_windows=(native_res[1] if native_res else None),
        sr=sr,
        voice=use_voice,
        speed=use_speed,
    )
    report.update(
        {
            "source": "tts_fallback",
            "engine": "kokoro-onnx",
            "voice": use_voice,
            "speed": use_speed,
            "broadcast_vocal_chain": "R41_highpass85_3bandEQ_comp3.5_limiter",
            "video_speed_per_clip": [w["speedup_factor"] for w in windows],
            "video_speed_warnings": [i + 1 for i, w in enumerate(windows) if w.get("video_speed_warning")],
        }
    )
    (audio_dir / "voice_report.json").write_text(json.dumps(report, indent=2), encoding="utf-8")
    return {"source": "tts_fallback", "res": (pcm, windows), "events": events, "report": report}
