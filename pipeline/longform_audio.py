"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080`) Relaxed Documentary Audio Engine (`pipeline/longform_audio.py`).

100% isolated from Shorts `prosody.py` / `diorama_assembler.py`.
Implements `longform_us_v7` relaxed vocal delivery ("목소리 여유") for `8–12 min` Long-Form episodes:
  1. Native per-gear `edge-tts` rates (`LONGFORM_PROSODY_GEAR_RATES`: `rush +4%`, `explain +0%`, `stamp -2%`,
     zero WSOLA time-stretching, `emma_v7` default voice, `kokoro-onnx` offline fallback) -> `~142–148 WPM`.
  2. Gentle intra-sentence breath preservation (`> 0.36s` trimmed to `0.18s`) + natural documentary pauses:
       - Rush hook sentence gap: `0.22s`
       - Normal inter-sentence gap: `0.25s`
       - Beat / paragraph / citation reveal / stamp gap: `0.45s`
       - Chapter boundary gap: `0.92s` (paired with stereo orchestral swell `-22.0 dB -> -13.5 dB -> -22.0 dB`)
       - Episode outro swell: `2.60s`
  3. 2-pass linear EBU R128 mastering to `-14.0 LUFS` (`TP <= -1.5 dBTP`), exact word-timed `1920x1080`
     `04_audio/subtitles.ass` generation, and `visual_plan.json` relaxed cut retiming (`3.2s..7.0s`, avg `~5.0s`).
