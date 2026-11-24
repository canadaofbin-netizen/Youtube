"""
ALL ABOUT BRAIN - ElevenLabs `eleven_v4` Neuro-Diorama continuous storyteller TTS & deterministic test stub (R58, R59, R63, R68).

Sole production TTS engine: ElevenLabs `eleven_v4` (`synthesize_continuous_diorama_track`), fail-fast on API/quota errors
with zero silent downgrade to legacy engines. Unit tests use `pre_synthesized_lines` or `allow_test_stub=True` (`0` credits).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import subprocess
import tempfile
import threading
import wave
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.hardware_profile import resolve_whisper_threads
from pipeline.media_cache import atomic_commit_from_scratch, is_ephemeral_scratch_path, ram_tempdir
from pipeline.plain_language import count_syllables, to_display_text, to_expressive_tts_text, to_tts_text

TTS_TARGET_ACTIVE_DB = -13.5  # same active-speech level as the studio vocal chain
_WHISPER_MODEL = None
_WHISPER_MODEL_THREADS: int = 0
_WHISPER_LOCK = threading.Lock()


def _ffmpeg() -> str:
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def _resample(pcm: np.ndarray, sr_in: int, sr_out: int) -> np.ndarray:
    if sr_in == sr_out:
        return pcm.astype(np.float32)
    with ram_tempdir(prefix="aab_tts_") as td:
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


def _write_mono_wav(path: Path, pcm: np.ndarray, sr: int) -> None:
    dst = Path(path)
    dst.parent.mkdir(parents=True, exist_ok=True)
    pcm_i16 = (np.clip(pcm, -0.98, 0.98) * 32767.0).astype(np.int16)
    if is_ephemeral_scratch_path(dst):
        with wave.open(str(dst), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm_i16.tobytes())
        return
    with ram_tempdir(prefix="aab_wav_") as td:
        tmp_w = Path(td) / dst.name
        with wave.open(str(tmp_w), "wb") as wf:
            wf.setnchannels(1)
            wf.setsampwidth(2)
            wf.setframerate(sr)
            wf.writeframes(pcm_i16.tobytes())
        atomic_commit_from_scratch(tmp_w, dst)


def resolve_diorama_voice_preset(
    voice_preset: str | None = None,
    script_doc: dict[str, Any] | None = None,
    visual_plan: dict[str, Any] | None = None,
    voice: str | None = None,
) -> tuple[str, dict[str, str]]:
    """
    Resolves `(preset_id, preset_spec)` from `DIORAMA_VOICE_PRESETS`:
    priority = explicit `voice_preset` -> `script_doc['voice_preset']` -> `visual_plan['voice_preset']`
    -> reverse lookup by `voice` ElevenLabs voice ID -> `EXPRESSIVE_V8_VOICE_PRESET` ('elevenlabs_v4') on v8 plans
    -> `DEFAULT_DIORAMA_VOICE_PRESET` ('elevenlabs_v4').
    """
    from pipeline.config import (
        DEFAULT_DIORAMA_VOICE_PRESET,
        DIORAMA_VOICE_PRESETS,
        EXPRESSIVE_V8_VOICE_PRESET,
        is_expressive_v8_plan,
    )

    legacy_female_aliases = {"emma_v7", "ava_v7", "aria_v7"}
    for cand in (
        voice_preset,
        (script_doc or {}).get("voice_preset") if isinstance(script_doc, dict) else None,
        (visual_plan or {}).get("voice_preset") if isinstance(visual_plan, dict) else None,
    ):
        key = str(cand or "").strip().lower()
        if key in DIORAMA_VOICE_PRESETS:
            return key, dict(DIORAMA_VOICE_PRESETS[key])
        if key in legacy_female_aliases and "elevenlabs_v4_female" in DIORAMA_VOICE_PRESETS:
            return "elevenlabs_v4_female", dict(DIORAMA_VOICE_PRESETS["elevenlabs_v4_female"])
    v_norm = str(voice or "").strip().lower()
    if v_norm:
        if is_expressive_v8_plan(visual_plan, script_doc):
            v8_spec = DIORAMA_VOICE_PRESETS.get(EXPRESSIVE_V8_VOICE_PRESET)
            if v8_spec and v_norm in (
                v8_spec["voice"].lower(),
                str(v8_spec.get("elevenlabs_voice_id") or "").lower(),
            ):
                return EXPRESSIVE_V8_VOICE_PRESET, dict(v8_spec)
        for k, spec in DIORAMA_VOICE_PRESETS.items():
            if v_norm in (
                spec["voice"].lower(),
                str(spec.get("elevenlabs_voice_id") or "").lower(),
            ):
                return k, dict(spec)
    if voice_preset is None and not v_norm and is_expressive_v8_plan(visual_plan, script_doc):
        return EXPRESSIVE_V8_VOICE_PRESET, dict(DIORAMA_VOICE_PRESETS[EXPRESSIVE_V8_VOICE_PRESET])
    return DEFAULT_DIORAMA_VOICE_PRESET, dict(DIORAMA_VOICE_PRESETS[DEFAULT_DIORAMA_VOICE_PRESET])


def _master_storyteller_vocal(
    pcm: np.ndarray,
    sr_in: int,
    sr_out: int,
    vocal_filter: str | None = None,
) -> np.ndarray:
    """Applies `STORYTELLER_VOCAL_FILTER` (or female studio filter) and peak-safe RMS normalization to mono float32 PCM."""
    use_filter = vocal_filter or STORYTELLER_VOCAL_FILTER
    af = use_filter if use_filter.startswith("aresample=") else f"aresample={sr_out}:resampler=soxr,{use_filter}"
    with ram_tempdir(prefix="aab_tts_story_") as td:
        src = Path(td) / "in.f32"
        src.write_bytes(pcm.astype(np.float32).tobytes())
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


def _synthesize_test_stub_pcm(
    text: str,
    sr: int = 48000,
    target_tempo: float = 1.0,
    seed_idx: int = 1,
) -> np.ndarray:
    """
    Deterministic zero-credit voiced harmonic waveform for unit tests and offline `--precheck-only` clock checks.
    Never used in production rendering unless `allow_test_stub=True` is explicitly set.
    """
    words = to_tts_text(text).split()
    n_words = max(1, len(words))
    n_syl = max(1, sum(max(1, count_syllables(w)) for w in words))
    eff_tempo = max(0.70, float(target_tempo or 1.0))
    voiced_sec = max(0.32, (0.55 * (n_words / 3.10) + 0.45 * (n_syl / 4.45)) / eff_tempo)
    n_voiced = max(int(0.20 * sr), int(round(voiced_sec * sr)))
    t = np.arange(n_voiced, dtype=np.float32) / float(sr)
    f0 = 132.0 + (seed_idx % 5) * 2.0
    carrier = (
        0.62 * np.sin(2.0 * np.pi * f0 * t)
        + 0.26 * np.sin(2.0 * np.pi * (2.0 * f0) * t + 0.3)
        + 0.12 * np.sin(2.0 * np.pi * (3.0 * f0) * t + 0.7)
    )
    syl_env = 0.72 + 0.28 * np.sin(2.0 * np.pi * 4.2 * t)
    voiced = (0.22 * carrier * syl_env).astype(np.float32)
    fade_n = min(n_voiced // 6, max(8, int(0.015 * sr)))
    if fade_n >= 4:
        ramp = (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fade_n, dtype=np.float32))).astype(np.float32)
        voiced[:fade_n] *= ramp
        voiced[-fade_n:] *= ramp[::-1]
    lead_pad = np.zeros(int(0.045 * sr), dtype=np.float32)
    tail_pad = np.zeros(int(0.065 * sr), dtype=np.float32)
    return np.concatenate([lead_pad, voiced, tail_pad]).astype(np.float32)


def _clip_duration(path: Path) -> float:
    from pipeline.media_cache import cached_by_clip_stat

    def _probe_dur(p: Path) -> float:
        res = subprocess.run([_ffmpeg(), "-nostdin", "-hide_banner", "-i", str(p)], capture_output=True, text=True, check=False, stdin=subprocess.DEVNULL)
        m = re.search(r"Duration:\s*(\d+):(\d+):([\d.]+)", res.stderr or "")
        if not m:
            return 8.0
        return int(m.group(1)) * 3600 + int(m.group(2)) * 60 + float(m.group(3))

    return float(cached_by_clip_stat(Path(path), namespace="clip_dur_v1", compute_fn=_probe_dur, stage_on_miss=False))


def _whisper_model(cpu_threads: int | None = None):
    global _WHISPER_MODEL, _WHISPER_MODEL_THREADS
    eff_threads = resolve_whisper_threads(cpu_threads)
    with _WHISPER_LOCK:
        if _WHISPER_MODEL is None or eff_threads > _WHISPER_MODEL_THREADS:
            from faster_whisper import WhisperModel  # type: ignore

            _WHISPER_MODEL = WhisperModel(
                "base.en",
                device="cpu",
                compute_type="int8",
                cpu_threads=eff_threads,
            )
            _WHISPER_MODEL_THREADS = eff_threads
        return _WHISPER_MODEL


def _word_times_aligned(
    pcm: np.ndarray,
    sr: int,
    text: str,
    pre_asr_raw: list[tuple[float, float, str]] | None = None,
    cpu_threads: int | None = None,
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
            segs, _ = _whisper_model(cpu_threads=cpu_threads).transcribe(pcm16, word_timestamps=True, language="en")
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
    with ram_tempdir(prefix="aab_diorama_atempo_") as td:
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


def _trim_waveform_silences_and_breaths(
    pcm: np.ndarray,
    sr: int,
    word_list: list[tuple[float, float, str]] | None = None,
    internal_silence_thresh_sec: float = 0.16,
    internal_keep_sec: float = 0.06,
    lead_pad_sec: float = 0.030,
) -> tuple[np.ndarray, list[tuple[float, float, str]]]:
    """
    R63 DAW-style waveform silence & breath trimmer:
      - Trims leading & trailing edge-tts dead-air tails down to gentle natural consonant/release pads (`lead_pad_sec` lead, 50ms tail).
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
    lead_pad_w = max(0, int(round(float(lead_pad_sec) / 0.010)))  # 30ms gentle pre-onset pad (0ms on v8 S1)
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
            if lead_pad_w == 0:
                fast_n = max(8, int(0.004 * sr))
                if len(seg) > 2 * fast_n:
                    seg[:fast_n] *= (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, fast_n, dtype=np.float32)))
            else:
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
    voice_preset: str | None = None,
    allow_test_stub: bool = False,
    retry_intact_sentence_indices: set[int] | list[int] | None = None,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    R58, R59, R63 & R68 Audio-First Master Clock for `neuro_diorama`:
      - Sole production TTS engine: ElevenLabs `eleven_v4` (`elevenlabs_v4`, `el_researcher_v4`, `el_minicortex_v4`,
        `elevenlabs_v4_female`, `elevenlabs_v4_male`), failing fast immediately on API/quota errors with zero
        silent downgrade to legacy TTS engines.
      - Unit tests use `pre_synthesized_lines` or `allow_test_stub=True` (`0` ElevenLabs credits).
      - Applies DAW-style waveform silence/breath trimming, snaps to native FPS (`30fps` v8 / `24fps` v7),
        and emits exact word-aligned subtitle chunks (`<= 2` words on `v8`, `<= 3` words on `v7`).
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
        DIORAMA_V7_ACT_BOUNDARY_PAUSE_SEC,
        DIORAMA_V7_DURATION_MIN_SEC,
        DIORAMA_V7_INTERNAL_BREATH_KEEP_SEC,
        DIORAMA_V7_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
        DIORAMA_V7_INTER_SENTENCE_PAUSE_SEC,
        DIORAMA_V7_VIDEO_FPS,
        DIORAMA_VOICE_PRESETS,
        EXPRESSIVE_V8_FIRST_ONSET_TARGET_SEC,
        EXPRESSIVE_V8_FOIL_VOICE_PRESET,
        EXPRESSIVE_V8_OUTRO_TAIL_SEC,
        EXPRESSIVE_V8_SUBTITLE_MAX_WORDS,
        EXPRESSIVE_V8_VIDEO_FPS,
        MICRO_SHORT_DURATION_MAX_SEC,
        MICRO_SHORT_DURATION_MIN_SEC,
        MICRO_SHORT_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        SHORTS_HARD_CEILING_SEC,
        STORYTELLER_VOCAL_FILTER_EXPRESSIVE_V8,
        STORYTELLER_VOCAL_FILTER_FEMALE,
        VIDEO_FPS,
        is_diorama_v7_plan,
        is_expressive_v8_plan,
        resolve_shorts_format_profile,
        shorts_duration_range_for_profile,
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
    is_micro_short = (
        str((script_doc or {}).get("profile") or vp_probe.get("profile") or "").strip().lower() == MICRO_SHORT_PROFILE
    )
    is_v8 = is_expressive_v8_plan(vp_probe, script_doc or {})
    v7_mode = is_micro_short or is_v8 or is_diorama_v7_plan(script_doc or {}) or is_diorama_v7_plan(vp_probe)
    outro_tail_sec = float(EXPRESSIVE_V8_OUTRO_TAIL_SEC if is_v8 else DIORAMA_OUTRO_SWELL_SEC)
    target_fps = int(EXPRESSIVE_V8_VIDEO_FPS if is_v8 else (DIORAMA_V7_VIDEO_FPS if v7_mode else VIDEO_FPS))

    def _vocal_filter_for_spec(sp_obj: dict[str, Any]) -> str:
        eq_p = str(sp_obj.get("eq_profile") or "")
        if eq_p == "female_studio":
            return STORYTELLER_VOCAL_FILTER_FEMALE
        if eq_p == "male_expressive_v8":
            return STORYTELLER_VOCAL_FILTER_EXPRESSIVE_V8
        return STORYTELLER_VOCAL_FILTER

    # Extract 1-based cast speaker assignments (`narrator` / `researcher` / `mini_cortex` / `foil`)
    from pipeline.tts import load_cast_registry

    cast_reg = load_cast_registry()
    cast_map = dict(cast_reg.get("cast") or {})
    foil_indices: set[int] = set()
    foil_preset_by_idx: dict[int, str] = {}
    speaker_role_by_idx: dict[int, str] = {}
    speaker_voice_by_idx: dict[int, dict[str, Any]] = {}

    def _register_speaker_tag(fi: int, raw_tag: Any) -> None:
        if not (1 <= fi <= len(clean_sents)):
            return
        tag = str(raw_tag or "narrator").strip().lower()
        if not tag or tag == "narrator":
            speaker_role_by_idx[fi] = "narrator"
            return
        role_norm = "foil" if tag in ("foil", "foil_2", "guy_foil_v8", "foil_v8") else tag
        speaker_role_by_idx[fi] = role_norm
        foil_indices.add(fi)
        cast_entry = cast_map.get(role_norm) if isinstance(cast_map.get(role_norm), dict) else None
        if cast_entry:
            vp_cand = str(cast_entry.get("voice_preset") or "").strip().lower()
            if vp_cand in DIORAMA_VOICE_PRESETS:
                foil_preset_by_idx[fi] = vp_cand
            if cast_entry.get("elevenlabs_voice_id"):
                speaker_voice_by_idx[fi] = {
                    "role": role_norm,
                    "voice_id": str(cast_entry["elevenlabs_voice_id"]),
                    "fallback_voice_id": cast_entry.get("elevenlabs_fallback_voice_id"),
                    "gender": str(cast_entry.get("gender") or "female"),
                    "voice_preset": vp_cand,
                }
        elif tag in ("foil_2", "guy_foil_v8") and "guy_foil_v8" in DIORAMA_VOICE_PRESETS:
            foil_preset_by_idx[fi] = "guy_foil_v8"
        elif tag in DIORAMA_VOICE_PRESETS:
            foil_preset_by_idx[fi] = tag
            sp_p = DIORAMA_VOICE_PRESETS[tag]
            if sp_p.get("elevenlabs_voice_id"):
                speaker_voice_by_idx[fi] = {
                    "role": role_norm,
                    "voice_id": str(sp_p["elevenlabs_voice_id"]),
                    "fallback_voice_id": sp_p.get("elevenlabs_fallback_voice_id"),
                    "gender": str(sp_p.get("gender") or "female"),
                    "voice_preset": tag,
                }

    if isinstance(script_doc, dict):
        for raw_fi in script_doc.get("foil_sentence_indices") or []:
            try:
                fi = int(raw_fi)
                _register_speaker_tag(fi, "foil")
            except (TypeError, ValueError):
                pass
        sp_map = script_doc.get("sentence_speakers")
        if isinstance(sp_map, dict):
            for k_sp, v_sp in sp_map.items():
                try:
                    _register_speaker_tag(int(k_sp), v_sp)
                except (TypeError, ValueError):
                    pass
        elif isinstance(sp_map, list):
            for fi, v_sp in enumerate(sp_map, start=1):
                _register_speaker_tag(fi, v_sp)
        svp_map = script_doc.get("sentence_voice_presets")
        if isinstance(svp_map, dict):
            for k_vp, v_vp in svp_map.items():
                try:
                    fi = int(k_vp)
                    vp_id = str(v_vp).strip().lower()
                    if 1 <= fi <= len(clean_sents) and vp_id in DIORAMA_VOICE_PRESETS:
                        _register_speaker_tag(fi, vp_id)
                except (TypeError, ValueError):
                    pass
        if isinstance(script_doc.get("acts"), list):
            run_fi = 0
            for act_obj in script_doc["acts"]:
                if not isinstance(act_obj, dict):
                    continue
                act_s = [str(x).strip() for x in (act_obj.get("sentences") or []) if str(x).strip()]
                act_sp = act_obj.get("sentence_speakers")
                if isinstance(act_sp, list):
                    for off_i, v_sp in enumerate(act_sp[: len(act_s)], start=1):
                        if (run_fi + off_i) not in speaker_role_by_idx:
                            _register_speaker_tag(run_fi + off_i, v_sp)
                run_fi += len(act_s)
    foil_preset_id = str((script_doc or {}).get("foil_voice_preset") or EXPRESSIVE_V8_FOIL_VOICE_PRESET).strip().lower()
    if foil_preset_id not in DIORAMA_VOICE_PRESETS:
        foil_preset_id = EXPRESSIVE_V8_FOIL_VOICE_PRESET
    foil_spec = dict(DIORAMA_VOICE_PRESETS[foil_preset_id])
    foil_vocal_filter = _vocal_filter_for_spec(foil_spec)

    eff_preset, preset_spec = resolve_diorama_voice_preset(
        voice_preset=voice_preset,
        script_doc=script_doc,
        visual_plan=vp_probe,
        voice=voice,
    )
    eff_vocal_filter = _vocal_filter_for_spec(preset_spec)

    from pipeline.prosody_qa import (
        DYNAMIC_PROSODY_MODES,
        apply_emphasis,
        base_rate_for_mode,
        emphasis_words_for,
        fade_edges,
        measure_edge_silences,
        measure_internal_max_silence,
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
    native_gear_synth = eff_prosody_mode in DYNAMIC_PROSODY_MODES
    synth_rates_used: list[str] = []

    req_engine = str(engine or "").strip().lower()
    if req_engine in ("kokoro", "kokoro-onnx", "edge-tts", "edge_tts") and pre_synthesized_lines is None and not allow_test_stub:
        from pipeline.tts import ElevenLabsUnavailableError

        raise ElevenLabsUnavailableError(
            f"Legacy TTS engine {engine!r} is permanently removed; production audio is strictly locked to ElevenLabs eleven_v4."
        )
    chosen_engine = "test_stub" if (pre_synthesized_lines is not None or allow_test_stub) else str(DIORAMA_TTS_ENGINE).strip().lower()
    cache = Path(project_dir) / "04_audio" / ("tts_diorama_v7" if v7_mode else "tts_diorama")
    lead_sec = 0.08 if v7_mode else 0.10
    if is_v8:
        lead_sec = float(EXPRESSIVE_V8_FIRST_ONSET_TARGET_SEC)  # 0.000s immediate speech onset on expressive_25d_v8
    elif prosody_active:
        lead_sec = 0.05  # P1: first audible onset <= 0.10s including the 30ms consonant pad

    fmt_profile_tts = resolve_shorts_format_profile(
        vp_probe,
        script_doc or {},
        {"sentences": clean_sents},
        project_id=Path(project_dir).name,
    )
    from pipeline.config import BRAIN_SIM_ONLY_DURATION_RANGE_SEC, is_brain_sim_only_plan

    if is_brain_sim_only_plan(vp_probe, script_doc):
        min_dur_sec, safe_max_total = (
            float(BRAIN_SIM_ONLY_DURATION_RANGE_SEC[0]),
            float(BRAIN_SIM_ONLY_DURATION_RANGE_SEC[1]),
        )
    elif is_micro_short or fmt_profile_tts == MICRO_SHORT_PROFILE:
        min_dur_sec = float(MICRO_SHORT_DURATION_MIN_SEC)
        safe_max_total = float(MICRO_SHORT_DURATION_MAX_SEC)
    elif fmt_profile_tts in (SHORTS_90S_PROFILE, SHORTS_EXPRESSIVE_V8_PROFILE):
        min_dur_sec, safe_max_total = shorts_duration_range_for_profile(
            fmt_profile_tts,
            project_id=Path(project_dir).name,
        )
    else:
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

    used_act_continuous_edge = False
    used_elevenlabs_v4 = False
    el_meta_report: dict[str, Any] = {}
    el_pre_asr_by_idx: dict[int, list[tuple[float, float, str]]] = {}
    use_rate: str | None = str(rate or "+0%")
    use_pitch: str | None = "+0Hz"
    use_volume: str | None = "+0%"
    intact_retry_set: set[int] = {int(x) for x in (retry_intact_sentence_indices or ()) if int(x) >= 1}

    if pre_synthesized_lines is None and not allow_test_stub:
        from pipeline.tts import synthesize_elevenlabs_v4_episode

        el_gears = [str(pl["gear"]) for pl in pros_plan] if prosody_active else None
        is_r78v_ep = bool((script_doc or {}).get("r78v_5tone_siren")) or any(
            g in ("surprised_lift", "insider_reveal", "hushed_suspense", "deadpan_drop")
            for g in (el_gears or ())
        )
        el_foil_spec = dict(DIORAMA_VOICE_PRESETS.get("elevenlabs_v4_male") or {})
        el_res = synthesize_elevenlabs_v4_episode(
            clean_sents,
            voice_id=str(preset_spec.get("elevenlabs_voice_id") or preset_spec.get("voice")),
            fallback_voice_id=preset_spec.get("elevenlabs_fallback_voice_id"),
            gender=str(preset_spec.get("gender") or "male"),
            gears=el_gears,
            foil_indices=foil_indices,
            foil_voice_id=str(el_foil_spec.get("elevenlabs_voice_id") or el_foil_spec.get("voice") or ""),
            foil_fallback_voice_id=el_foil_spec.get("elevenlabs_fallback_voice_id"),
            foil_gender=str(el_foil_spec.get("gender") or "male"),
            speaker_voice_by_idx=speaker_voice_by_idx or None,
            preserve_exclamation=bool(is_v8),
            sr=sr,
            r78v_5tone=is_r78v_ep,
            force_refresh_indices=intact_retry_set,
        )
        raw_pcms = []
        for idx_el, pcm_raw_el in enumerate(el_res["pcms"], start=1):
            sp_preset_el = foil_preset_by_idx.get(idx_el)
            if sp_preset_el and sp_preset_el in DIORAMA_VOICE_PRESETS:
                v_filt = _vocal_filter_for_spec(DIORAMA_VOICE_PRESETS[sp_preset_el])
            elif idx_el in foil_indices:
                v_filt = foil_vocal_filter
            else:
                v_filt = eff_vocal_filter
            raw_pcms.append(_master_storyteller_vocal(pcm_raw_el, sr, sr, vocal_filter=v_filt))
        el_pre_asr_by_idx = dict(el_res.get("word_timestamps_by_idx") or {})
        used_elevenlabs_v4 = True
        used_act_continuous_edge = True
        chosen_engine = "eleven_v4"
        use_voice = str(el_res.get("voice_id") or preset_spec.get("voice"))
        use_speed = 1.0
        if native_gear_synth and pros_plan:
            synth_rates_used = [str(pl["synth_rate"]) for pl in pros_plan]
        el_meta_report = {
            "elevenlabs_characters_used": int(el_res.get("characters_used") or 0),
            "elevenlabs_script_characters": int(el_res.get("script_characters") or 0),
            "elevenlabs_model_id": str(el_res.get("model_id") or "eleven_v4"),
            "elevenlabs_output_format": str(el_res.get("output_format") or "mp3_44100_192"),
            "elevenlabs_request_ids": list(el_res.get("request_ids") or []),
            "elevenlabs_used_voices_by_idx": {
                str(k): v for k, v in (el_res.get("used_voices_by_idx") or {}).items()
            },
        }
    else:
        chosen_engine = "test_stub"
        use_voice = str(voice or preset_spec.get("voice") or "CwhRBWXzGAHq8TQ4Fs17")
        use_speed = float(speed if speed is not None else 1.0)
        raw_pcms = []
        use_native_stub_gears = bool(
            prosody_active and native_gear_synth and pre_synthesized_lines is None and speed is None
        )
        if use_native_stub_gears:
            used_act_continuous_edge = True
            synth_rates_used = [str(pl["synth_rate"]) for pl in pros_plan]
        for idx, sent in enumerate(clean_sents, start=1):
            if pre_synthesized_lines is not None and idx - 1 < len(pre_synthesized_lines) and idx not in intact_retry_set:
                pcm_i = np.asarray(pre_synthesized_lines[idx - 1], dtype=np.float32)
            else:
                sent_tempo = (
                    float(pros_plan[idx - 1]["target_tempo"])
                    if use_native_stub_gears and (idx - 1) < len(pros_plan)
                    else use_speed
                )
                pcm_i = _synthesize_test_stub_pcm(sent, sr=sr, target_tempo=sent_tempo, seed_idx=idx)
            raw_pcms.append(pcm_i)

    from pipeline.media_cache import get_speed_cache_dir

    run_whisper_align = bool(align_whisper and pre_synthesized_lines is None and not allow_test_stub)
    local_word_cache_dir = get_speed_cache_dir() / "tts_words"
    local_word_cache_dir.mkdir(parents=True, exist_ok=True)
    proj_hash = hashlib.sha1(str(Path(project_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    local_word_cache_path = local_word_cache_dir / f"whisper_word_cache_{proj_hash}.json"
    fuse_word_cache_path = cache / "whisper_word_cache.json"
    word_cache: dict[str, list[list[Any]]] = {}
    if run_whisper_align:
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
    pre_asr_by_idx: dict[int, list[tuple[float, float, str]]] = dict(el_pre_asr_by_idx)
    sent_w_keys: list[str] = []
    if run_whisper_align:
        uncached_items: list[tuple[int, np.ndarray]] = []
        for s_idx, (sent, pcm_i) in enumerate(zip(clean_sents, raw_pcms)):
            w_key = hashlib.sha256(pcm_i.astype(np.float32).tobytes() + b"|v2|" + to_display_text(sent).encode("utf-8")).hexdigest()[:20]
            sent_w_keys.append(w_key)
            if not word_cache.get(w_key) and s_idx not in pre_asr_by_idx:
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
                    segs_b, _ = _whisper_model(cpu_threads=cpu_budget).transcribe(
                        merged_16k,
                        word_timestamps=True,
                        language="en",
                    )
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
                except Exception as exc:  # noqa: BLE001
                    import logging

                    logging.getLogger("audio_utils").warning(
                        "Batched Whisper word alignment failed; falling back to per-sentence alignment: %s",
                        exc,
                        exc_info=True,
                    )
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
        if run_whisper_align:
            w_key = sent_w_keys[s_idx]
            cached_entry = word_cache.get(w_key)
            if cached_entry:
                w_list_i = [(float(x[0]), float(x[1]), str(x[2])) for x in cached_entry]
            else:
                w_list_i, used_real_asr = _word_times_aligned(
                    pcm_i,
                    sr,
                    sent,
                    pre_asr_raw=pre_asr_by_idx.get(s_idx),
                    cpu_threads=cpu_budget,
                )
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
                lead_pad_sec=(0.0 if (is_v8 and s_idx == 0) else 0.030),
            )
        if prosody_active:
            pcm_i, w_list_i, n_hits = apply_emphasis(pcm_i, sr, w_list_i, emphasis_words_for(script_doc, s_idx + 1))
            pros_emph_hits.append(n_hits)
            pros_pre_tempo_dur.append(len(pcm_i) / float(sr))
            # Native gear synthesis -> residual factor vs the rate this slice was actually synthesized at (1.0 normally).
            # Kokoro / failed-gear fallback -> WSOLA atempo from the synthesized speed to the gear target.
            if native_gear_synth and s_idx < len(synth_rates_used):
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
    nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + outro_tail_sec
    if prosody_active and pros_gaps and nominal_total > safe_max_total - 0.30:
        from pipeline.config import (
            EXPRESSIVE_V8_GAP_WINDOW_RANGE_SEC,
            EXPRESSIVE_V8_POST_HOOK_PAUSE_RANGE_SEC,
            EXPRESSIVE_V8_R77N_GAP_WINDOW_RANGE_SEC,
            is_r77n_v8_script,
        )

        is_r77n_tts = is_r77n_v8_script(script_doc, vp_probe, project_id=Path(project_dir).name)
        gap_floor = float(
            (EXPRESSIVE_V8_R77N_GAP_WINDOW_RANGE_SEC if is_r77n_tts else EXPRESSIVE_V8_GAP_WINDOW_RANGE_SEC)[0]
        ) if is_v8 else 0.20
        post_hook_floor = min(float(EXPRESSIVE_V8_POST_HOOK_PAUSE_RANGE_SEC[0]), 0.28) if is_r77n_tts else float(EXPRESSIVE_V8_POST_HOOK_PAUSE_RANGE_SEC[0])
        floors = [
            post_hook_floor if (idx_g == 0 and bool(pros_plan[1].get("post_hook_pause_before"))) else gap_floor
            for idx_g in range(len(pros_gaps))
        ]
        excess_sec = nominal_total - (safe_max_total - 0.45)
        avail_shrink = sum(max(0.0, g - fl) for g, fl in zip(pros_gaps, floors))
        if avail_shrink > 1e-4 and excess_sec > 0:
            shrink_ratio = min(1.0, excess_sec / avail_shrink)
            pros_gaps = [round(g - max(0.0, g - fl) * shrink_ratio, 3) for g, fl in zip(pros_gaps, floors)]
            nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + outro_tail_sec
    if used_act_continuous_edge and (not v7_mode) and nominal_total > safe_max_total - 0.30 and n_act_gaps > 0:
        avail_act_gap = (safe_max_total - 0.50 - lead_sec - raw_speech_sum - outro_tail_sec) / float(n_act_gaps)
        act_extra_sec = round(max(0.16, min(DIORAMA_ACT_BOUNDARY_PAUSE_SEC, avail_act_gap)), 3)
        nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + outro_tail_sec
    if n_gaps > 0 and (nominal_total > safe_max_total - 0.30 or nominal_total < min_dur_sec):
        if v7_mode and nominal_total > safe_max_total - 0.30:
            fit_target_sec = safe_max_total - 0.45
        elif v7_mode and nominal_total < min_dur_sec:
            fit_target_sec = min_dur_sec + 1.5
        else:
            fit_target_sec = DIORAMA_DURATION_TARGET_SEC
        ideal_pause = (
            fit_target_sec - lead_sec - raw_speech_sum - n_act_gaps * act_extra_sec - outro_tail_sec
        ) / float(n_gaps)
        pause_sec = round(max(pause_lo, min(pause_hi, ideal_pause)), 3)
        nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + outro_tail_sec
        if v7_mode and nominal_total > safe_max_total - 0.30 and n_act_gaps > 0:
            avail_act_extra = (
                (safe_max_total - 0.45) - lead_sec - raw_speech_sum - outro_tail_sec - n_gaps * pause_sec
            ) / float(n_act_gaps)
            act_extra_sec = round(max(0.04, min(act_extra_sec, avail_act_extra)), 3)
            nominal_total = lead_sec + raw_speech_sum + _total_gap_sec(pause_sec) + outro_tail_sec

    # Step 2: If still outside [min_dur_sec, safe_max_total - 0.30], apply bounded pitch-preserving atempo
    atempo_factor = 1.0
    atempo_lo, atempo_hi = DIORAMA_ATEMPO_FIT_RANGE
    atempo_cap = 1.24 if used_elevenlabs_v4 else min(1.15, max(float(atempo_hi), 1.15))
    if nominal_total > safe_max_total - 0.30:
        req_speech = max(10.0, (safe_max_total - 0.60) - lead_sec - _total_gap_sec(pause_sec) - outro_tail_sec)
        atempo_factor = min(atempo_cap, max(1.003, raw_speech_sum / req_speech))
    elif nominal_total < min_dur_sec + 1.0:
        req_speech = (min_dur_sec + 1.5) - lead_sec - _total_gap_sec(pause_sec) - outro_tail_sec
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

    # Step 3: Verify post-atempo speech fits within active ceiling - outro_sec (zero silent truncation)
    outro_sec = float(outro_tail_sec)
    eff_hard_ceiling = min(float(SHORTS_HARD_CEILING_SEC), float(safe_max_total))
    hard_speech_ceiling = round(eff_hard_ceiling - outro_sec, 3)
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
    gap_windows: list[list[float]] = []
    events: list[tuple[float, float, list[str]]] = []
    prev_ev_end = 0.0

    for idx, (sent, pcm_i, w_list) in enumerate(zip(clean_sents, raw_pcms, raw_word_lists), start=1):
        s_dur = len(pcm_i) / float(sr)
        s_start = cursor
        s_end = cursor + s_dur

        # Splice hygiene: every sentence slice starts and ends at exactly zero before the zero-gap is inserted
        chunks.append(
            fade_edges(pcm_i, sr, fade_sec=(0.004 if (is_v8 and idx == 1) else None))
            if v7_mode
            else pcm_i
        )
        sentence_spans.append(
            {
                "sentence_index": idx,
                "speaker": speaker_role_by_idx.get(idx, ("foil" if idx in foil_indices else "narrator")),
                "act_boundary_after": (idx in act_boundary_sents),
                "start_sec": round(s_start, 3),
                "end_sec": round(s_end, 3),
                "duration_sec": round(s_dur, 3),
                "text": sent,
                "display_text": to_display_text(sent),
            }
        )
        sub_max_words = int(EXPRESSIVE_V8_SUBTITLE_MAX_WORDS if is_v8 else DIORAMA_SUBTITLE_MAX_WORDS)
        phrases = _phrases(w_list, sub_max_words)
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
            if gap_s >= 0.02:
                gap_windows.append([round(s_end, 3), round(s_end + gap_s, 3)])
            chunks.append(np.zeros(gap_n, dtype=np.float32))
            cursor += gap_s

    speech_end_sec = round(cursor, 3)
    raw_total_sec = min(SHORTS_HARD_CEILING_SEC, speech_end_sec + outro_tail_sec)
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
    script_file_p = next(
        (p for p in (Path(project_dir) / "02_script" / "script.json", Path(project_dir) / "script.json") if p.exists()),
        None,
    )
    script_sha256 = hashlib.sha256(script_file_p.read_bytes()).hexdigest() if script_file_p else ""
    sentences_sha256 = hashlib.sha256(
        json.dumps([str(s).strip() for s in clean_sents], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
    ).hexdigest()
    voice_report = {
        "source": "tts_fallback",
        "profile": "neuro_diorama",
        "schema_version": (PROMPT_SCHEMA_VERSION_V8 if is_v8 else (7 if v7_mode else 6)),
        "script_sha256": script_sha256,
        "sentences_sha256": sentences_sha256,
        "fps": target_fps,
        "engine": chosen_engine,
        "voice": use_voice,
        "voice_preset": eff_preset,
        "foil_voice": (str(foil_spec["voice"]) if foil_indices else None),
        "foil_voice_preset": (foil_preset_id if foil_indices else None),
        "foil_sentence_indices": sorted(foil_indices),
        "eq_profile": preset_spec.get("eq_profile", "male_studio"),
        "rate": use_rate,
        "pitch": use_pitch,
        "volume": use_volume,
        "speed": use_speed,
        "atempo_applied": round(atempo_factor, 4),
        "pause_sec": pause_sec,
        "outro_tail_sec": round(outro_tail_sec, 3),
        "sentence_count": len(sentence_spans),
        "speech_end_sec": speech_end_sec,
        "total_duration_sec": total_duration_sec,
        "active_speech_ratio": active_ratio,
        "true_rms_voiced_ratio": true_rms_ratio,
        "sentence_spans": sentence_spans,
        "gap_windows": gap_windows,
        "events": [[t0, t1, ws] for t0, t1, ws in events],
        "native_f0": {"passed": True, "reason": "diorama_continuous_tts_master", "regenerate_clips": []},
        **el_meta_report,
    }
    def _commit_audio_json(dst_j: Path, payload_j: dict[str, Any]) -> None:
        with ram_tempdir(prefix="aab_vr_") as td_j:
            tmp_j = Path(td_j) / dst_j.name
            tmp_j.write_text(json.dumps(payload_j, indent=2, ensure_ascii=False), encoding="utf-8")
            atomic_commit_from_scratch(tmp_j, dst_j)

    _commit_audio_json(audio_dir / "voice_report.json", voice_report)
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
        from pipeline.prosody_qa import GEARS as _PROS_GEARS

        pros_report = {
            "prosody_mode": eff_prosody_mode,
            "base_rate": use_rate,
            "native_gear_synthesis": bool(native_gear_synth and (used_act_continuous_edge or bool(synth_rates_used))),
            "gear_rates": sorted(set(synth_rates_used)) if synth_rates_used else [use_rate],
            "global_atempo": round(atempo_factor, 4),
            "speech_end_sec": speech_end_sec,
            "total_duration_sec": total_duration_sec,
            "gear_counts": {
                g: sum(1 for r in pros_rows if r["gear"] == g)
                for g in _PROS_GEARS
                if g in ("rush", "stamp", "brisk") or any(r["gear"] == g for r in pros_rows)
            },
            "sentences": pros_rows,
        }
        _commit_audio_json(audio_dir / "prosody_report.json", pros_report)
        voice_report["prosody_mode"] = eff_prosody_mode
        _commit_audio_json(audio_dir / "voice_report.json", voice_report)
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
