"""
ALL ABOUT BRAIN - Voice track resolver, Neuro-Diorama continuous storyteller TTS, and local fallback (R49, R58, R63).

1. Standard 10-clip Shorts (`resolve_project_voice_track`, R49):
   - Native Google Flow narration when per-clip F0 passes the semitone gate (`voice_consistency`), else local Kokoro TTS (`kokoro-onnx`).
   - Override: `04_audio/voice_source.json` `{"force": "native" | "tts_fallback"}`.
2. Neuro-Diorama 3-Minute Long-Shorts (`synthesize_continuous_diorama_track`, R58/R63):
   - Default Schema v7 (`lowpoly_pastel_v7`): Act-continuous `edge-tts` (`en-US-AndrewMultilingualNeural`, unified `+8%` / `1.08x`,
     `+14Hz` high-tenor pitch, `-10%` internal vocoder headroom, `kokoro-onnx` `1.08x` offline fallback) with natural human breath trimming
     (`0.28s` threshold -> `0.14s` cosine overlap-add breath) and tear-free Silk Clean linear EQ (`STORYTELLER_VOCAL_FILTER`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
import re
import subprocess
import tempfile
import wave
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    AV_SPEEDUP_FACTOR,
    CLIP_PRE_PIVOT_HOLD_SEC,
    CLIP_VISUAL_HOLD_SEC,
    DEFAULT_VOICE_SOURCE,
    END_FADE_SEC,
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
from pipeline.plain_language import to_display_text, to_expressive_tts_text, to_tts_text
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


def _write_mono_wav(path: Path, pcm: np.ndarray, sr: int) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    pcm_i16 = (np.clip(pcm, -0.98, 0.98) * 32767.0).astype(np.int16)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_i16.tobytes())


def _resolve_kokoro_voice(voice: str | None) -> str:
    """Maps empty or `edge-tts` neural voice IDs (e.g. `en-US-AndrewMultilingualNeural`) to `VOICE_FALLBACK_VOICE`."""
    raw = str(voice or "").strip()
    if not raw or "neural" in raw.lower() or "-" in raw:
        return VOICE_FALLBACK_VOICE
    return raw


def _master_storyteller_vocal(pcm: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    """Applies `STORYTELLER_VOCAL_FILTER` (Silk Clean EQ) and peak-safe RMS normalization to mono float32 PCM."""
    with tempfile.TemporaryDirectory(prefix="aab_tts_story_") as td:
        src = Path(td) / "in.f32"
        src.write_bytes(pcm.astype(np.float32).tobytes())
        af = f"aresample={sr_out}:resampler=soxr,{STORYTELLER_VOCAL_FILTER}"
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
    out = np.frombuffer(res.stdout, dtype=np.float32).copy()
    active = out[np.abs(out) > 0.02]
    rms = float(np.sqrt(np.mean(np.square(active)))) if active.size else float(np.sqrt(np.mean(np.square(out)) + 1e-9))
    peak = float(np.max(np.abs(out))) if out.size else 0.0
    max_clean_gain = (0.92 / peak) if peak > 1e-5 else 3.5
    gain = min((10.0 ** (TTS_TARGET_ACTIVE_DB / 20.0)) / max(rms, 1e-4), max_clean_gain, 3.5)
    return np.clip(out * gain, -0.95, 0.95).astype(np.float32)


def synthesize_line(
    text: str,
    sr: int = 48000,
    cache_dir: Path | None = None,
    clip_no: int = 0,
    voice: str | None = None,
    speed: float | None = None,
    vocal_profile: str = "broadcast",
) -> np.ndarray:
    """One narration line -> mono float32 PCM at sr, fixed channel voice / speed, vocal chain + active level normalized."""
    use_voice = _resolve_kokoro_voice(voice)
    use_speed = float(speed if speed is not None else VOICE_FALLBACK_SPEED)
    is_storyteller = str(vocal_profile or "broadcast").strip().lower() == "storyteller"
    chain_tag = "storyteller_silk_v1" if is_storyteller else "r41_v2"
    spoken = to_tts_text(text)
    key = hashlib.sha256(f"{spoken}|{use_voice}|{use_speed}|{chain_tag}|{sr}".encode()).hexdigest()[:16]
    cached = Path(cache_dir) / f"clip_{clip_no}_{key}.f32" if cache_dir else None
    wav_out = Path(cache_dir) / f"clip_{clip_no}.wav" if (cache_dir and clip_no > 0) else None
    if cached and cached.exists():
        pcm = np.frombuffer(cached.read_bytes(), dtype=np.float32).copy()
        if wav_out is not None and not wav_out.exists():
            _write_mono_wav(wav_out, pcm, sr)
        return pcm
    audio, sr_in = _kokoro().create(spoken, voice=use_voice, speed=use_speed, lang="en-us")
    raw_f32 = np.asarray(audio, dtype=np.float32)
    if is_storyteller:
        pcm = _master_storyteller_vocal(raw_f32, int(sr_in), sr)
    else:
        pcm = _master_broadcast_vocal(raw_f32, int(sr_in), sr)
    # trim leading / trailing silence
    env = np.abs(pcm) > 0.01
    if env.any():
        first = max(0, int(np.argmax(env)) - int(0.02 * sr))
        last = min(len(pcm), len(pcm) - int(np.argmax(env[::-1])) + int(0.06 * sr))
        pcm = pcm[first:last]
    if not is_storyteller:
        active = pcm[np.abs(pcm) > 0.02]
        rms = float(np.sqrt(np.mean(np.square(active)))) if active.size else float(np.sqrt(np.mean(np.square(pcm)) + 1e-9))
        gain = min((10.0 ** (TTS_TARGET_ACTIVE_DB / 20.0)) / max(rms, 1e-4), 4.0)
        pcm = np.clip(pcm * gain, -0.95, 0.95).astype(np.float32)
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_bytes(pcm.tobytes())
    if wav_out is not None:
        _write_mono_wav(wav_out, pcm, sr)
    return pcm


def _clip_duration(path: Path) -> float:
    from pipeline.media_cache import cached_by_clip_stat

    def _probe_dur(p: Path) -> float:
        res = subprocess.run([_ffmpeg(), "-nostdin", "-hide_banner", "-i", str(p)], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", res.stderr or "")
        if not m:
            return 8.0
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    return float(cached_by_clip_stat(Path(path), namespace="clip_dur_v1", compute_fn=_probe_dur, stage_on_miss=False))


def _whisper_model():
    global _WHISPER_MODEL
    if _WHISPER_MODEL is None:
        from faster_whisper import WhisperModel  # type: ignore

        _WHISPER_MODEL = WhisperModel(
            "base.en",
            device="cpu",
            compute_type="int8",
            cpu_threads=max(1, min(4, os.cpu_count() or 2)),
        )
    return _WHISPER_MODEL


def _word_times_aligned(
    pcm: np.ndarray,
    sr: int,
    text: str,
    pre_asr_raw: list[tuple[float, float, str]] | None = None,
) -> tuple[list[tuple[float, float, str]], bool]:
    """
    Display words (after full-sentence to_display_text normalization) with strictly monotonic
    [start, end] inside the TTS stem (faster-whisper alignment + drift-bounded gap interpolation).
    Returns `(word_tuples, used_real_asr)` so synthetic fallback timings never poison disk caches.
    """
    from pipeline.plain_language import count_syllables

    disp_words = to_display_text(text).split()
    if not disp_words:
        return [], False

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
    eff_min_w = 0.06 if dur >= 0.06 * n_sp else max(0.02, min(0.06, (dur * 0.85) / max(1, n_sp)))
    weights = [max(1, count_syllables(w)) for w in spoken_words]
    total_syl_w = float(sum(weights)) or 1.0
    exp_starts: list[float] = []
    cum_exp = 0.0
    for w_k in weights:
        exp_starts.append(dur * (cum_exp / total_syl_w))
        cum_exp += w_k

    used_real_asr = False
    try:
        # Empty `pre_asr_raw` (`None` or `[]`) on a non-empty sentence is treated as a cache miss
        # and retried with single-sentence Whisper transcription before linear fallback.
        if pre_asr_raw:
            asr_raw = pre_asr_raw
        else:
            pcm16 = _resample(pcm, sr, 16000)
            segs, _ = _whisper_model().transcribe(pcm16, word_timestamps=True, language="en")
            asr_raw = [
                (float(w.start), float(w.end), str(w.word).strip())
                for s in segs
                for w in (s.words or [])
                if str(w.word).strip()
            ]
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
        max_single_drift = max(0.75, 0.38 * dur)
        cand_anchors: list[tuple[int, float, float]] = []
        for blk in sm.get_matching_blocks():
            if blk.size <= 0:
                continue
            for k in range(blk.size):
                w_idx = blk.a + k
                a0, a1, _ = asr[blk.b + k]
                # Guard isolated 1-word matches from snapping to a repeated function word in a misheard clause
                if blk.size == 1 and abs(float(a0) - exp_starts[w_idx]) > max_single_drift:
                    continue
                earliest_t0 = w_idx * eff_min_w
                latest_t1 = max(earliest_t0 + eff_min_w, dur - (n_sp - 1 - w_idx) * eff_min_w)
                latest_t0 = max(earliest_t0, latest_t1 - eff_min_w)
                c0 = max(earliest_t0, min(float(a0), latest_t0))
                c1 = max(c0 + eff_min_w, min(max(float(a1), c0 + eff_min_w), latest_t1))
                cand_anchors.append((w_idx, c0, c1))

        accepted = 0
        prev_idx = -1
        prev_t0 = 0.0
        prev_t1 = 0.0
        for w_idx, c0, c1 in cand_anchors:
            req_gap = max(0, w_idx - prev_idx - 1) * eff_min_w
            if prev_idx >= 0 and c0 < prev_t1 + req_gap:
                # Allow minor <=30ms Whisper boundary overlap if previous anchor still keeps >= eff_min_w
                trimmed_prev_t1 = max(prev_t0 + eff_min_w, c0 - req_gap)
                if c0 >= trimmed_prev_t1 + req_gap - 1e-6 and trimmed_prev_t1 <= prev_t1 + 1e-6 and (prev_t1 - trimmed_prev_t1) <= 0.04:
                    times[prev_idx] = (prev_t0, trimmed_prev_t1)
                    prev_t1 = trimmed_prev_t1
                else:
                    # Drop the anchor that drifted farther from expected syllable trajectory
                    prev_drift = abs(prev_t0 - exp_starts[prev_idx])
                    curr_drift = abs(c0 - exp_starts[w_idx])
                    if curr_drift < prev_drift and (w_idx == 0 or c0 >= 0.0):
                        # Re-validate against the earlier kept anchor before `prev_idx`
                        times[prev_idx] = None
                        earlier = [(m_i, times[m_i][0], times[m_i][1]) for m_i in range(prev_idx) if times[m_i] is not None]
                        if earlier:
                            e_i, e_t0, e_t1 = earlier[-1]
                            if c0 < e_t1 + max(0, w_idx - e_i - 1) * eff_min_w:
                                times[prev_idx] = (prev_t0, prev_t1)
                                continue
                        times[w_idx] = (c0, c1)
                        prev_idx, prev_t0, prev_t1 = w_idx, c0, c1
                    continue
            times[w_idx] = (c0, c1)
            prev_idx, prev_t0, prev_t1 = w_idx, c0, c1
            accepted += 1
        used_real_asr = bool(asr_raw) and accepted > 0
    except Exception:  # noqa: BLE001
        used_real_asr = False

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
        n_gap_w = j - i
        min_span_need = n_gap_w * eff_min_w
        if right_t < left_t + min_span_need:
            right_t = min(dur, left_t + min_span_need)
        extra_span = max(0.0, (right_t - left_t) - min_span_need)
        span_w = float(sum(weights[i:j])) or 1.0
        cur_t = left_t
        for k in range(i, j):
            w_k = weights[k]
            w_dur = eff_min_w + extra_span * (w_k / span_w)
            times[k] = (cur_t, cur_t + w_dur)
            cur_t += w_dur
        i = j

    # Enforce strict monotonic non-overlapping spoken word times with >= eff_min_w floor
    mono_spoken: list[tuple[float, float]] = []
    cursor_t = 0.0
    for k in range(n_sp):
        rem_after = n_sp - 1 - k
        max_t1 = max(cursor_t + eff_min_w, dur - rem_after * eff_min_w)
        max_t0 = max(cursor_t, max_t1 - eff_min_w)
        raw_t0, raw_t1 = times[k] or (cursor_t, cursor_t + eff_min_w)
        t0 = max(cursor_t, min(raw_t0, max_t0))
        t1 = max(t0 + eff_min_w, min(max(raw_t1, t0 + eff_min_w), max_t1))
        mono_spoken.append((t0, t1))
        cursor_t = t1

    out: list[tuple[float, float, str]] = []
    for s0, s1, dw in disp_spans:
        w_start = mono_spoken[s0][0]
        w_end = mono_spoken[s1 - 1][1]
        out.append((round(w_start, 3), round(max(w_end, w_start + eff_min_w), 3), dw))
    return out, used_real_asr


def _word_times(
    pcm: np.ndarray,
    sr: int,
    text: str,
    pre_asr_raw: list[tuple[float, float, str]] | None = None,
) -> list[tuple[float, float, str]]:
    """
    Display words (after full-sentence to_display_text normalization) with strictly monotonic
    [start, end] inside the TTS stem (faster-whisper alignment + bounded gap interpolation).
    """
    return _word_times_aligned(pcm=pcm, sr=sr, text=text, pre_asr_raw=pre_asr_raw)[0]


_DANGLING_TAIL_WORDS: frozenset[str] = frozenset(
    {
        "a", "an", "the", "of", "to", "in", "on", "at", "by", "for", "with", "from", "into",
        "onto", "upon", "under", "beneath", "behind", "across", "along", "through", "than",
        "and", "or", "but", "yet", "nor", "as", "his", "her", "your", "their", "its", "my", "our",
    }
)


def _phrases(words: list[tuple[float, float, str]], max_words: int) -> list[tuple[float, float, list[str]]]:
    """
    Balanced syntactic phrase chunker (<= max_words per event):
      - Respects comma/period clause boundaries.
      - Never ends a chunk on a dangling article/preposition/possessive or bare numeral before its unit.
      - Eliminates 1-word trailing flashes (<0.35s) by splitting 4 -> 2+2, 7 -> 3+2+2, 10 -> 3+3+2+2.
    """
    if not words:
        return []
    m = max(2, int(max_words))
    # First split at internal punctuation boundaries (, ; : .) so clauses stay clean
    clauses: list[list[tuple[float, float, str]]] = []
    cur_c: list[tuple[float, float, str]] = []
    for w in words:
        cur_c.append(w)
        if re.search(r"[,;:.!?]$", w[2]):
            clauses.append(cur_c)
            cur_c = []
    if cur_c:
        clauses.append(cur_c)

    def _is_dangling(token: str) -> bool:
        clean = re.sub(r"[^a-z0-9%]", "", token.lower())
        if not clean:
            return False
        if clean in _DANGLING_TAIL_WORDS:
            return True
        # Bare digits without % should stay attached to their following unit noun ('13 pounds', '18 months')
        if clean.isdigit():
            return True
        return False

    out: list[tuple[float, float, list[str]]] = []
    for cl in clauses:
        n = len(cl)
        idx = 0
        while idx < n:
            rem = n - idx
            if rem <= m:
                chunk = cl[idx:]
                idx = n
            elif rem == m + 1 and m >= 3:
                # 4 words -> 2 + 2 instead of 3 + 1 orphan
                take = 2
                if take < rem and _is_dangling(cl[idx + take - 1][2]) and take > 1 and not _is_dangling(cl[idx][2]):
                    take = 1 if rem - 1 <= m else 2
                chunk = cl[idx : idx + take]
                idx += take
            else:
                take = m
                # Step back by 1 word if ending on a dangling article/preposition/numeral
                if _is_dangling(cl[idx + take - 1][2]) and take >= 2:
                    take -= 1
                # Avoid leaving a 1-word orphan at the end of the clause
                if (n - (idx + take)) == 1 and take >= 2:
                    take -= 1
                chunk = cl[idx : idx + take]
                idx += take
            out.append((chunk[0][0], chunk[-1][1], [x[2] for x in chunk]))

    # Pass 2: Forward-merge 1-word comma/adverb openers ('Next,', 'Today,', 'Faster') & rebalance 1+3 -> 2+2
    fwd: list[tuple[float, float, list[str]]] = []
    p_i = 0
    while p_i < len(out):
        ev = out[p_i]
        if (
            p_i + 1 < len(out)
            and len(ev[2]) == 1
            and not re.search(r"[.!?]$", ev[2][-1])
            and (out[p_i + 1][0] - ev[1]) < 0.35
        ):
            nxt = out[p_i + 1]
            if len(ev[2]) + len(nxt[2]) <= m:
                fwd.append((ev[0], nxt[1], ev[2] + nxt[2]))
                p_i += 2
                continue
            if len(nxt[2]) == m and m >= 3 and not re.search(r"[,;:]$", ev[2][-1]):
                # e.g. ['Faster'] + ['than', 'a', 'blink,'] -> ['Faster', 'than'] + ['a', 'blink,']
                mid_t = round(0.5 * (ev[1] + nxt[0]) + 0.30 * (nxt[1] - nxt[0]), 3)
                fwd.append((ev[0], mid_t, [ev[2][0], nxt[2][0]]))
                fwd.append((round(mid_t + 0.01, 3), nxt[1], nxt[2][1:]))
                p_i += 2
                continue
        fwd.append(ev)
        p_i += 1

    # Pass 3: Eliminate dangling trailing articles ('a', 'an', 'the') by shifting article to next noun phrase
    for k in range(len(fwd) - 1):
        c0_s, c0_e, w0 = fwd[k]
        c1_s, c1_e, w1 = fwd[k + 1]
        tail_clean = re.sub(r"[^a-z]", "", w0[-1].lower())
        if (
            len(w0) >= 2
            and tail_clean in {"a", "an", "the"}
            and not re.search(r"[,;:.!?]$", w0[-1])
            and len(w1) < m
            and (c1_s - c0_e) < 0.25
        ):
            art = w0[-1]
            rem_w0 = w0[:-1]
            shift_t = round(max(c0_s + 0.14, c0_e - 0.10), 3)
            # If rem_w0 becomes 1 word (e.g. ['than'], ['of'], ['into']), attach it to previous chunk if room
            if (
                len(rem_w0) == 1
                and k > 0
                and len(fwd[k - 1][2]) < m
                and not re.search(r"[,;:.!?]$", fwd[k - 1][2][-1])
                and (c0_s - fwd[k - 1][1]) < 0.25
            ):
                p_s, _, p_w = fwd[k - 1]
                fwd[k - 1] = (p_s, shift_t, p_w + rem_w0)
                fwd[k] = (shift_t, shift_t, [])
                fwd[k + 1] = (round(shift_t + 0.01, 3), c1_e, [art] + w1)
            else:
                fwd[k] = (c0_s, shift_t, rem_w0)
                fwd[k + 1] = (round(shift_t + 0.01, 3), c1_e, [art] + w1)
    fwd = [x for x in fwd if x[2]]

    # Pass 4: Merge any remaining single-word ultra-short (<0.34s) chunk backward when room permits
    merged: list[tuple[float, float, list[str]]] = []
    for ev in fwd:
        if (
            merged
            and len(ev[2]) == 1
            and (ev[1] - ev[0]) < 0.34
            and len(merged[-1][2]) < m
            and not re.search(r"[.!?]$", merged[-1][2][-1])
        ):
            prev = merged.pop()
            merged.append((prev[0], ev[1], prev[2] + ev[2]))
        else:
            merged.append(ev)
    return merged


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
        start = 0.0
        clip_speed = AV_SPEEDUP_FACTOR
        if out_dur * clip_speed > clip_dur - 0.05:
            clip_speed = (clip_dur - 0.05) / out_dur  # always fits the source: never clone frames
        clip_speed = min(hi_spd, clip_speed)
        seg = np.zeros(int(round(out_dur * sr)), dtype=np.float32)
        a0 = int(round(TTS_LEAD_SEC * sr))
        line_scaled = np.clip(line * (1.10 if i >= piv else 0.96), -0.88, 0.88).astype(np.float32)
        seg[a0 : a0 + len(line_scaled)] = line_scaled[: max(0, len(seg) - a0)]
        end_fade_n = int(END_FADE_SEC * sr)
        if i == n - 1 and len(seg) > end_fade_n * 2:
            seg[-end_fade_n:] *= np.linspace(0.20, 0.0, end_fade_n, dtype=np.float32)
        segments.append(seg)
        windows.append(
            {
                "clip_dur": clip_dur,
                "trim_start": round(start, 4),
                "trim_end": round(start + out_dur * clip_speed, 4),
                "src_trimmed_dur": round(out_dur * clip_speed, 4),
                "trimmed_dur": round(out_dur, 4),
                "speedup_factor": round(clip_speed, 4),
                "speech_start": round(start + TTS_LEAD_SEC * clip_speed, 4),
                "speech_end": round(start + (TTS_LEAD_SEC + tts_dur) * clip_speed, 4),
                "has_speech": True,
                "voice_source": "tts_fallback",
                "voice_name": use_voice,
                "video_speed_warning": clip_speed < lo_spd,
                "pivot_clip_idx": piv,
                "broke_early": False,
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
    default_tts_lock = DEFAULT_VOICE_SOURCE == "tts" and force != "native"
    if force in ("tts_fallback", "tts") or default_tts_lock:
        f0_report = {
            "passed": True,
            "reason": "default_voice_source_tts" if default_tts_lock else "forced_tts_fallback",
            "regenerate_clips": [],
        }
    else:
        try:
            from pipeline.flow_live_single_worker import analyze_flow_clip_candidate

            f0s = [float(analyze_flow_clip_candidate(cf).get("f0_median_hz", 0.0)) for cf in clip_files[: len(clip_scripts)]]
            f0_report = evaluate_f0_series(f0s)
        except Exception as exc:  # noqa: BLE001
            f0_report = {"passed": False, "reason": f"F0 analysis failed: {exc}", "regenerate_clips": []}

    use_native = (
        native_res is not None
        and f0_report.get("passed")
        and force not in ("tts_fallback", "tts")
        and not default_tts_lock
    )
    if force == "native" and native_res is not None:
        use_native = True
    report: dict[str, Any] = {"native_f0": f0_report, "forced": force or ("tts" if default_tts_lock else None)}
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


def _syllable_word_times(dur_sec: float, text: str) -> list[tuple[float, float, str]]:
    """Fast monotonic syllable-proportional word spans inside `[0, dur_sec]`."""
    from pipeline.plain_language import count_syllables

    disp_words = to_display_text(text).split()
    if not disp_words:
        return []
    weights = [max(1, count_syllables(to_tts_text(w) or w)) for w in disp_words]
    total_w = float(sum(weights)) or 1.0
    out: list[tuple[float, float, str]] = []
    cum = 0.0
    for w_txt, wt in zip(disp_words, weights):
        t0 = dur_sec * (cum / total_w)
        t1 = dur_sec * ((cum + wt) / total_w)
        out.append((round(t0, 3), round(max(t0 + 0.04, t1), 3), w_txt))
        cum += wt
    return out


def _apply_pitch_preserving_atempo(pcm: np.ndarray, sr: int, factor: float) -> np.ndarray:
    """Applies FFmpeg pitch-preserving `atempo` (never `asetrate`) within `[0.5, 2.0]`."""
    if abs(factor - 1.0) < 0.003:
        return pcm.astype(np.float32)
    f_clamped = max(0.5, min(2.0, float(factor)))
    with tempfile.TemporaryDirectory(prefix="aab_diorama_atempo_") as td:
        src = Path(td) / "in.f32"
        src.write_bytes(pcm.astype(np.float32).tobytes())
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-f", "f32le", "-ar", str(sr), "-ac", "1", "-i", str(src),
                "-af", f"atempo={f_clamped:.5f}", "-f", "f32le", "-ac", "1", "pipe:1",
            ],
            capture_output=True, check=False, timeout=120, stdin=subprocess.DEVNULL,
        )
    if res.returncode != 0 or not res.stdout:
        return pcm.astype(np.float32)
    return np.frombuffer(res.stdout, dtype=np.float32).copy()


STORYTELLER_VOCAL_FILTER = (
    "volume=-3dB,"
    "highpass=f=78,"
    "equalizer=f=135:t=q:w=1.1:g=1.5,"
    "equalizer=f=330:t=q:w=1.4:g=-1.1,"
    "equalizer=f=1850:t=q:w=1.1:g=0.4,"
    "equalizer=f=3150:t=q:w=1.2:g=-1.5,"
    "equalizer=f=6200:t=q:w=0.9:g=-1.5,"
    "acompressor=threshold=-18dB:ratio=1.25:attack=25:release=220:makeup=1.14,"
    "alimiter=limit=0.88:attack=5:release=60:level=disabled"
)


def _humanize_vocoder_pcm(pcm: np.ndarray, sr: int) -> np.ndarray:
    """
    Studio Preamp & Condenser De-Vocoder Stage (0.000s timing change, 0.0Hz pitch change):
      1. Subtle asymmetric 2nd-order harmonic soft-saturation (analog preamp/vocal-cord warmth) with >65Hz DC block.
      2. Soft >11.2 kHz condenser-mic air reconstruction correlated to active speech consonants so 24kHz TTS stems
         never exhibit a razor-sharp 12kHz digital Nyquist brickwall inside a 48kHz master.
    """
    arr = np.asarray(pcm, dtype=np.float32)
    if arr.size < 64:
        return arr.copy()
    from scipy import signal as sp_signal

    # 1. Subtle asymmetric even-order preamp warmth (~1.1% 2nd-harmonic glue, DC-blocked)
    drive = 1.07
    even = 0.016
    warmed = (np.tanh(drive * arr + even * np.square(arr)) / drive).astype(np.float32)
    if sr >= 8000 and arr.size > 128:
        sos_dc = sp_signal.butter(1, 65.0, btype="high", fs=float(sr), output="sos")
        warmed = sp_signal.sosfilt(sos_dc, warmed).astype(np.float32)

    # 2. Gentle 11.2-15.0 kHz studio condenser air shelf derived from upper-voiced 5.2-8.6 kHz harmonics
    if sr >= 44100 and arr.size > 512:
        hi_nyq = min(15000.0, sr * 0.45)
        if hi_nyq > 11600.0:
            sos_src = sp_signal.butter(2, [5200.0, 8600.0], btype="bandpass", fs=float(sr), output="sos")
            src_hf = sp_signal.sosfilt(sos_src, warmed).astype(np.float32)
            exc = (src_hf * np.abs(src_hf)).astype(np.float32)
            sos_air = sp_signal.butter(2, [11200.0, hi_nyq], btype="bandpass", fs=float(sr), output="sos")
            air_band = sp_signal.sosfilt(sos_air, exc).astype(np.float32)
            air_rms = float(np.sqrt(np.mean(np.square(air_band)) + 1e-12))
            body_rms = float(np.sqrt(np.mean(np.square(warmed)) + 1e-12))
            if air_rms > 1e-7 and body_rms > 1e-6:
                # Target ~ -30 dB subtle condenser air relative to speech RMS
                air_gain = min(12.0, (body_rms * 0.031) / air_rms)
                warmed = (warmed + air_band * air_gain).astype(np.float32)
    return np.clip(warmed, -0.96, 0.96).astype(np.float32)


def _apply_studio_booth_glue(
    master_voice: np.ndarray,
    sr: int,
    lead_sec: float,
    speech_end_sec: float,
) -> np.ndarray:
    """
    Damped Studio Vocal-Booth Acoustic Glue (0.000s timing change, exact sample-length parity):
      - Convolves active speech [0 : speech_end_sec] with ultra-short Haas-window booth early reflections
        (11.5ms, 17.8ms, 24.5ms low-passed at 3.2 kHz, -26.5 dB total wet, zero reverb tail) so spliced
        rush/stamp/brisk streams share one physical microphone space.
      - Replaces -inf dBFS mathematical zero vacuum between slices with -62 dBFS warm studio preamp room air.
    """
    out = np.asarray(master_voice, dtype=np.float32).copy()
    n_total = out.size
    s0 = max(0, min(n_total, int(round(lead_sec * sr))))
    s1 = max(s0, min(n_total, int(round(speech_end_sec * sr))))
    if s1 - s0 < int(0.15 * sr) or sr < 8000:
        return out
    from scipy import signal as sp_signal

    # 1. Haas-window (<26ms) damped booth early reflections (zero audible echo, natural chest/booth depth)
    ir_len = max(32, int(0.032 * sr))
    ir = np.zeros(ir_len, dtype=np.float32)
    for ms_delay, tap_gain in ((11.5, 0.028), (17.8, -0.019), (24.5, 0.012)):
        idx_d = min(ir_len - 1, int(round(ms_delay * 0.001 * sr)))
        ir[idx_d] += tap_gain
    sos_booth = sp_signal.butter(2, min(3200.0, sr * 0.42), btype="low", fs=float(sr), output="sos")
    ir = sp_signal.sosfilt(sos_booth, ir).astype(np.float32)
    seg = out[:s1]
    wet = sp_signal.fftconvolve(seg, ir, mode="full")[: len(seg)].astype(np.float32)
    out[:s1] = (0.988 * seg + wet).astype(np.float32)

    # 2. Continuous -62 dBFS (~0.00079 RMS) warm pink-filtered studio mic room air across [lead_sec : speech_end_sec]
    span_n = s1 - s0
    rng = np.random.default_rng(1073)
    raw_air = rng.standard_normal(span_n).astype(np.float32)
    sos_room = sp_signal.butter(
        2,
        [110.0, min(2200.0, sr * 0.40)],
        btype="bandpass",
        fs=float(sr),
        output="sos",
    )
    room_air = sp_signal.sosfilt(sos_room, raw_air).astype(np.float32)
    r_rms = float(np.sqrt(np.mean(np.square(room_air)) + 1e-12))
    target_rms = float(10.0 ** (-62.0 / 20.0))
    room_air = (room_air * (target_rms / r_rms)).astype(np.float32)
    fade_n = min(span_n // 4, int(0.035 * sr))
    if fade_n >= 4:
        env = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fade_n, dtype=np.float32))
        room_air[:fade_n] *= env
        room_air[-fade_n:] *= env[::-1]
    out[s0:s1] = np.clip(out[s0:s1] + room_air, -0.97, 0.97).astype(np.float32)
    return out


def _decode_mp3_storyteller_pcm(mp3_bytes: bytes, sr_out: int) -> np.ndarray:
    """Decodes edge-tts MP3 bytes to mono float32 PCM at `sr_out` with studio mic de-buzz EQ & preamp warmth."""
    with tempfile.TemporaryDirectory(prefix="aab_edge_mp3_") as td:
        src = Path(td) / "in.mp3"
        src.write_bytes(mp3_bytes)
        af = f"aresample={sr_out}:resampler=soxr,{STORYTELLER_VOCAL_FILTER}"
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error",
                "-i", str(src), "-af", af, "-f", "f32le", "-ac", "1", "pipe:1",
            ],
            capture_output=True, check=False, timeout=120, stdin=subprocess.DEVNULL,
        )
    if res.returncode != 0 or not res.stdout:
        raise RuntimeError(f"Failed decoding edge-tts MP3 bytes: {res.stderr.decode(errors='ignore')[:200]}")
    pcm = _humanize_vocoder_pcm(np.frombuffer(res.stdout, dtype=np.float32).copy(), sr_out)
    active = pcm[np.abs(pcm) > 0.02]
    rms = float(np.sqrt(np.mean(np.square(active)))) if active.size else float(np.sqrt(np.mean(np.square(pcm)) + 1e-9))
    peak = float(np.max(np.abs(pcm))) if pcm.size else 0.0
    max_clean_gain = (0.92 / peak) if peak > 1e-5 else 3.5
    gain = min((10.0 ** (TTS_TARGET_ACTIVE_DB / 20.0)) / max(rms, 1e-4), max_clean_gain, 3.5)
    return (pcm * gain).astype(np.float32)


def _run_coro_sync(coro: Any) -> Any:
    """Runs an async coroutine safely whether or not an event loop is already active on this thread."""
    import asyncio
    import threading

    try:
        asyncio.get_running_loop()
    except RuntimeError:
        return asyncio.run(coro)
    box: dict[str, Any] = {}

    def _target() -> None:
        try:
            box["res"] = asyncio.run(coro)
        except BaseException as exc:  # noqa: BLE001
            box["err"] = exc

    th = threading.Thread(target=_target, daemon=True)
    th.start()
    th.join(timeout=180)
    if th.is_alive():
        raise TimeoutError("Async TTS operation timed out after 180s")
    if "err" in box:
        raise box["err"]
    return box.get("res")


def _synthesize_edge_tts_acts(
    clean_sents: list[str],
    script_doc: dict[str, Any] | None,
    sr: int,
    cache_dir: Path,
    voice: str,
    rate: str,
    pitch: str = "+14Hz",
    volume: str = "-10%",
    sentence_rates: list[str] | None = None,
    rates_used_out: list[str] | None = None,
) -> list[np.ndarray]:
    """
    Synthesizes each Act in ONE unbroken continuous `edge-tts` pass (`en-US-AndrewMultilingualNeural`),
    preserving human cross-sentence breath and conversational pitch contour while slicing cleanly along
    contiguous `SentenceBoundary` timestamps so every sentence maps 1:1 to its visual cut.

    `sentence_rates` (1:1 with `clean_sents`, Prosody Plan B native gears): every Act is synthesized once per
    distinct rate it needs, and each sentence is taken from the stream matching its own rate, so no WSOLA
    post-stretch is required. If a non-base rate stream fails, its sentences fall back to the base `rate`
    stream; `rates_used_out` receives the rate each returned slice was actually synthesized at.
    """
    import edge_tts  # type: ignore

    cache_dir.mkdir(parents=True, exist_ok=True)
    act_groups: list[list[str]] = []
    if isinstance(script_doc, dict) and isinstance(script_doc.get("acts"), list):
        grouped = [
            [str(x).strip() for x in (a.get("sentences") or []) if str(x).strip()]
            for a in script_doc["acts"]
            if isinstance(a, dict)
        ]
        grouped = [g for g in grouped if g]
        if sum(len(g) for g in grouped) == len(clean_sents):
            act_groups = grouped
    if not act_groups:
        act_groups = [clean_sents[i : i + 7] for i in range(0, len(clean_sents), 7)]

    def _prep_for_act_stream(s: str) -> str:
        t = to_expressive_tts_text(s)
        # Convert internal mid-sentence '...' before words to ' — ' so SentenceBoundary never splits one sentence into two
        t = re.sub(r"\.\.\.\s+(?=[A-Za-z])", " — ", t)
        # Replace '!' with '.' in TTS stream to prevent high-pitch (+14Hz) neural vocoder overdrive/tearing
        t = t.replace("!", ".")
        if not re.search(r"[.!?]$", t):
            t += "."
        return t

    from pipeline.config import DIORAMA_TTS_BITRATE_BPS, DIORAMA_TTS_OUTPUT_FORMAT

    async def _stream_edge_high_bitrate(
        req_text: str,
        req_voice: str,
        req_rate: str,
        req_pitch: str,
        req_vol: str,
        conn: Any,
        connect_timeout: int = 8,
        receive_timeout: int = 35,
    ) -> tuple[bytes, list[dict[str, Any]]]:
        """
        Streams high-bitrate `DIORAMA_TTS_OUTPUT_FORMAT` (`audio-24khz-96kbitrate-mono-mp3`, 2x over 48kbps default)
        directly from Microsoft ReadAloud WebSocket with exact `DIORAMA_TTS_BITRATE_BPS` offset compensation and
        `SentenceBoundary` metadata intact (0.000s timing difference vs 48kbps).
        """
        import aiohttp  # type: ignore
        from xml.sax.saxutils import escape, unescape
        import edge_tts.communicate as ec_mod  # type: ignore

        tts_cfg = ec_mod.TTSConfig(req_voice, req_rate, req_vol, req_pitch, "SentenceBoundary")
        chunks_txt = list(
            ec_mod.split_text_by_byte_length(
                escape(ec_mod.remove_incompatible_characters(req_text)),
                4096,
            )
        )
        session_timeout = aiohttp.ClientTimeout(
            total=None,
            connect=None,
            sock_connect=connect_timeout,
            sock_read=receive_timeout,
        )
        audio_buf = bytearray()
        bounds: list[dict[str, Any]] = []
        offset_comp = 0
        cum_bytes = 0

        async with aiohttp.ClientSession(connector=conn, connector_owner=False, trust_env=True, timeout=session_timeout) as session:
            for part_txt in chunks_txt:
                chunk_bytes = 0
                got_audio = False
                ws_url = (
                    f"{ec_mod.WSS_URL}&ConnectionId={ec_mod.connect_id()}"
                    f"&Sec-MS-GEC={ec_mod.DRM.generate_sec_ms_gec()}"
                    f"&Sec-MS-GEC-Version={ec_mod.SEC_MS_GEC_VERSION}"
                )
                async with session.ws_connect(
                    ws_url,
                    compress=15,
                    headers=ec_mod.DRM.headers_with_muid(ec_mod.WSS_HEADERS),
                    ssl=ec_mod._SSL_CTX,
                ) as ws:
                    await ws.send_str(
                        f"X-Timestamp:{ec_mod.date_to_string()}\r\n"
                        "Content-Type:application/json; charset=utf-8\r\n"
                        "Path:speech.config\r\n\r\n"
                        '{"context":{"synthesis":{"audio":{"metadataoptions":{'
                        '"sentenceBoundaryEnabled":"true","wordBoundaryEnabled":"false"'
                        "},"
                        f'"outputFormat":"{DIORAMA_TTS_OUTPUT_FORMAT}"'
                        "}}}}\r\n"
                    )
                    await ws.send_str(
                        ec_mod.ssml_headers_plus_data(
                            ec_mod.connect_id(),
                            ec_mod.date_to_string(),
                            ec_mod.mkssml(tts_cfg, part_txt),
                        )
                    )
                    async for msg in ws:
                        if msg.type == aiohttp.WSMsgType.TEXT:
                            enc = msg.data.encode("utf-8")
                            params, body = ec_mod.get_headers_and_data(enc, enc.find(b"\r\n\r\n"))
                            p_hdr = params.get(b"Path")
                            if p_hdr == b"audio.metadata":
                                for m_obj in json.loads(body).get("Metadata", []):
                                    m_type = m_obj.get("Type")
                                    if m_type in ("SentenceBoundary", "WordBoundary"):
                                        bounds.append(
                                            {
                                                "type": m_type,
                                                "offset": int(m_obj["Data"]["Offset"]) + offset_comp,
                                                "duration": int(m_obj["Data"]["Duration"]),
                                                "text": unescape(m_obj["Data"]["text"]["Text"]),
                                            }
                                        )
                            elif p_hdr == b"turn.end":
                                cum_bytes += chunk_bytes
                                offset_comp = (cum_bytes * 8 * ec_mod.TICKS_PER_SECOND) // int(DIORAMA_TTS_BITRATE_BPS)
                                break
                        elif msg.type == aiohttp.WSMsgType.BINARY:
                            if len(msg.data) < 2:
                                continue
                            h_len = int.from_bytes(msg.data[:2], "big")
                            if h_len > len(msg.data):
                                continue
                            params, data_b = ec_mod.get_headers_and_data(msg.data, h_len)
                            if params.get(b"Path") != b"audio":
                                continue
                            c_type = params.get(b"Content-Type")
                            if c_type is None and len(data_b) == 0:
                                continue
                            if len(data_b) > 0:
                                got_audio = True
                                chunk_bytes += len(data_b)
                                audio_buf.extend(data_b)
                        elif msg.type == aiohttp.WSMsgType.ERROR:
                            raise RuntimeError(f"ReadAloud WebSocket error: {msg.data}")
                if not got_audio:
                    raise RuntimeError(f"No audio received for {DIORAMA_TTS_OUTPUT_FORMAT}")
        if not audio_buf:
            raise RuntimeError("empty high-bitrate edge-tts stream")
        return bytes(audio_buf), bounds

    async def _fetch_edge(text: str, sem: Any | None = None, use_rate: str | None = None) -> tuple[bytes, list[dict[str, Any]]]:
        import asyncio
        import socket
        import aiohttp  # type: ignore

        is_real_edge_pkg = getattr(edge_tts, "__file__", None) is not None

        async def _single_attempt(try_rate: str, try_pitch: str, try_vol: str) -> tuple[bytes, list[dict[str, Any]]]:
            conn = aiohttp.TCPConnector(family=socket.AF_INET)
            try:
                if is_real_edge_pkg and DIORAMA_TTS_OUTPUT_FORMAT != "audio-24khz-48kbitrate-mono-mp3":
                    try:
                        return await _stream_edge_high_bitrate(
                            text, voice, try_rate, try_pitch, try_vol, conn=conn, connect_timeout=8, receive_timeout=35
                        )
                    except Exception:  # noqa: BLE001
                        pass
                comm = edge_tts.Communicate(
                    text,
                    voice=voice,
                    rate=try_rate,
                    pitch=try_pitch,
                    volume=try_vol,
                    boundary="SentenceBoundary",
                    connector=conn,
                    connect_timeout=8,
                    receive_timeout=35,
                )
                audio_buf = bytearray()
                bounds: list[dict[str, Any]] = []
                async for ch in comm.stream():
                    if ch["type"] == "audio":
                        audio_buf.extend(ch["data"])
                    elif ch["type"] == "SentenceBoundary":
                        bounds.append(ch)
                if audio_buf:
                    return bytes(audio_buf), bounds
                raise RuntimeError("empty edge-tts stream")
            finally:
                if not conn.closed:
                    await conn.close()

        req_rate = str(use_rate or rate)
        last_err: Exception | None = None
        for attempt in range(4):
            try:
                if sem is not None:
                    async with sem:
                        return await asyncio.wait_for(_single_attempt(req_rate, pitch, volume), timeout=55.0)
                return await asyncio.wait_for(_single_attempt(req_rate, pitch, volume), timeout=55.0)
            except Exception as exc:  # noqa: BLE001
                last_err = exc
            if attempt < 3:
                await asyncio.sleep(0.8 * (attempt + 1))
        raise RuntimeError(f"edge-tts failed after 4 attempts: {last_err}")

    from pipeline.media_cache import get_speed_cache_dir

    local_tts_dir = get_speed_cache_dir() / "tts_npz"
    local_tts_dir.mkdir(parents=True, exist_ok=True)

    per_sent_rates = [str(r or rate) for r in (sentence_rates or [])]
    if len(per_sent_rates) != len(clean_sents):
        per_sent_rates = [str(rate)] * len(clean_sents)
    rates_by_act: list[list[str]] = []
    _pos = 0
    for act_sents in act_groups:
        rates_by_act.append(per_sent_rates[_pos : _pos + len(act_sents)])
        _pos += len(act_sents)

    act_specs: list[dict[str, Any]] = []
    slices_by_act: dict[tuple[int, str], list[np.ndarray]] = {}
    missing_specs: list[dict[str, Any]] = []

    for a_idx, act_sents in enumerate(act_groups, start=1):
        norm_sents = [_prep_for_act_stream(s) for s in act_sents]
        sub_counts = [max(1, len([x for x in re.split(r"(?<=[.!?])\s+", ns.strip()) if x.strip()])) for ns in norm_sents]
        for act_rate in sorted(set(rates_by_act[a_idx - 1])):
            key = hashlib.sha256(
                f"edge_act_v7_studio96k|{DIORAMA_TTS_OUTPUT_FORMAT}|{STORYTELLER_VOCAL_FILTER}|{voice}|{act_rate}|{pitch}|{volume}|{sr}|{'||'.join(norm_sents)}".encode()
            ).hexdigest()[:16]
            local_npz = local_tts_dir / f"edge_act_{a_idx}_{key}.npz"
            fuse_npz = cache_dir / f"edge_act_{a_idx}_{key}.npz"
            hit_npz = local_npz if local_npz.exists() else (fuse_npz if fuse_npz.exists() else None)
            if hit_npz is not None:
                try:
                    with np.load(hit_npz) as data:
                        slices_by_act[(a_idx, act_rate)] = [
                            np.asarray(data[f"s_{i}"], dtype=np.float32) for i in range(len(act_sents))
                        ]
                    continue
                except Exception:  # noqa: BLE001
                    pass
            spec_item = {
                "a_idx": a_idx,
                "rate": act_rate,
                "act_sents": act_sents,
                "norm_sents": norm_sents,
                "sub_counts": sub_counts,
                "local_npz": local_npz,
            }
            act_specs.append(spec_item)
            missing_specs.append(spec_item)

    if missing_specs:
        async def _fetch_all_missing() -> list[Any]:
            sem = asyncio.Semaphore(1)
            return list(
                await asyncio.gather(
                    *(_fetch_edge(" ".join(sp["norm_sents"]), sem=sem, use_rate=sp["rate"]) for sp in missing_specs),
                    return_exceptions=True,
                )
            )

        fetched_acts = _run_coro_sync(_fetch_all_missing())
        for sp, fetched in zip(missing_specs, fetched_acts):
            if isinstance(fetched, BaseException):
                try:  # one extra sequential retry round before degrading (edge-tts throttles long parallel batches)
                    fetched = _run_coro_sync(_fetch_edge(" ".join(sp["norm_sents"]), use_rate=sp["rate"]))
                except Exception as retry_exc:  # noqa: BLE001
                    if sp["rate"] == str(rate):
                        raise retry_exc from fetched
                    continue  # non-base gear stream failed -> base-rate slices + WSOLA fallback below
            mp3_bytes, bounds = fetched
            a_idx = sp["a_idx"]
            act_rate = sp["rate"]
            act_sents = sp["act_sents"]
            norm_sents = sp["norm_sents"]
            sub_counts = sp["sub_counts"]
            expected_bounds = sum(sub_counts)
            if mp3_bytes and len(bounds) == expected_bounds:
                act_pcm = _decode_mp3_storyteller_pcm(mp3_bytes, sr)
                n_total = len(act_pcm)
                env = np.abs(act_pcm) > 0.008
                first_samp = max(0, int(np.argmax(env)) - int(0.035 * sr)) if env.any() else 0
                last_samp = min(n_total, n_total - int(np.argmax(env[::-1])) + int(0.10 * sr)) if env.any() else n_total
                cuts = [first_samp]
                win_n = max(64, int(0.012 * sr))
                b_indices = [sum(sub_counts[:i]) for i in range(1, len(act_sents))]
                for b_idx in b_indices:
                    b = bounds[b_idx]
                    raw_cut = int(round(float(b["offset"]) * 1e-7 * sr))
                    lo_c = max(cuts[-1] + int(0.14 * sr), raw_cut - int(0.16 * sr))
                    hi_c = min(last_samp - int(0.14 * sr), raw_cut + int(0.03 * sr))
                    if hi_c > lo_c + win_n:
                        step = max(32, win_n // 3)
                        best_c = raw_cut
                        best_e = float("inf")
                        for cand in range(lo_c, hi_c - win_n + 1, step):
                            seg_e = float(np.mean(np.square(act_pcm[cand : cand + win_n])))
                            if seg_e < best_e:
                                best_e = seg_e
                                best_c = cand + win_n // 2
                        zc_lo = max(lo_c, best_c - 96)
                        zc_hi = min(hi_c, best_c + 96)
                        zc_seg = act_pcm[zc_lo:zc_hi]
                        if len(zc_seg) > 2:
                            best_c = zc_lo + int(np.argmin(np.abs(zc_seg)))
                        cuts.append(best_c)
                    else:
                        cuts.append(max(cuts[-1] + int(0.12 * sr), min(last_samp - int(0.12 * sr), raw_cut)))
                cuts.append(max(cuts[-1] + int(0.12 * sr), last_samp))
                slices = [act_pcm[cuts[i] : cuts[i + 1]].copy() for i in range(len(act_sents))]
            else:
                async def _fetch_fallback_lines(
                    _ns: list[str] = norm_sents, _r: str = act_rate
                ) -> list[tuple[bytes, list[dict[str, Any]]]]:
                    sem = asyncio.Semaphore(1)
                    return list(await asyncio.gather(*(_fetch_edge(ns, sem=sem, use_rate=_r) for ns in _ns)))

                line_results = _run_coro_sync(_fetch_fallback_lines())
                slices = []
                for b_mp3, _ in line_results:
                    p_line = _decode_mp3_storyteller_pcm(b_mp3, sr)
                    env = np.abs(p_line) > 0.008
                    if env.any():
                        s0 = max(0, int(np.argmax(env)) - int(0.035 * sr))
                        s1 = min(len(p_line), len(p_line) - int(np.argmax(env[::-1])) + int(0.18 * sr))
                        p_line = p_line[s0:s1]
                    slices.append(p_line)

            try:
                np.savez_compressed(sp["local_npz"], **{f"s_{i}": sl for i, sl in enumerate(slices)})
            except OSError:
                pass
            slices_by_act[(a_idx, act_rate)] = slices

    out_pcms: list[np.ndarray] = []
    used_rates: list[str] = []
    for a_idx in range(1, len(act_groups) + 1):
        for s_i, want_rate in enumerate(rates_by_act[a_idx - 1]):
            got = want_rate if (a_idx, want_rate) in slices_by_act else str(rate)
            if (a_idx, got) not in slices_by_act:
                # base stream was never requested for this Act (all sentences at other gears): fetch it now
                base_only = _synthesize_edge_tts_acts(
                    act_groups[a_idx - 1], None, sr, cache_dir, voice, str(rate), pitch, volume
                )
                slices_by_act[(a_idx, got)] = base_only
            out_pcms.append(slices_by_act[(a_idx, got)][s_i])
            used_rates.append(got)
    if rates_used_out is not None:
        rates_used_out.clear()
        rates_used_out.extend(used_rates)
    return out_pcms


def _trim_waveform_silences_and_breaths(
    pcm: np.ndarray,
    sr: int,
    word_list: list[tuple[float, float, str]] | None = None,
    internal_silence_thresh_sec: float = 0.16,
    internal_keep_sec: float = 0.06,
) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """
    R63 DAW-style waveform silence & breath trimmer:
      - Trims leading & trailing edge-tts dead-air tails down to gentle natural consonant/release pads (30ms lead, 50ms tail).
      - Compresses excessive internal silent gaps longer than `internal_silence_thresh_sec` down to `internal_keep_sec`
        with smooth 12ms overlap-add cosine crossfades while preserving natural conversational breaths (`>= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN`).
      - Shifts aligned word timestamps `(t0, t1, w)` monotonically to match the trimmed waveform.
    """
    arr = np.asarray(pcm, dtype=np.float32)
    if len(arr) < int(0.12 * sr):
        return arr, list(word_list or [])

    win = max(64, int(0.010 * sr))  # 10ms RMS windows
    n_wins = len(arr) // win
    if n_wins < 6:
        return arr, list(word_list or [])

    framed = arr[: n_wins * win].reshape(n_wins, win)
    rms = np.sqrt(np.mean(np.square(framed), axis=1) + 1e-10)
    db = 20.0 * np.log10(rms)
    p95 = float(np.percentile(db, 95))
    thresh_db = max(-43.0, p95 - 27.5)
    voiced = db >= thresh_db
    if not np.any(voiced):
        return arr, list(word_list or [])

    v_idx = np.where(voiced)[0]
    lead_pad_w = 3   # 30ms gentle pre-onset consonant pad
    tail_pad_w = 5   # 50ms natural post-release consonant/breath taper pad
    w_start = max(0, int(v_idx[0]) - lead_pad_w)
    w_end = min(n_wins, int(v_idx[-1]) + 1 + tail_pad_w)

    min_silent_w = max(4, int(round(internal_silence_thresh_sec / 0.010)))
    keep_silent_w = max(2, int(round(internal_keep_sec / 0.010)))
    xfade = max(8, int(0.012 * sr))

    # Collect kept sample intervals [s0, s1) from the original waveform
    kept_intervals: list[tuple[int, int]] = []
    cur_s = w_start * win
    w_i = w_start
    while w_i < w_end:
        if not voiced[w_i]:
            run_s = w_i
            while w_i < w_end and not voiced[w_i]:
                w_i += 1
            run_len = w_i - run_s
            if run_len >= min_silent_w and run_s > w_start and w_i < w_end:
                left_keep = keep_silent_w // 2
                right_keep = keep_silent_w - left_keep
                cut_a = (run_s + left_keep) * win
                cut_b = (w_i - right_keep) * win
                if cut_b - cut_a > xfade:
                    pad_l = xfade // 2
                    pad_r = xfade - pad_l
                    cut_a += pad_l
                    cut_b -= pad_r
                if cut_b > cut_a:
                    kept_intervals.append((cur_s, cut_a))
                    cur_s = cut_b
        else:
            w_i += 1
    final_samp = min(len(arr), w_end * win)
    if final_samp > cur_s:
        kept_intervals.append((cur_s, final_samp))
    if not kept_intervals:
        return arr, list(word_list or [])

    # Join intervals with 12ms overlap-add cosine crossfades across internal splices (zero room-tone dip)
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, xfade, dtype=np.float32)))
    seg_meta: list[tuple[int, int, int, bool]] = []  # (orig_a0, orig_a1, out_s0, overlapped_prev)
    out_buf: np.ndarray | None = None
    for idx_k, (a0, a1) in enumerate(kept_intervals):
        seg = arr[a0:a1].copy()
        if idx_k == 0 and len(seg) > 2 * xfade:
            seg[:xfade] *= ramp
        if idx_k == len(kept_intervals) - 1 and len(seg) > 2 * xfade:
            seg[-xfade:] *= ramp[::-1]
        if out_buf is None:
            seg_meta.append((a0, a1, 0, False))
            out_buf = seg
        elif len(out_buf) > 2 * xfade and len(seg) > 2 * xfade:
            ov_start = len(out_buf) - xfade
            seg_meta.append((a0, a1, ov_start, True))
            blended = out_buf[-xfade:] * ramp[::-1] + seg[:xfade] * ramp
            out_buf = np.concatenate([out_buf[:-xfade], blended, seg[xfade:]])
        else:
            seg_meta.append((a0, a1, len(out_buf), False))
            out_buf = np.concatenate([out_buf, seg])

    out_pcm = (out_buf if out_buf is not None else arr).astype(np.float32)
    out_dur = len(out_pcm) / float(sr)

    # Strictly monotonic piecewise-linear knot map from original sample time -> trimmed sample time
    orig_knots: list[float] = [0.0]
    new_knots: list[float] = [0.0]
    for k_i, (a0, a1, ns0_samp, ov_prev) in enumerate(seg_meta):
        ov_next = (k_i + 1 < len(seg_meta)) and seg_meta[k_i + 1][3]
        core_a0 = a0 + (xfade if ov_prev else 0)
        core_ns0 = ns0_samp + (xfade if ov_prev else 0)
        core_a1 = a1 - (xfade if ov_next else 0)
        core_ns1 = ns0_samp + (a1 - a0) - (xfade if ov_next else 0)
        os0_t = max(orig_knots[-1], core_a0 / float(sr))
        ns0_t = max(new_knots[-1], min(out_dur, core_ns0 / float(sr)))
        orig_knots.append(os0_t)
        new_knots.append(ns0_t)
        os1_t = max(orig_knots[-1], core_a1 / float(sr))
        ns1_t = max(new_knots[-1], min(out_dur, core_ns1 / float(sr)))
        orig_knots.append(os1_t)
        new_knots.append(ns1_t)
    full_in_dur = len(arr) / float(sr)
    if full_in_dur > orig_knots[-1]:
        orig_knots.append(full_in_dur)
        new_knots.append(out_dur)

    def _map_t(t_val: float) -> float:
        return float(np.interp(float(t_val), orig_knots, new_knots))

    new_words: list[tuple[float, float, str]] = []
    prev_nt1 = 0.0
    for t0, t1, w in (word_list or []):
        max_nt0 = max(0.0, out_dur - 0.02)
        nt0 = round(min(max_nt0, max(prev_nt1, _map_t(float(t0)))), 3)
        nt1 = round(min(out_dur, max(nt0 + (0.04 if out_dur >= nt0 + 0.04 else 0.01), _map_t(float(t1)))), 3)
        new_words.append((nt0, nt1, w))
        prev_nt1 = nt1
    return out_pcm, new_words


def _compute_true_rms_voiced_ratio(
    pcm: np.ndarray,
    sr: int,
    lead_sec: float = 0.0,
    speech_end_sec: float | None = None,
) -> float:
    """Computes genuine acoustic RMS voiced fraction across [lead_sec, speech_end_sec] (25ms windows > -41 dBFS)."""
    s0 = max(0, int(round(lead_sec * sr)))
    s1 = len(pcm) if speech_end_sec is None else min(len(pcm), int(round(speech_end_sec * sr)))
    seg = pcm[s0:s1]
    win = max(64, int(0.025 * sr))
    n_w = len(seg) // win
    if n_w < 2:
        return 1.0
    framed = seg[: n_w * win].reshape(n_w, win)
    rms_db = 20.0 * np.log10(np.sqrt(np.mean(np.square(framed), axis=1) + 1e-10))
    p95 = float(np.percentile(rms_db, 95))
    thresh = max(-42.0, p95 - 27.0)
    return round(float(np.mean(rms_db >= thresh)), 4)


def synthesize_continuous_diorama_track(
    project_dir: Path,
    sentences: list[str],
    sr: int = 48000,
    voice: str | None = None,
    speed: float | None = None,
    align_whisper: bool = True,
    pre_synthesized_lines: list[np.ndarray] | None = None,
    script_doc: dict[str, Any] | None = None,
    engine: str | None = None,
    pitch: str | None = None,
    rate: str | None = None,
    prosody_mode: str | None = None,
) -> dict[str, Any]:
    """
    R58, R59 & R63 Audio-First Master Clock for Schema v6/v7 `neuro_diorama`:
      - Schema v7 (`lowpoly_pastel_v7`): Runs `en-US-AndrewMultilingualNeural` at unified `1.08x` `DIORAMA_V7_TTS_RATE` (`+8%`),
        `DIORAMA_V7_TTS_PITCH` (`+14Hz`), and `DIORAMA_V7_TTS_VOLUME` (`-10%`) with tear-free Silk Clean EQ,
        applies gentle DAW-style waveform silence/breath trimming (`>= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN` true RMS voiced ratio),
        snaps to native `24.0fps`, and emits contiguous `0-frame` subtitle phrase boundaries.
      - Schema v6: Preserves legacy `+32%` / `30.0fps` behavior 100%.
    """
    from pipeline.config import (
        DIORAMA_ACT_BOUNDARY_PAUSE_SEC,
        DIORAMA_ATEMPO_FIT_RANGE,
        DIORAMA_DURATION_MAX_SEC,
        DIORAMA_DURATION_MIN_SEC,
        DIORAMA_DURATION_TARGET_SEC,
        DIORAMA_OUTRO_SWELL_SEC,
        DIORAMA_PAUSE_TUNE_RANGE_SEC,
        DIORAMA_SPEECH_PAUSE_SEC,
        DIORAMA_SUBTITLE_MAX_WORDS,
        DIORAMA_TTS_ENGINE,
        DIORAMA_TTS_PITCH,
        DIORAMA_TTS_RATE,
        DIORAMA_TTS_SPEED,
        DIORAMA_TTS_VOICE,
        DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC,
        DIORAMA_V7_DURATION_MIN_SEC,
        DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC,
        DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
        DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC,
        DIORAMA_V7_TTS_PITCH,
        DIORAMA_V7_TTS_RATE,
        DIORAMA_V7_TTS_SPEED,
        DIORAMA_V7_TTS_VOLUME,
        DIORAMA_V7_VIDEO_FPS,
        SHORTS_HARD_CEILING_SEC,
        VIDEO_FPS,
        is_diorama_v7_plan,
    )

    clean_sents = [str(s).strip() for s in sentences if str(s).strip()]
    if not clean_sents:
        raise ValueError("synthesize_continuous_diorama_track requires non-empty sentences")

    vp_probe: dict[str, Any] = {}
    vp_candidate = Path(project_dir) / "03_visuals" / "visual_plan.json"
    if vp_candidate.exists():
        try:
            vp_probe = json.loads(vp_candidate.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            vp_probe = {}
    v7_mode = is_diorama_v7_plan(script_doc or {}) or is_diorama_v7_plan(vp_probe)
    target_fps = int(DIORAMA_V7_VIDEO_FPS if v7_mode else VIDEO_FPS)

    from pipeline.prosody import (
        apply_emphasis,
        base_rate_for_mode,
        emphasis_words_for,
        measure_edge_silences,
        measure_internal_max_silence,
        fade_edges,
        plan_sentence_prosody,
        rate_to_speed,
        resolve_prosody_mode,
    )

    eff_prosody_mode = resolve_prosody_mode(prosody_mode, script_doc, v7_mode)
    prosody_active = eff_prosody_mode != "uniform_108x"
    if prosody_active and rate is None:
        rate = base_rate_for_mode(eff_prosody_mode)
    pros_plan = plan_sentence_prosody(
        [str(s).strip() for s in sentences if str(s).strip()], script_doc, eff_prosody_mode
    ) if prosody_active else []
    native_gear_synth = eff_prosody_mode == "dynamic_rush_v7"
    synth_rates_used: list[str] = []

    chosen_engine = str(engine or ("kokoro-onnx" if pre_synthesized_lines is not None else DIORAMA_TTS_ENGINE)).strip().lower()
    cache = Path(project_dir) / "04_audio" / ("tts_diorama_v7" if v7_mode else "tts_diorama")
    lead_sec = 0.08 if v7_mode else 0.10
    if prosody_active:
        lead_sec = 0.05  # P1: first audible onset <= 0.10s including the 30ms consonant pad
    min_dur_sec = float(DIORAMA_V7_DURATION_MIN_SEC if v7_mode else DIORAMA_DURATION_MIN_SEC)
    safe_max_total = min(DIORAMA_DURATION_MAX_SEC, SHORTS_HARD_CEILING_SEC - 0.10)

    # Identify 1-based sentence indices that conclude Acts 1..5 so Act transitions breathe naturally
    act_boundary_sents: set[int] = set()
    if isinstance(script_doc, dict) and isinstance(script_doc.get("acts"), list):
        running = 0
        acts_list = script_doc["acts"]
        for a_i, act_item in enumerate(acts_list):
            if not isinstance(act_item, dict):
                continue
            cnt = sum(1 for x in (act_item.get("sentences") or []) if str(x).strip())
            running += cnt
            if cnt > 0 and a_i < len(acts_list) - 1 and 1 <= running < len(clean_sents):
                act_boundary_sents.add(running)

    default_tts_speed = float(DIORAMA_V7_TTS_SPEED if v7_mode else DIORAMA_TTS_SPEED)
    used_act_continuous_edge = False
    use_rate: str | None = None
    use_pitch: str | None = None
    use_volume: str | None = None
    if chosen_engine in ("edge_tts", "edge-tts") and pre_synthesized_lines is None:
        use_voice = str(voice or DIORAMA_TTS_VOICE)
        doc_rate = str((script_doc or {}).get("tts_rate") or "").strip()
        if v7_mode and doc_rate in ("+5%", "+0%"):
            doc_rate = ""
        doc_pitch = str((script_doc or {}).get("tts_pitch") or "").strip()
        if v7_mode and doc_pitch == "+0Hz":
            doc_pitch = ""
        use_rate = str(rate or doc_rate or (DIORAMA_V7_TTS_RATE if v7_mode else DIORAMA_TTS_RATE))
        use_pitch = str(pitch or doc_pitch or (DIORAMA_V7_TTS_PITCH if v7_mode else DIORAMA_TTS_PITCH))
        use_volume = str(DIORAMA_V7_TTS_VOLUME if v7_mode else "+0%")
        if speed is not None:
            use_speed = float(speed)
        elif v7_mode and re.fullmatch(r"[+-]?\d+(?:\.\d+)?%", use_rate.strip()):
            use_speed = round(1.0 + float(use_rate.strip().rstrip("%")) / 100.0, 4)
        else:
            use_speed = default_tts_speed
        try:
            raw_pcms = _synthesize_edge_tts_acts(
                clean_sents=clean_sents,
                script_doc=script_doc,
                sr=sr,
                cache_dir=cache,
                voice=use_voice,
                rate=use_rate,
                pitch=use_pitch,
                volume=use_volume,
                sentence_rates=[str(pl["synth_rate"]) for pl in pros_plan] if native_gear_synth else None,
                rates_used_out=synth_rates_used,
            )
            used_act_continuous_edge = True
            chosen_engine = "edge_tts"
        except Exception:  # noqa: BLE001
            chosen_engine = "kokoro-onnx"
            use_rate = None
            use_pitch = None
            use_volume = None

    if not used_act_continuous_edge:
        use_voice = _resolve_kokoro_voice(voice)
        use_speed = float(speed if speed is not None else default_tts_speed)
        raw_pcms = []
        for idx, sent in enumerate(clean_sents, start=1):
            if pre_synthesized_lines is not None and idx - 1 < len(pre_synthesized_lines):
                pcm_i = np.asarray(pre_synthesized_lines[idx - 1], dtype=np.float32)
            else:
                pcm_i = synthesize_line(
                    sent,
                    sr=sr,
                    cache_dir=cache,
                    clip_no=idx,
                    voice=use_voice,
                    speed=use_speed,
                    vocal_profile="storyteller",
                )
            raw_pcms.append(pcm_i)

    from pipeline.media_cache import get_speed_cache_dir

    local_word_cache_dir = get_speed_cache_dir() / "tts_words"
    local_word_cache_dir.mkdir(parents=True, exist_ok=True)
    proj_hash = hashlib.sha1(str(Path(project_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    local_word_cache_path = local_word_cache_dir / f"whisper_word_cache_{proj_hash}.json"
    fuse_word_cache_path = cache / "whisper_word_cache.json"
    word_cache: dict[str, list[list[Any]]] = {}
    if align_whisper and pre_synthesized_lines is None:
        for wc_cand in (local_word_cache_path, fuse_word_cache_path):
            if wc_cand.exists():
                try:
                    loaded_wc = json.loads(wc_cand.read_text(encoding="utf-8"))
                    if isinstance(loaded_wc, dict):
                        for k_wc, v_wc in loaded_wc.items():
                            if isinstance(v_wc, list) and v_wc:
                                word_cache[k_wc] = v_wc
                except Exception:  # noqa: BLE001
                    pass
    word_cache_dirty = False

    # Batch uncached sentences into <=25.5s 16kHz windows so Whisper runs ~7 mel windows instead of 62!
    pre_asr_by_idx: dict[int, list[tuple[float, float, str]]] = {}
    sent_w_keys: list[str] = []
    if align_whisper and pre_synthesized_lines is None:
        uncached_items: list[tuple[int, np.ndarray]] = []
        for s_idx, (sent, pcm_i) in enumerate(zip(clean_sents, raw_pcms)):
            w_key = hashlib.sha256(pcm_i.astype(np.float32).tobytes() + b"|v2|" + to_display_text(sent).encode("utf-8")).hexdigest()[:20]
            sent_w_keys.append(w_key)
            if not word_cache.get(w_key):
                uncached_items.append((s_idx, _resample(pcm_i, sr, 16000)))
        if uncached_items:
            gap_n = int(0.65 * 16000)
            gap_zeros = np.zeros(gap_n, dtype=np.float32)
            batch_items: list[tuple[int, int, int, np.ndarray]] = []
            batch_bufs: list[np.ndarray] = []
            cur_samp = 0
            max_batch_samp = int(25.5 * 16000)

            def _flush_whisper_batch(items_b: list[tuple[int, int, int, np.ndarray]], bufs_b: list[np.ndarray]) -> None:
                if not items_b:
                    return
                try:
                    merged_16k = np.concatenate(bufs_b)
                    segs_b, _ = _whisper_model().transcribe(merged_16k, word_timestamps=True, language="en")
                    all_w = [
                        (float(w.start), float(w.end), str(w.word).strip())
                        for sg in segs_b
                        for w in (sg.words or [])
                        if str(w.word).strip()
                    ]
                    for orig_i, a_samp, b_samp, _p16 in items_b:
                        t_a = a_samp / 16000.0
                        t_b = b_samp / 16000.0
                        dur_s = max(0.05, t_b - t_a)
                        mapped = [
                            (max(0.0, w0 - t_a), min(dur_s, max(0.02, w1 - t_a)), wt)
                            for w0, w1, wt in all_w
                            if (t_a - 0.06) <= (0.5 * (w0 + w1)) <= (t_b + 0.06)
                        ]
                        pre_asr_by_idx[orig_i] = mapped
                except Exception:  # noqa: BLE001
                    return

            for orig_i, p16 in uncached_items:
                add_len = len(p16) + (gap_n if batch_bufs else 0)
                if batch_bufs and (cur_samp + add_len) > max_batch_samp:
                    _flush_whisper_batch(batch_items, batch_bufs)
                    batch_items = []
                    batch_bufs = []
                    cur_samp = 0
                if batch_bufs:
                    batch_bufs.append(gap_zeros)
                    cur_samp += gap_n
                s_a = cur_samp
                batch_bufs.append(p16)
                cur_samp += len(p16)
                batch_items.append((orig_i, s_a, cur_samp, p16))
            _flush_whisper_batch(batch_items, batch_bufs)

    raw_word_lists: list[list[tuple[float, float, str]]] = []
    trimmed_pcms: list[np.ndarray] = []
    pros_pre_tempo_dur: list[float] = []
    pros_emph_hits: list[int] = []
    pros_applied_wsola: list[float] = []
    for s_idx, (sent, pcm_i) in enumerate(zip(clean_sents, raw_pcms)):
        dur_i = len(pcm_i) / float(sr)
        if align_whisper and pre_synthesized_lines is None:
            w_key = sent_w_keys[s_idx]
            cached_entry = word_cache.get(w_key)
            if cached_entry:
                w_list_i = [(float(x[0]), float(x[1]), str(x[2])) for x in cached_entry]
            else:
                w_list_i, used_real_asr = _word_times_aligned(pcm_i, sr, sent, pre_asr_raw=pre_asr_by_idx.get(s_idx))
                if used_real_asr and w_list_i:
                    word_cache[w_key] = [[t0, t1, w] for t0, t1, w in w_list_i]
                    word_cache_dirty = True
        else:
            w_list_i = _syllable_word_times(dur_i, sent)
        if v7_mode:
            trim_t = pros_plan[s_idx]["trim_thresh_sec"] if prosody_active else DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC
            trim_k = pros_plan[s_idx]["trim_keep_sec"] if prosody_active else DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC
            pcm_i, w_list_i = _trim_waveform_silences_and_breaths(
                pcm_i,
                sr=sr,
                word_list=w_list_i,
                internal_silence_thresh_sec=trim_t,
                internal_keep_sec=trim_k,
            )
        if prosody_active:
            pcm_i, w_list_i, n_hits = apply_emphasis(pcm_i, sr, w_list_i, emphasis_words_for(script_doc, s_idx + 1))
            pros_emph_hits.append(n_hits)
            pros_pre_tempo_dur.append(len(pcm_i) / float(sr))
            # Native gear synthesis -> residual factor vs the rate this slice was actually synthesized at (1.0 normally).
            # Kokoro / failed-gear fallback -> WSOLA atempo from the synthesized speed to the gear target.
            if native_gear_synth and used_act_continuous_edge and s_idx < len(synth_rates_used):
                fac = round(float(pros_plan[s_idx]["target_tempo"]) / rate_to_speed(synth_rates_used[s_idx]), 4)
                if abs(fac - 1.0) < 0.006:
                    fac = 1.0  # integer-% rate rounding residual (< 0.6%) is inaudible; never WSOLA for it
            elif native_gear_synth and not used_act_continuous_edge:
                fac = round(float(pros_plan[s_idx]["target_tempo"]) / max(0.5, float(use_speed)), 4)
            else:
                fac = float(pros_plan[s_idx]["wsola_factor"])
            pros_applied_wsola.append(fac if abs(fac - 1.0) >= 0.003 else 1.0)
            if abs(fac - 1.0) >= 0.003:
                pcm_fit = _apply_pitch_preserving_atempo(pcm_i, sr, fac)
                scale_w = (len(pcm_fit) / float(sr)) / max(1e-4, len(pcm_i) / float(sr))
                w_list_i = [(round(t0 * scale_w, 3), round(t1 * scale_w, 3), w) for t0, t1, w in w_list_i]
                pcm_i = pcm_fit
        trimmed_pcms.append(pcm_i)
        raw_word_lists.append(w_list_i)
    if word_cache_dirty:
        try:
            tmp_wc = local_word_cache_path.with_suffix(".json.tmp")
            tmp_wc.write_text(json.dumps(word_cache, ensure_ascii=False), encoding="utf-8")
            os.replace(tmp_wc, local_word_cache_path)
        except Exception:  # noqa: BLE001
            pass
    raw_pcms = trimmed_pcms

    n_sents = len(raw_pcms)
    raw_speech_sum = sum(len(p) / float(sr) for p in raw_pcms)
    n_gaps = max(0, n_sents - 1)
    n_act_gaps = len(act_boundary_sents)
    n_reg_gaps = max(0, n_gaps - n_act_gaps)

    if v7_mode:
        pause_lo, pause_hi = (0.07, 0.24)
        pause_sec = DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC
        act_extra_sec = max(0.0, DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC - DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC)
    elif used_act_continuous_edge:
        # Act-continuous edge-tts slices ALREADY include natural human breath inside each sentence slice!
        pause_lo, pause_hi = (0.00, 0.28)
        pause_sec = 0.00
        act_extra_sec = DIORAMA_ACT_BOUNDARY_PAUSE_SEC
    else:
        pause_lo, pause_hi = DIORAMA_PAUSE_TUNE_RANGE_SEC
        pause_sec = DIORAMA_SPEECH_PAUSE_SEC
        act_extra_sec = max(0.0, DIORAMA_ACT_BOUNDARY_PAUSE_SEC - DIORAMA_SPEECH_PAUSE_SEC)

    pros_gaps: list[float] = [float(pros_plan[i]["gap_before_sec"]) for i in range(1, n_sents)] if prosody_active else []

    def _total_gap_sec(base_p: float) -> float:
        if prosody_active:
            return float(sum(pros_gaps))
        return n_reg_gaps * base_p + n_act_gaps * (base_p + act_extra_sec)

    # Step 1: Tune inter-sentence / Act-boundary breath gap before touching atempo
    nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + DIORAMA_OUTRO_SWELL_SEC
    if used_act_continuous_edge and (not v7_mode) and nominal_total > safe_max_total - 0.30 and n_act_gaps > 0:
        avail_act_gap = (safe_max_total - 0.50 - lead_sec - raw_speech_sum - DIORAMA_OUTRO_SWELL_SEC) / float(n_act_gaps)
        act_extra_sec = round(max(0.16, min(DIORAMA_ACT_BOUNDARY_PAUSE_SEC, avail_act_gap)), 3)
        nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + DIORAMA_OUTRO_SWELL_SEC
    if n_gaps > 0 and (nominal_total > safe_max_total - 0.30 or nominal_total < min_dur_sec):
        if v7_mode and nominal_total > safe_max_total - 0.30:
            fit_target_sec = safe_max_total - 0.45
        elif v7_mode and nominal_total < min_dur_sec:
            fit_target_sec = min_dur_sec + 1.5
        else:
            fit_target_sec = DIORAMA_DURATION_TARGET_SEC
        ideal_pause = (
            fit_target_sec - lead_sec - raw_speech_sum - n_act_gaps * act_extra_sec - DIORAMA_OUTRO_SWELL_SEC
        ) / float(n_gaps)
        pause_sec = round(max(pause_lo, min(pause_hi, ideal_pause)), 3)
        nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + DIORAMA_OUTRO_SWELL_SEC
        if v7_mode and nominal_total > safe_max_total - 0.30 and n_act_gaps > 0:
            avail_act_extra = (
                (safe_max_total - 0.45) - lead_sec - raw_speech_sum - DIORAMA_OUTRO_SWELL_SEC - n_gaps * pause_sec
            ) / float(n_act_gaps)
            act_extra_sec = round(max(0.04, min(act_extra_sec, avail_act_extra)), 3)
            nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + DIORAMA_OUTRO_SWELL_SEC

    # Step 2: If still outside [min_dur_sec, safe_max_total - 0.30], apply bounded pitch-preserving atempo (<= 1.15x)
    atempo_factor = 1.0
    atempo_lo, atempo_hi = DIORAMA_ATEMPO_FIT_RANGE
    atempo_cap = min(1.15, max(float(atempo_hi), 1.15))
    if nominal_total > safe_max_total - 0.30:
        req_speech = max(10.0, (safe_max_total - 0.60) - lead_sec - _total_gap_sec(pause_sec) - DIORAMA_OUTRO_SWELL_SEC)
        atempo_factor = min(atempo_cap, max(1.003, raw_speech_sum / req_speech))
    elif nominal_total < min_dur_sec + 1.0:
        req_speech = (min_dur_sec + 1.5) - lead_sec - _total_gap_sec(pause_sec) - DIORAMA_OUTRO_SWELL_SEC
        if req_speech > 0:
            atempo_factor = max(atempo_lo, min(1.0, raw_speech_sum / req_speech))

    if abs(atempo_factor - 1.0) >= 0.003:
        fitted_pcms: list[np.ndarray] = []
        fitted_words: list[list[tuple[float, float, str]]] = []
        for pcm_i, w_list in zip(raw_pcms, raw_word_lists):
            pcm_fit = _apply_pitch_preserving_atempo(pcm_i, sr, atempo_factor)
            scale = (len(pcm_fit) / float(sr)) / max(1e-4, len(pcm_i) / float(sr))
            fitted_pcms.append(pcm_fit)
            fitted_words.append([(round(t0 * scale, 3), round(t1 * scale, 3), w) for t0, t1, w in w_list])
        raw_pcms = fitted_pcms
        raw_word_lists = fitted_words

    # Step 3: Verify post-atempo speech fits within SHORTS_HARD_CEILING_SEC - outro_sec (zero silent truncation)
    outro_sec = float(DIORAMA_OUTRO_SWELL_SEC)
    hard_speech_ceiling = round(float(SHORTS_HARD_CEILING_SEC) - outro_sec, 3)
    chunks: list[np.ndarray] = [np.zeros(int(round(lead_sec * sr)), dtype=np.float32)]
    reg_pause_samples = int(round(pause_sec * sr))
    act_pause_samples = int(round((pause_sec + act_extra_sec) * sr))
    projected_gap_sec = (
        n_reg_gaps * (reg_pause_samples / float(sr))
        + n_act_gaps * (act_pause_samples / float(sr))
    )
    if prosody_active:
        projected_gap_sec = sum(int(round(g * sr)) / float(sr) for g in pros_gaps)
    projected_speech_end = lead_sec + sum(len(p) / float(sr) for p in raw_pcms) + projected_gap_sec
    if projected_speech_end > hard_speech_ceiling + 1e-3:
        raise RuntimeError(
            f"Diorama narration speech_end ({projected_speech_end:.3f}s) exceeds hard ceiling "
            f"({hard_speech_ceiling:.3f}s = {SHORTS_HARD_CEILING_SEC:.1f}s - {outro_sec:.2f}s outro) "
            f"after bounded atempo={atempo_factor:.4f}x (max 1.15x) across {n_sents} sentences; "
            "shorten narration script instead of truncating trailing sentences."
        )

    cursor = lead_sec
    sentence_spans: list[dict[str, Any]] = []
    events: list[tuple[float, float, list[str]]] = []
    prev_ev_end = 0.0

    for idx, (sent, pcm_i, w_list) in enumerate(zip(clean_sents, raw_pcms, raw_word_lists), start=1):
        s_dur = len(pcm_i) / float(sr)
        s_start = cursor
        s_end = cursor + s_dur

        # Splice hygiene: every sentence slice starts and ends at exactly zero before the zero-gap is inserted
        chunks.append(fade_edges(pcm_i, sr) if v7_mode else pcm_i)
        sentence_spans.append(
            {
                "sentence_index": idx,
                "act_boundary_after": (idx in act_boundary_sents),
                "start_sec": round(s_start, 3),
                "end_sec": round(s_end, 3),
                "duration_sec": round(s_dur, 3),
                "text": sent,
                "display_text": to_display_text(sent),
            }
        )
        phrases = _phrases(w_list, DIORAMA_SUBTITLE_MAX_WORDS)
        for p_idx, (t0, t1, disp_words) in enumerate(phrases):
            if v7_mode:
                ev_s = round(max(prev_ev_end, s_start + t0), 3)
                if p_idx + 1 < len(phrases):
                    ev_e = round(max(ev_s + 0.08, s_start + phrases[p_idx + 1][0]), 3)
                else:
                    ev_e = round(max(ev_s + 0.08, s_end), 3)
            else:
                ev_s = round(max(prev_ev_end + 0.01 if prev_ev_end > 0 else 0.0, s_start + t0), 2)
                if p_idx + 1 < len(phrases):
                    next_s = round(s_start + phrases[p_idx + 1][0], 2)
                    ev_e = round(min(s_end, s_start + t1, max(ev_s + 0.06, next_s - 0.01)), 2)
                else:
                    ev_e = round(min(s_end + 0.04, max(ev_s + 0.08, s_start + t1)), 2)
                if ev_e <= ev_s:
                    ev_e = round(ev_s + 0.06, 2)
            events.append((ev_s, ev_e, disp_words))
            prev_ev_end = ev_e

        cursor = s_end
        if idx < n_sents:
            if prosody_active:
                gap_n = int(round(pros_gaps[idx - 1] * sr))
            else:
                gap_n = act_pause_samples if idx in act_boundary_sents else reg_pause_samples
            gap_s = gap_n / float(sr)
            chunks.append(np.zeros(gap_n, dtype=np.float32))
            cursor += gap_s

    speech_end_sec = round(cursor, 3)
    raw_total_sec = min(SHORTS_HARD_CEILING_SEC, speech_end_sec + DIORAMA_OUTRO_SWELL_SEC)
    total_frames = min(int(SHORTS_HARD_CEILING_SEC * target_fps), max(60, int(round(raw_total_sec * target_fps))))
    total_duration_sec = round(total_frames / float(target_fps), 3)
    tail_samples = max(0, int(round(total_duration_sec * sr)) - sum(len(c) for c in chunks))
    if tail_samples > 0:
        chunks.append(np.zeros(tail_samples, dtype=np.float32))

    master_voice = np.concatenate(chunks)[: int(round(total_duration_sec * sr))]
    voiced_sum = sum(sp["duration_sec"] for sp in sentence_spans)
    active_ratio = round(voiced_sum / max(0.1, speech_end_sec - lead_sec), 4)
    true_rms_ratio = _compute_true_rms_voiced_ratio(master_voice, sr, lead_sec, speech_end_sec)
    if v7_mode:
        master_voice = _apply_studio_booth_glue(master_voice, sr, lead_sec, speech_end_sec)

    audio_dir = Path(project_dir) / "04_audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    voice_report = {
        "source": "tts_fallback",
        "profile": "neuro_diorama",
        "schema_version": (7 if v7_mode else 6),
        "fps": target_fps,
        "engine": chosen_engine,
        "voice": use_voice,
        "rate": use_rate,
        "pitch": use_pitch,
        "volume": use_volume,
        "speed": use_speed,
        "atempo_applied": round(atempo_factor, 4),
        "pause_sec": pause_sec,
        "sentence_count": len(sentence_spans),
        "speech_end_sec": speech_end_sec,
        "total_duration_sec": total_duration_sec,
        "active_speech_ratio": active_ratio,
        "true_rms_voiced_ratio": true_rms_ratio,
        "sentence_spans": sentence_spans,
        "events": [[t0, t1, ws] for t0, t1, ws in events],
        "native_f0": {"passed": True, "reason": "diorama_continuous_tts_master", "regenerate_clips": []},
    }
    (audio_dir / "voice_report.json").write_text(json.dumps(voice_report, indent=2, ensure_ascii=False), encoding="utf-8")
    if prosody_active:
        base_spd = round(1.0 + float(str(use_rate or "+0%").strip().rstrip("%") or 0) / 100.0, 4) if use_rate else float(use_speed)
        edges = [measure_edge_silences(p, sr) for p in raw_pcms]
        pros_rows: list[dict[str, Any]] = []
        for i, (pl, sp, pcm_i) in enumerate(zip(pros_plan, sentence_spans, raw_pcms)):
            final_dur = len(pcm_i) / float(sr)
            sent_spd = rate_to_speed(synth_rates_used[i]) if i < len(synth_rates_used) else base_spd
            measured_tempo = round(sent_spd * (pros_pre_tempo_dur[i] / max(1e-4, final_dur)) * atempo_factor, 4)
            n_w = len(str(sp["text"]).split())
            pre_sil = None
            if i > 0:
                pre_sil = round(edges[i - 1][1] + pros_gaps[i - 1] + edges[i][0], 3)
            pros_rows.append(
                {
                    **pl,
                    "synth_rate": synth_rates_used[i] if i < len(synth_rates_used) else use_rate,
                    "native_gear_synth": bool(i < len(synth_rates_used) and native_gear_synth),
                    "wsola_factor": pros_applied_wsola[i] if i < len(pros_applied_wsola) else pl["wsola_factor"],
                    "target_tempo": round(float(pl["target_tempo"]) * atempo_factor, 4),
                    "measured_tempo": measured_tempo,
                    "duration_sec": round(final_dur, 3),
                    "words": n_w,
                    "wpm": round(n_w / max(0.05, final_dur / 60.0), 1),
                    "lead_silence_sec": edges[i][0],
                    "trail_silence_sec": edges[i][1],
                    "acoustic_pre_silence_sec": pre_sil,
                    "max_internal_silence_sec": measure_internal_max_silence(pcm_i, sr),
                    "emphasis_hits": pros_emph_hits[i] if i < len(pros_emph_hits) else 0,
                }
            )
        pros_report = {
            "prosody_mode": eff_prosody_mode,
            "base_rate": use_rate,
            "native_gear_synthesis": bool(native_gear_synth and used_act_continuous_edge),
            "gear_rates": sorted(set(synth_rates_used)) if synth_rates_used else [use_rate],
            "global_atempo": round(atempo_factor, 4),
            "speech_end_sec": speech_end_sec,
            "total_duration_sec": total_duration_sec,
            "gear_counts": {g: sum(1 for r in pros_rows if r["gear"] == g) for g in ("rush", "stamp", "brisk")},
            "sentences": pros_rows,
        }
        (audio_dir / "prosody_report.json").write_text(json.dumps(pros_report, indent=2, ensure_ascii=False), encoding="utf-8")
        voice_report["prosody_mode"] = eff_prosody_mode
        (audio_dir / "voice_report.json").write_text(json.dumps(voice_report, indent=2, ensure_ascii=False), encoding="utf-8")
    return {
        "pcm": master_voice,
        "sr": sr,
        "fps": target_fps,
        "speech_end_sec": speech_end_sec,
        "total_duration_sec": total_duration_sec,
        "total_frames": total_frames,
        "active_speech_ratio": active_ratio,
        "true_rms_voiced_ratio": true_rms_ratio,
        "pause_sec": pause_sec,
        "atempo_applied": round(atempo_factor, 4),
        "sentence_spans": sentence_spans,
        "events": events,
        "report": voice_report,
    }