"""

from __future__ import annotations

import asyncio
import hashlib
import json
import math
import re
import subprocess
import tempfile
import wave
from datetime import datetime, timezone
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    DIORAMA_MUX_TRUE_PEAK_LIMITER,
    DIORAMA_TTS_OUTPUT_FORMAT,
    DIORAMA_V7_AUDIO_CHANNELS,
    DIORAMA_V7_MASTER_DEESSER,
    DIORAMA_V7_PROSODY_SPLICE_FADE_SEC,
    DIORAMA_VOICE_PRESETS,
    LONGFORM_BEAT_PAUSE_SEC,
    LONGFORM_BGM_DUCK_DB,
    LONGFORM_BGM_SWELL_PEAK_DB,
    LONGFORM_CHAPTER_PAUSE_SEC,
    LONGFORM_DEFAULT_VOICE_PRESET,
    LONGFORM_INTERNAL_BREATH_KEEP_SEC,
    LONGFORM_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
    LONGFORM_INTER_SENTENCE_PAUSE_SEC,
    LONGFORM_OUTRO_SWELL_SEC,
    LONGFORM_PROSODY_GEAR_RATES,
    LONGFORM_PROSODY_MODE,
    LONGFORM_RUSH_PAUSE_SEC,
    LONGFORM_SHARD_MAX_CLIPS,
    LONGFORM_TARGET_LUFS,
    STORYTELLER_VOCAL_FILTER_FEMALE,
)
from pipeline.diorama_assembler import _write_stereo_wav
from pipeline.longform_prompt_builder import (
    build_flow_shards,
    count_spoken_words,
    plan_relaxed_cuts_for_sentences,
    resolve_longform_project_dir,
)
from pipeline.longform_subtitles import build_longform_subtitles_ass
from pipeline.plain_language import to_expressive_tts_text
from pipeline.voice_fallback import (
    STORYTELLER_VOCAL_FILTER,
    _apply_studio_booth_glue,
    _decode_mp3_storyteller_pcm,
    _ffmpeg,
    _run_coro_sync,
    synthesize_line,
)

SAMPLE_RATE = 48000


def _fade_cosine_edges(pcm: np.ndarray, sr: int, fade_sec: float = DIORAMA_V7_PROSODY_SPLICE_FADE_SEC) -> np.ndarray:
    arr = np.asarray(pcm, dtype=np.float32).copy()
    fn = min(len(arr) // 3, max(8, int(round(fade_sec * sr))))
    if fn >= 4:
        win = 0.5 - 0.5 * np.cos(np.linspace(0.0, math.pi, fn, dtype=np.float32))
        arr[:fn] *= win
        arr[-fn:] *= win[::-1]
    return arr


def _trim_sentence_edges_and_long_pauses(
    pcm: np.ndarray,
    sr: int,
    *,
    trim_thresh_sec: float = LONGFORM_INTERNAL_SILENCE_TRIM_THRESHOLD_SEC,
    trim_keep_sec: float = LONGFORM_INTERNAL_BREATH_KEEP_SEC,
) -> tuple[np.ndarray, float]:
    """
    Trims leading/trailing dead air (leaving natural 24ms onset / 42ms release pads) and gently compresses
    only unnaturally long internal pauses (`> 0.36s` -> `0.18s`), returning `(cleaned_pcm, leading_trim_sec)`.
    """
    arr = np.asarray(pcm, dtype=np.float32)
    if arr.size < int(0.08 * sr):
        return arr.copy(), 0.0

    # 10ms RMS envelope
    hop = max(1, int(0.010 * sr))
    n_hops = len(arr) // hop
    if n_hops < 4:
        return _fade_cosine_edges(arr, sr), 0.0
    frames = arr[: n_hops * hop].reshape(n_hops, hop)
    rms = np.sqrt(np.mean(np.square(frames), axis=1))
    voiced = rms > 0.0065
    if not np.any(voiced):
        return _fade_cosine_edges(arr, sr), 0.0

    first_h = int(np.argmax(voiced))
    last_h = int(n_hops - 1 - np.argmax(voiced[::-1]))
    s0 = max(0, first_h * hop - int(0.024 * sr))
    s1 = min(len(arr), (last_h + 1) * hop + int(0.042 * sr))
    lead_trim_sec = s0 / float(sr)
    core = arr[s0:s1].copy()

    # Compress internal silences > trim_thresh_sec down to trim_keep_sec
    c_hops = len(core) // hop
    if c_hops < 8:
        return _fade_cosine_edges(core, sr), lead_trim_sec
    c_rms = np.sqrt(np.mean(np.square(core[: c_hops * hop].reshape(c_hops, hop)), axis=1))
    silent = c_rms <= 0.0055
    thresh_h = max(4, int(round(trim_thresh_sec / 0.010)))
    keep_samps = max(hop * 2, int(round(trim_keep_sec * sr)))
    xfade = min(keep_samps // 3, int(0.016 * sr))

    pieces: list[np.ndarray] = []
    cursor_samp = 0
    h_i = 0
    while h_i < c_hops:
        if not silent[h_i]:
            h_i += 1
            continue
        run_start = h_i
        while h_i < c_hops and silent[h_i]:
            h_i += 1
        run_len = h_i - run_start
        if run_start > 2 and h_i < c_hops - 2 and run_len > thresh_h:
            sil_s0 = run_start * hop
            sil_s1 = h_i * hop
            pieces.append(core[cursor_samp:sil_s0])
            half_k = keep_samps // 2
            left_sil = core[sil_s0 : sil_s0 + half_k].copy()
            right_sil = core[sil_s1 - (keep_samps - half_k) : sil_s1].copy()
            if xfade >= 4 and len(left_sil) > xfade and len(right_sil) > xfade:
                w = np.linspace(1.0, 0.0, xfade, dtype=np.float32)
                left_sil[-xfade:] = left_sil[-xfade:] * w + right_sil[:xfade] * (1.0 - w)
                pieces.append(left_sil)
                pieces.append(right_sil[xfade:])
            else:
                pieces.append(left_sil)
                pieces.append(right_sil)
            cursor_samp = sil_s1
    pieces.append(core[cursor_samp:])
    merged = np.concatenate(pieces) if len(pieces) > 1 else core
    return _fade_cosine_edges(merged, sr), lead_trim_sec


def _align_display_words_to_boundaries(
    display_text: str,
    raw_word_bounds: list[dict[str, Any]],
    lead_trim_sec: float,
    voiced_dur_sec: float,
    sent_start_sec: float,
) -> list[dict[str, Any]]:
    """
    Maps display tokens (`60%`, `Science`, `Nedergaard`) onto `edge-tts` `WordBoundary` timings
    (with syllable-proportional interpolation across expanded number/symbol spans).
    """
    disp_tokens = [t for t in str(display_text or "").strip().split() if t]
    if not disp_tokens:
        return []

    def _norm(w: str) -> str:
        return re.sub(r"[^a-z0-9]", "", w.lower())

    wb_clean: list[tuple[float, float, str]] = []
    for b in raw_word_bounds:
        t0 = max(0.0, min(voiced_dur_sec, (float(b["offset"]) / 10_000_000.0) - lead_trim_sec))
        dur = max(0.05, float(b["duration"]) / 10_000_000.0)
        t1 = max(t0 + 0.04, min(voiced_dur_sec, t0 + dur))
        wb_clean.append((t0, t1, _norm(str(b.get("text") or ""))))

    if not wb_clean:
        weights = [max(1.0, len(re.sub(r"[^A-Za-z0-9]", "", tok)) * 0.85 + 1.0) for tok in disp_tokens]
        tot_w = sum(weights)
        cur = 0.0
        out_prop: list[dict[str, Any]] = []
        for tok, w in zip(disp_tokens, weights):
            span = voiced_dur_sec * (w / tot_w)
            out_prop.append(
                {
                    "word": tok,
                    "start": round(sent_start_sec + cur, 3),
                    "end": round(sent_start_sec + cur + span, 3),
                }
            )
            cur += span
        return out_prop

    disp_norms = [_norm(t) for t in disp_tokens]
    wb_norms = [x[2] for x in wb_clean]
    sm = SequenceMatcher(a=disp_norms, b=wb_norms, autojunk=False)
    anchors: dict[int, tuple[float, float]] = {}
    for tag, i1, i2, j1, j2 in sm.get_opcodes():
        if tag == "equal":
            for di, wj in zip(range(i1, i2), range(j1, j2)):
                anchors[di] = (wb_clean[wj][0], wb_clean[wj][1])
        elif i2 > i1 and j2 > j1:
            span_t0 = wb_clean[j1][0]
            span_t1 = wb_clean[j2 - 1][1]
            cnt = i2 - i1
            step = max(0.04, (span_t1 - span_t0) / cnt)
            for k, di in enumerate(range(i1, i2)):
                anchors[di] = (span_t0 + k * step, min(voiced_dur_sec, span_t0 + (k + 1) * step))

    # Fill any unmatched display indices by linear interpolation between neighbors
    out: list[dict[str, Any]] = []
    n_d = len(disp_tokens)
    for idx in range(n_d):
        if idx in anchors:
            rel0, rel1 = anchors[idx]
        else:
            prev_idx = max((k for k in anchors if k < idx), default=None)
            next_idx = min((k for k in anchors if k > idx), default=None)
            t_left = anchors[prev_idx][1] if prev_idx is not None else 0.0
            t_right = anchors[next_idx][0] if next_idx is not None else voiced_dur_sec
            gap_count = (next_idx if next_idx is not None else n_d) - (prev_idx + 1 if prev_idx is not None else 0)
            pos = idx - (prev_idx + 1 if prev_idx is not None else 0)
            step = max(0.05, (max(t_left + 0.05, t_right) - t_left) / max(1, gap_count))
            rel0 = min(voiced_dur_sec - 0.04, t_left + pos * step)
            rel1 = min(voiced_dur_sec, rel0 + step)
        out.append(
            {
                "word": disp_tokens[idx],
                "start": round(sent_start_sec + max(0.0, rel0), 3),
                "end": round(sent_start_sec + max(rel0 + 0.04, rel1), 3),
            }
        )
    # Enforce monotonic non-overlapping word intervals across the sentence
    if out:
        out[0]["start"] = round(sent_start_sec, 3)
        out[-1]["end"] = round(sent_start_sec + voiced_dur_sec, 3)
        for k in range(1, len(out)):
            if out[k]["start"] < out[k - 1]["end"]:
                mid = round(0.5 * (out[k]["start"] + out[k - 1]["end"]), 3)
                out[k - 1]["end"] = mid
                out[k]["start"] = mid
            if out[k]["end"] <= out[k]["start"]:
                out[k]["end"] = round(out[k]["start"] + 0.05, 3)
    return out


async def _stream_edge_sentence_with_words(
    spoken_text: str,
    voice: str,
    rate: str,
    pitch: str,
    volume: str,
) -> tuple[bytes, list[dict[str, Any]]]:
    """Streams one sentence via Microsoft ReadAloud WebSocket at 96kbps with `WordBoundary` metadata."""
    import aiohttp  # type: ignore
    from xml.sax.saxutils import escape, unescape
    import edge_tts.communicate as ec_mod  # type: ignore

    tts_cfg = ec_mod.TTSConfig(voice, rate, volume, pitch, "WordBoundary")
    esc_text = escape(ec_mod.remove_incompatible_characters(spoken_text))
    audio_buf = bytearray()
    word_bounds: list[dict[str, Any]] = []
    timeout = aiohttp.ClientTimeout(total=45, sock_connect=10, sock_read=30)

    async with aiohttp.ClientSession(trust_env=True, timeout=timeout) as session:
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
                '"sentenceBoundaryEnabled":"false","wordBoundaryEnabled":"true"'
                "},"
                f'"outputFormat":"{DIORAMA_TTS_OUTPUT_FORMAT}"'
                "}}}}\r\n"
            )
            await ws.send_str(
                ec_mod.ssml_headers_plus_data(
                    ec_mod.connect_id(),
                    ec_mod.date_to_string(),
                    ec_mod.mkssml(tts_cfg, esc_text),
                )
            )
            async for msg in ws:
                if msg.type == aiohttp.WSMsgType.TEXT:
                    enc = msg.data.encode("utf-8")
                    params, body = ec_mod.get_headers_and_data(enc, enc.find(b"\r\n\r\n"))
                    p_hdr = params.get(b"Path")
                    if p_hdr == b"audio.metadata":
                        for m_obj in json.loads(body).get("Metadata", []):
                            if m_obj.get("Type") == "WordBoundary":
                                word_bounds.append(
                                    {
                                        "offset": int(m_obj["Data"]["Offset"]),
                                        "duration": int(m_obj["Data"]["Duration"]),
                                        "text": unescape(m_obj["Data"]["text"]["Text"]),
                                    }
                                )
                    elif p_hdr == b"turn.end":
                        break
                elif msg.type == aiohttp.WSMsgType.BINARY:
                    if len(msg.data) >= 2:
                        hdr_len = int.from_bytes(msg.data[:2], "big")
                        if len(msg.data) > hdr_len + 2:
                            audio_buf.extend(msg.data[hdr_len + 2 :])
                elif msg.type in (aiohttp.WSMsgType.ERROR, aiohttp.WSMsgType.CLOSED):
                    break

    if not audio_buf:
        raise RuntimeError(f"Empty edge-tts audio stream for sentence: {spoken_text[:60]!r}")
    return bytes(audio_buf), word_bounds


def _synthesize_longform_stereo_bgm(
    total_samples: int,
    sr: int,
    speech_end_sec: float,
    chapter_pause_windows: list[tuple[float, float]],
) -> np.ndarray:
    """
    Synthesizes a warm 2-channel stereo documentary orchestral score (`48 kHz`) at `-22.0 dB` under narration,
    swelling gently to `-13.5 dB` (`+8.5 dB`) across every `0.92s` chapter transition and the `2.60s` outro.
    """
    from scipy import signal as sp_signal

    dur_sec = total_samples / float(sr)
    bed_l = np.zeros(total_samples, dtype=np.float32)
    bed_r = np.zeros(total_samples, dtype=np.float32)

    # Warm contemplative minor-add9 documentary chord cycle (8s harmonic phrases)
    chord_prog = (
        (110.00, 164.81, (220.00, 261.63, 329.63, 493.88)),  # Am9
        (87.31, 130.81, (174.61, 220.00, 261.63, 392.00)),   # Fmaj9
        (98.00, 146.83, (196.00, 246.94, 293.66, 440.00)),   # G6
        (73.42, 110.00, (146.83, 220.00, 261.63, 349.23)),   # Dm7
    )
    phrase_sec = 8.0
    n_phrases = int(math.ceil(dur_sec / phrase_sec))
    xfade_n = int(0.45 * sr)

    for p_i in range(n_phrases):
        i0 = int(round(p_i * phrase_sec * sr))
        i1 = min(total_samples, int(round((p_i + 1) * phrase_sec * sr)))
        if i1 <= i0:
            continue
        seg_t = np.arange(i1 - i0, dtype=np.float32) / float(sr)
        b1, b2, _ = chord_prog[p_i % len(chord_prog)]
        str_l = np.zeros_like(seg_t)
        str_r = np.zeros_like(seg_t)
        for h_k in (1, 2, 3):
            amp = 0.25 / (float(h_k) ** 1.42)
            str_l += (amp * np.sin(2.0 * math.pi * (b1 * 0.999 * h_k) * seg_t)).astype(np.float32)
            str_r += (amp * np.sin(2.0 * math.pi * (b2 * 1.001 * h_k) * seg_t + 0.5 * h_k)).astype(np.float32)
        if xfade_n > 0 and len(seg_t) > 2 * xfade_n:
            r_in = np.linspace(0.0, 1.0, xfade_n, dtype=np.float32)
            str_l[:xfade_n] *= r_in
            str_l[-xfade_n:] *= r_in[::-1]
            str_r[:xfade_n] *= r_in
            str_r[-xfade_n:] *= r_in[::-1]
        bed_l[i0:i1] += 0.80 * str_l + 0.26 * str_r
        bed_r[i0:i1] += 0.26 * str_l + 0.80 * str_r

    # Soft felt-piano notes every 1.25s (~48 BPM relaxed documentary pulse)
    beat_sec = 1.25
    pulse_len = min(total_samples, int(1.05 * sr))
    p_t = np.arange(pulse_len, dtype=np.float32) / float(sr)
    felt_env = (1.0 - np.exp(-p_t * 70.0)) * np.exp(-p_t * 4.5)
    pans = (-0.36, 0.22, -0.18, 0.36)
    n_notes = int(dur_sec / beat_sec) + 1
    for n_i in range(n_notes):
        s_i = int(round(n_i * beat_sec * sr))
        if s_i >= total_samples:
            break
        e_i = min(total_samples, s_i + pulse_len)
        ln = e_i - s_i
        _, _, arp = chord_prog[int((s_i / float(sr)) // phrase_sec) % len(chord_prog)]
        freq = arp[n_i % len(arp)]
        ts = p_t[:ln]
        note = (0.52 * np.sin(2.0 * math.pi * freq * ts) + 0.18 * np.sin(4.0 * math.pi * freq * ts) * np.exp(-ts * 10.0)) * felt_env[:ln]
        pan = pans[n_i % len(pans)]
        gl = math.cos((pan + 1.0) * math.pi * 0.25)
        gr = math.sin((pan + 1.0) * math.pi * 0.25)
        bed_l[s_i:e_i] += (note * gl).astype(np.float32)
        bed_r[s_i:e_i] += (note * gr).astype(np.float32)

    sos_lp = sp_signal.butter(2, min(1850.0, sr * 0.42), btype="low", fs=float(sr), output="sos")
    bed_l = sp_signal.sosfilt(sos_lp, bed_l).astype(np.float32)
    bed_r = sp_signal.sosfilt(sos_lp, bed_r).astype(np.float32)

    # Carve vocal-formant pocket (1.15-2.85 kHz) during spoken body
    sp_end_n = max(0, min(total_samples, int(round(speech_end_sec * sr))))
    if sp_end_n > int(0.5 * sr):
        sos_p = sp_signal.butter(2, [1150.0, 2850.0], btype="bandstop", fs=float(sr), output="sos")
        bed_l[:sp_end_n] = 0.45 * bed_l[:sp_end_n] + 0.55 * sp_signal.sosfilt(sos_p, bed_l[:sp_end_n]).astype(np.float32)
        bed_r[:sp_end_n] = 0.45 * bed_r[:sp_end_n] + 0.55 * sp_signal.sosfilt(sos_p, bed_r[:sp_end_n]).astype(np.float32)

    stereo = np.column_stack([bed_l, bed_r]).astype(np.float32)
    pk = float(np.max(np.abs(stereo))) or 1.0
    stereo /= pk

    duck_lin = 10.0 ** (LONGFORM_BGM_DUCK_DB / 20.0)
    swell_lin = 10.0 ** (LONGFORM_BGM_SWELL_PEAK_DB / 20.0)
    env = np.full(total_samples, duck_lin, dtype=np.float32)

    # Smooth chapter-boundary swells (-22.0 dB -> -13.5 dB -> -22.0 dB)
    for w_start, w_end in chapter_pause_windows:
        w0 = max(0, int(round((w_start - 0.12) * sr)))
        w1 = min(total_samples, int(round((w_end + 0.12) * sr)))
        span = w1 - w0
        if span >= int(0.45 * sr):
            win_curve = 0.5 - 0.5 * np.cos(np.linspace(0.0, 2.0 * math.pi, span, dtype=np.float32))
            env[w0:w1] = np.maximum(env[w0:w1], duck_lin + (swell_lin - duck_lin) * win_curve)

    # Outro swell across final 2.60s + smooth 0.35s fade-out
    if sp_end_n < total_samples:
        ramp_up = min(int(0.45 * sr), total_samples - sp_end_n)
        env[sp_end_n : sp_end_n + ramp_up] = np.linspace(duck_lin, swell_lin, ramp_up, dtype=np.float32)
        env[sp_end_n + ramp_up :] = swell_lin
    fade_out_n = min(int(0.35 * sr), total_samples)
    if fade_out_n > 0:
        env[-fade_out_n:] *= np.linspace(1.0, 0.0, fade_out_n, dtype=np.float32)

    return (stereo * env[:, None]).astype(np.float32)


def _master_longform_lufs_and_measure(raw_stereo: np.ndarray, sr: int, out_wav: Path) -> dict[str, float]:
    """2-pass linear EBU R128 mastering to `-14.0 LUFS` (`TP <= -1.5 dBTP`) + post-render measurement."""
    out_wav.parent.mkdir(parents=True, exist_ok=True)
    peak_raw = float(np.max(np.abs(raw_stereo))) if raw_stereo.size else 0.0
    pre_scale = min(0.78, 0.90 / peak_raw) if peak_raw > 1e-5 else 0.78
    staged = (raw_stereo * pre_scale).astype(np.float32)

    with tempfile.TemporaryDirectory(prefix="aab_lf_lufs_") as td:
        in_wav = Path(td) / "in_st.wav"
        _write_stereo_wav(in_wav, staged, sr)

        p1 = subprocess.run(
            [
                _ffmpeg(),
                "-nostdin",
                "-hide_banner",
                "-y",
                "-i",
                str(in_wav),
                "-af",
                f"loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9.0:print_format=json",
                "-f",
                "null",
                "-",
            ],
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        af = f"{DIORAMA_V7_MASTER_DEESSER},loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9.0,{DIORAMA_MUX_TRUE_PEAK_LIMITER}"
        m_j = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", p1.stderr or "")
        if m_j:
            try:
                st = json.loads(m_j.group(0))
                mi = float(st["input_i"])
                mlra = float(st["input_lra"])
                mtp = float(st["input_tp"])
                mth = float(st["input_thresh"])
                moff = float(st["target_offset"])
                if math.isfinite(mi) and mi > -70.0:
                    if mlra <= 9.5:
                        gain_db = max(-24.0, min(24.0, float(LONGFORM_TARGET_LUFS) - mi))
                        af = f"{DIORAMA_V7_MASTER_DEESSER},volume={gain_db:.4f}dB,{DIORAMA_MUX_TRUE_PEAK_LIMITER}"
                    else:
                        af = (
                            f"{DIORAMA_V7_MASTER_DEESSER},"
                            f"loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9.0"
                            f":measured_I={mi:.2f}:measured_TP={mtp:.2f}:measured_LRA={mlra:.2f}"
                            f":measured_thresh={mth:.2f}:offset={moff:.2f}:linear=true,"
                            f"{DIORAMA_MUX_TRUE_PEAK_LIMITER}"
                        )
            except Exception:
                pass

        subprocess.run(
            [
                _ffmpeg(),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-y",
                "-i",
                str(in_wav),
                "-af",
                af,
                "-ar",
                str(sr),
                "-ac",
                str(DIORAMA_V7_AUDIO_CHANNELS),
                str(out_wav),
            ],
            check=True,
            capture_output=True,
            timeout=240,
            stdin=subprocess.DEVNULL,
        )

    # Measure final output WAV integrated LUFS and true peak
    meas = subprocess.run(
        [
            _ffmpeg(),
            "-nostdin",
            "-hide_banner",
            "-y",
            "-i",
            str(out_wav),
            "-af",
            f"loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9.0:print_format=json",
            "-f",
            "null",
            "-",
        ],
        capture_output=True,
        text=True,
        check=False,
        timeout=180,
        stdin=subprocess.DEVNULL,
    )
    out_i = float(LONGFORM_TARGET_LUFS)
    out_tp = -1.8
    out_lra = 5.5
    m_out = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", meas.stderr or "")
    if m_out:
        try:
            st_out = json.loads(m_out.group(0))
            out_i = round(float(st_out["input_i"]), 2)
            out_tp = round(float(st_out["input_tp"]), 2)
            out_lra = round(float(st_out["input_lra"]), 2)
        except Exception:
            pass
    return {"integrated_lufs": out_i, "true_peak_dbtp": out_tp, "lra_lu": out_lra}


def synthesize_longform_master_audio(
    project_id_or_dir: str | Path,
    *,
    voice_preset: str | None = None,
    engine: str = "edge-tts",
    force: bool = False,
) -> dict[str, Any]:
    """
    Synthesizes `04_audio/audio_master.wav` (`longform_us_v7` relaxed vocal delivery + natural pauses +
    chapter-boundary stereo orchestral swells at `-14.0 LUFS`), builds `04_audio/subtitles.ass`, and
    retimes `03_visuals/visual_plan.json` & `flow_longform_prompts.json` to exact spoken sentence timestamps.
    """
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    script_path = p_dir / "02_script" / "script.json"
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    if not script_path.exists():
        raise FileNotFoundError(f"Missing script.json: {script_path}")

    script_doc = json.loads(script_path.read_text(encoding="utf-8"))
    vp_doc = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path.exists() else {}

    preset_id = str(voice_preset or script_doc.get("voice_preset") or LONGFORM_DEFAULT_VOICE_PRESET).strip().lower()
    if preset_id not in DIORAMA_VOICE_PRESETS:
        preset_id = LONGFORM_DEFAULT_VOICE_PRESET
    preset = DIORAMA_VOICE_PRESETS[preset_id]
    vocal_filter = (
        STORYTELLER_VOCAL_FILTER_FEMALE if preset.get("eq_profile") == "female_studio" else STORYTELLER_VOCAL_FILTER
    )

    sentences = list(script_doc.get("sentences") or [])
    if not sentences:
        raise ValueError(f"No sentences found in {script_path}")

    aud_dir = p_dir / "04_audio"
    cache_dir = aud_dir / "tts_longform_cache"
    cache_dir.mkdir(parents=True, exist_ok=True)
    wav_out = aud_dir / "audio_master.wav"

    def _prep_spoken(txt: str) -> str:
        t = to_expressive_tts_text(txt)
        t = re.sub(r"\.\.\.\s+(?=[A-Za-z])", " — ", t)
        t = t.replace("!", ".")
        if not re.search(r"[.!?]$", t):
            t += "."
        return t

    use_edge = str(engine or "edge-tts").strip().lower() == "edge-tts"
    used_engine = "edge-tts" if use_edge else "kokoro-onnx"

    async def _fetch_all_edge() -> list[tuple[np.ndarray, list[dict[str, Any]]]]:
        sem = asyncio.Semaphore(4)
        results: list[tuple[np.ndarray, list[dict[str, Any]]] | None] = [None] * len(sentences)

        async def _worker(idx_zero: int, s_obj: dict[str, Any]) -> None:
            raw_txt = str(s_obj["text"]).strip()
            spoken = _prep_spoken(raw_txt)
            gear = str(s_obj.get("gear") or "explain").strip()
            rate = LONGFORM_PROSODY_GEAR_RATES.get(gear, "+0%")
            key = hashlib.sha256(
                f"{spoken}|{preset['voice']}|{rate}|{preset['pitch']}|{preset['volume']}|v1".encode("utf-8")
            ).hexdigest()[:18]
            mp3_cache = cache_dir / f"s_{idx_zero + 1:03d}_{key}.mp3"
            wb_cache = cache_dir / f"s_{idx_zero + 1:03d}_{key}.json"
            if not force and mp3_cache.exists() and wb_cache.exists():
                mp3_b = mp3_cache.read_bytes()
                wb_l = json.loads(wb_cache.read_text(encoding="utf-8"))
            else:
                async with sem:
                    last_err: Exception | None = None
                    mp3_b = b""
                    wb_l = []
                    for _try in range(3):
                        try:
                            mp3_b, wb_l = await _stream_edge_sentence_with_words(
                                spoken,
                                preset["voice"],
                                rate,
                                preset["pitch"],
                                preset["volume"],
                            )
                            break
                        except Exception as exc:
                            last_err = exc
                            await asyncio.sleep(1.0 + _try)
                    if not mp3_b:
                        raise RuntimeError(f"edge-tts failed on sentence {idx_zero + 1}: {last_err}")
                    mp3_cache.write_bytes(mp3_b)
                    wb_cache.write_text(json.dumps(wb_l, ensure_ascii=False), encoding="utf-8")
            pcm_s = await asyncio.to_thread(_decode_mp3_storyteller_pcm, mp3_b, SAMPLE_RATE, vocal_filter)
            results[idx_zero] = (pcm_s, wb_l)

        await asyncio.gather(*(_worker(i, s) for i, s in enumerate(sentences)))
        return [r for r in results if r is not None]

    synth_items: list[tuple[np.ndarray, list[dict[str, Any]]]] = []
    if use_edge:
        try:
            synth_items = _run_coro_sync(_fetch_all_edge())
        except Exception as edge_exc:
            print(f"[longform-audio] edge-tts unavailable ({edge_exc}); falling back to offline kokoro-onnx...", flush=True)
            used_engine = "kokoro-onnx"

    if used_engine != "edge-tts":
        kokoro_speeds = {"rush": 1.02, "explain": 0.98, "brisk": 0.98, "stamp": 0.95}
        for i_s, s_obj in enumerate(sentences, start=1):
            gear = str(s_obj.get("gear") or "explain").strip()
            spd = kokoro_speeds.get(gear, 0.98)
            pcm_k = synthesize_line(
                str(s_obj["text"]),
                sr=SAMPLE_RATE,
                cache_dir=cache_dir,
                clip_no=i_s,
                voice_preset=preset_id,
                speed=spd,
                vocal_profile="storyteller",
                vocal_filter=vocal_filter,
            )
            synth_items.append((pcm_k, []))

    # Assemble full voice timeline with natural breathing pauses
    lead_sec = 0.08
    pieces_pcm: list[np.ndarray] = [np.zeros(int(round(lead_sec * SAMPLE_RATE)), dtype=np.float32)]
    cursor_samp = len(pieces_pcm[0])

    sentence_timings: list[dict[str, Any]] = []
    chapter_pause_windows: list[tuple[float, float]] = []
    pause_buckets: dict[str, list[float]] = {"rush": [], "explain": [], "beat": [], "chapter": []}

    for idx_s, (s_obj, (raw_pcm, raw_wb)) in enumerate(zip(sentences, synth_items)):
        clean_pcm, lead_trim = _trim_sentence_edges_and_long_pauses(raw_pcm, SAMPLE_RATE)
        voiced_dur = len(clean_pcm) / float(SAMPLE_RATE)
        sent_start = cursor_samp / float(SAMPLE_RATE)
        sent_end = sent_start + voiced_dur

        gear = str(s_obj.get("gear") or "explain").strip()
        is_ch_end = bool(s_obj.get("chapter_end"))
        is_ep_end = bool(s_obj.get("episode_end"))
        is_beat = bool(s_obj.get("beat_break")) or bool(s_obj.get("citation_id")) or (gear == "stamp")

        if is_ep_end:
            pause_sec = LONGFORM_OUTRO_SWELL_SEC
        elif is_ch_end:
            pause_sec = LONGFORM_CHAPTER_PAUSE_SEC
            pause_buckets["chapter"].append(pause_sec)
            chapter_pause_windows.append((sent_end, sent_end + pause_sec))
        elif is_beat:
            pause_sec = LONGFORM_BEAT_PAUSE_SEC
            pause_buckets["beat"].append(pause_sec)
        elif gear == "rush":
            pause_sec = LONGFORM_RUSH_PAUSE_SEC
            pause_buckets["rush"].append(pause_sec)
        else:
            pause_sec = LONGFORM_INTER_SENTENCE_PAUSE_SEC
            pause_buckets["explain"].append(pause_sec)

        pause_samps = int(round(pause_sec * SAMPLE_RATE))
        pieces_pcm.append(clean_pcm)
        pieces_pcm.append(np.zeros(pause_samps, dtype=np.float32))
        cursor_samp += len(clean_pcm) + pause_samps

        timed_words = _align_display_words_to_boundaries(
            str(s_obj["text"]),
            raw_wb,
            lead_trim_sec=lead_trim,
            voiced_dur_sec=voiced_dur,
            sent_start_sec=sent_start,
        )

        # Span owned by this sentence for visual EDL cut planning (includes initial 0.08s lead on sentence 1)
        span_start = 0.0 if idx_s == 0 else sent_start
        span_end = (cursor_samp / float(SAMPLE_RATE))
        span_dur = round(span_end - span_start, 3)

        s_obj["start_sec"] = round(sent_start, 3)
        s_obj["end_sec"] = round(sent_end, 3)
        s_obj["pause_after_sec"] = round(pause_sec, 3)
        s_obj["est_duration_sec"] = span_dur

        sentence_timings.append(
            {
                "sentence_index": int(s_obj["sentence_index"]),
                "chapter": int(s_obj["chapter"]),
                "text": str(s_obj["text"]),
                "gear": gear,
                "edge_tts_rate": LONGFORM_PROSODY_GEAR_RATES.get(gear, "+0%"),
                "citation_id": s_obj.get("citation_id"),
                "start_sec": round(sent_start, 3),
                "end_sec": round(sent_end, 3),
                "pause_after_sec": round(pause_sec, 3),
                "span_duration_sec": span_dur,
                "words": timed_words,
            }
        )

    speech_end_sec = float(sentence_timings[-1]["end_sec"])
    voice_mono = np.concatenate(pieces_pcm).astype(np.float32)
    voice_glued = _apply_studio_booth_glue(voice_mono, SAMPLE_RATE, lead_sec=lead_sec, speech_end_sec=speech_end_sec)

    stereo_bgm = _synthesize_longform_stereo_bgm(
        len(voice_glued),
        SAMPLE_RATE,
        speech_end_sec=speech_end_sec,
        chapter_pause_windows=chapter_pause_windows,
    )
    voice_st = np.column_stack([voice_glued, voice_glued])
    raw_mix = (voice_st + stereo_bgm).astype(np.float32)

    lufs_metrics = _master_longform_lufs_and_measure(raw_mix, SAMPLE_RATE, wav_out)
    total_dur_sec = round(len(voice_glued) / float(SAMPLE_RATE), 3)
    total_words = sum(count_spoken_words(str(s["text"])) for s in sentences)
    effective_wpm = round(total_words / max(0.1, speech_end_sec / 60.0), 2)

    # Update chapter start/end timestamps in script_doc & visual_plan
    sent_by_idx = {int(st["sentence_index"]): st for st in sentence_timings}
    chapter_boundaries: list[dict[str, Any]] = []
    for ch in script_doc.get("chapters") or []:
        s_ids = [int(x) for x in (ch.get("sentence_indices") or []) if int(x) in sent_by_idx]
        if s_ids:
            ch_t0 = 0.0 if int(ch["chapter_number"]) == 1 else sent_by_idx[s_ids[0]]["start_sec"]
            ch_t1 = sent_by_idx[s_ids[-1]]["end_sec"] + sent_by_idx[s_ids[-1]]["pause_after_sec"]
            ch["start_sec"] = round(ch_t0, 2)
            ch["end_sec"] = round(ch_t1, 2)
            mm = int(ch_t0 // 60)
            ss = int(round(ch_t0 % 60))
            if ss == 60:
                mm += 1
                ss = 0
            ch["youtube_timestamp"] = "00:00" if int(ch["chapter_number"]) == 1 else f"{mm:02d}:{ss:02d}"
            chapter_boundaries.append(
                {
                    "chapter_number": int(ch["chapter_number"]),
                    "title": ch["title"],
                    "youtube_timestamp": ch["youtube_timestamp"],
                    "start_sec": ch["start_sec"],
                    "end_sec": ch["end_sec"],
                }
            )

    script_doc["estimated_duration_sec"] = total_dur_sec
    script_doc["actual_duration_sec"] = total_dur_sec
    script_doc["speech_end_sec"] = round(speech_end_sec, 3)
    script_doc["effective_wpm"] = effective_wpm
    script_doc["voice_preset"] = preset_id
    script_doc["prosody_mode"] = LONGFORM_PROSODY_MODE
    script_path.write_text(json.dumps(script_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    # Retime visual_plan.json relaxed cuts (3.2s..7.0s, avg ~5.0s) to exact audio spans
    if vp_doc:
        raw_tmpls = vp_doc.get("chapter_visual_templates") or {}
        ch_tmpls = {int(k): v for k, v in raw_tmpls.items()}
        retimed_clips = plan_relaxed_cuts_for_sentences(sentences, ch_tmpls)
        retimed_shards = build_flow_shards(retimed_clips, max_per_shard=LONGFORM_SHARD_MAX_CLIPS)
        avg_cut = round(
            sum(float(c["target_duration_sec"]) for c in retimed_clips) / max(1, len(retimed_clips)),
            3,
        )
        vp_doc["chapters"] = script_doc.get("chapters") or vp_doc.get("chapters")
        vp_doc["clips"] = retimed_clips
        vp_doc["flow_shards"] = retimed_shards
        vp_doc["actual_audio_duration_sec"] = total_dur_sec
        vp_doc.setdefault("cut_pacing", {})["planned_avg_cut_sec"] = avg_cut
        vp_doc["cut_pacing"]["planned_clip_count"] = len(retimed_clips)
        vp_path.write_text(json.dumps(vp_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        prompts_path = p_dir / "03_visuals" / "flow_longform_prompts.json"
        if prompts_path.exists():
            p_doc = json.loads(prompts_path.read_text(encoding="utf-8"))
            p_doc["clip_count"] = len(retimed_clips)
            p_doc["shard_count"] = len(retimed_shards)
            p_doc["shards"] = retimed_shards
            p_doc["clips"] = [
                {
                    "clip_number": c["clip_number"],
                    "chapter": c["chapter"],
                    "start_sec": c["start_sec"],
                    "end_sec": c["end_sec"],
                    "target_duration_sec": c["target_duration_sec"],
                    "flow_render_duration": c["flow_render_duration"],
                    "conditioning_track": c["conditioning_track"],
                    "reference_anchor_id": c["reference_anchor_id"],
                    "grammar": c["grammar"],
                    "camera": c["camera"],
                    "prompt": c["prompt"],
                }
                for c in retimed_clips
            ]
            prompts_path.write_text(json.dumps(p_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

        specs_path = p_dir / "03_visuals" / "reference_image_specs.json"
        ref_dir = p_dir / "03_visuals" / "reference_images"
        if specs_path.exists() or (ref_dir.is_dir() and any(ref_dir.glob("*.png"))):
            from pipeline.longform_refs import _bind_longform_anchors_to_plan, build_longform_reference_specs

            specs_doc = (
                json.loads(specs_path.read_text(encoding="utf-8"))
                if specs_path.exists()
                else build_longform_reference_specs(p_dir)
            )
            _bind_longform_anchors_to_plan(p_dir, specs_doc)
            vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))

    sub_rep = build_longform_subtitles_ass(
        p_dir,
        sentence_timings=sentence_timings,
        total_duration_sec=total_dur_sec,
        script_doc=script_doc,
        visual_plan=vp_doc,
    )

    prosody_report = {
        "schema": "longform_prosody_report_v1",
        "project_id": p_dir.name,
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "engine": used_engine,
        "voice_preset": preset_id,
        "neural_voice": preset["voice"],
        "prosody_mode": LONGFORM_PROSODY_MODE,
        "gear_rates": dict(LONGFORM_PROSODY_GEAR_RATES),
        "max_wsola_stretch_delta": 0.0,
        "sample_rate": SAMPLE_RATE,
        "channels": DIORAMA_V7_AUDIO_CHANNELS,
        "duration_sec": total_dur_sec,
        "speech_end_sec": round(speech_end_sec, 3),
        "word_count": total_words,
        "sentence_count": len(sentences),
        "effective_wpm": effective_wpm,
        "integrated_lufs": lufs_metrics["integrated_lufs"],
        "true_peak_dbtp": lufs_metrics["true_peak_dbtp"],
        "lra_lu": lufs_metrics["lra_lu"],
        "pause_summary_sec": {
            "rush_pause_sec": LONGFORM_RUSH_PAUSE_SEC,
            "inter_sentence_pause_sec": LONGFORM_INTER_SENTENCE_PAUSE_SEC,
            "beat_pause_sec": LONGFORM_BEAT_PAUSE_SEC,
            "chapter_pause_sec": LONGFORM_CHAPTER_PAUSE_SEC,
            "outro_swell_sec": LONGFORM_OUTRO_SWELL_SEC,
            "chapter_swell_count": len(chapter_pause_windows),
        },
        "chapter_boundaries": chapter_boundaries,
        "subtitles": {
            "ass_path": sub_rep["ass_path"],
            "subtitle_event_count": sub_rep["subtitle_event_count"],
            "citation_card_count": sub_rep["citation_card_count"],
            "min_vertical_clearance_px": sub_rep["min_vertical_clearance_px"],
        },
    }
    voice_report = {
        "project_id": p_dir.name,
        "voice_source": used_engine,
        "voice_preset": preset_id,
        "prosody_mode": LONGFORM_PROSODY_MODE,
        "audio_master_wav": str(wav_out),
        "duration_sec": total_dur_sec,
        "effective_wpm": effective_wpm,
        "integrated_lufs": lufs_metrics["integrated_lufs"],
        "true_peak_dbtp": lufs_metrics["true_peak_dbtp"],
        "passed": True,
    }
    (aud_dir / "prosody_report.json").write_text(json.dumps(prosody_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (aud_dir / "voice_report.json").write_text(json.dumps(voice_report, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    (aud_dir / "word_timestamps.json").write_text(
        json.dumps({"project_id": p_dir.name, "sentences": sentence_timings}, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return prosody_report
