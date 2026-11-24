"""ALL ABOUT BRAIN — Master Audio, Stereo BGM & Foley Synthesizer (`assembler_audio.py`)."""

from __future__ import annotations
from pipeline import config as _cfg
from pipeline.assembler_subtitles import *
from pipeline.assembler_subtitles import _KEYWORD_BEAT_SPLIT_RE, _V7_DEFAULT_CAM_CYCLE, _V8_POWER_TOKENS, _V8_STOPWORDS, _clip_duration, _ffmpeg, _format_ass_ts, _frame_boundary_ass_sec, _parse_ass_time, _sanitize_ass_multiline, _sanitize_ass_single_line, _write_mono_wav, ensure_bundled_condensed_font, generate_diorama_ass_subtitles, probe_ass_font_resolution

def _write_stereo_wav(path: Path, stereo_pcm: np.ndarray, sr: int) -> None:
    """Writes a 2-channel 16-bit PCM WAV (`shape == (N, 2)`)."""
    arr = np.asarray(stereo_pcm, dtype=np.float32)
    if arr.ndim == 1:
        arr = np.stack([arr, arr], axis=1)
    clipped = np.clip(arr, -1.0, 1.0)
    pcm16 = (clipped * 32767.0).astype(np.int16)
    path.parent.mkdir(parents=True, exist_ok=True)
    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(int(sr))
        wf.writeframes(pcm16.tobytes())


def _synthesize_documentary_pulse_bgm(
    total_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    R59 Restrained Documentary Soundscape:
      - `88 BPM` minimal warm acoustic marimba/pulse tension bed in D minor.
      - Ducked at `-24.0 dB` under voice, swelling `+8.0 dB` over the final `2.2s` sky title card.
      - Zero digital UI cut ticks; sparse physical analog impulses only on key prop actions.
    """
    t = np.arange(total_samples, dtype=np.float32) / float(sr)
    beat_sec = 60.0 / float(DIORAMA_BGM_BPM)
    sub_beat = beat_sec * 0.5  # 8th-note documentary pulse

    # Warm evolving 6-Act D-minor documentary harmonic progression (Dm9 -> Bbmaj7 -> Gm9 -> Asus4/A7 -> Fmaj7 -> Dm/Dsus2)
    act_chords: dict[int, tuple[float, float, tuple[float, ...]]] = {
        1: (73.42, 110.00, (146.83, 220.00, 174.61, 164.81, 146.83, 220.00, 196.00, 174.61)),
        2: (58.27, 87.31, (116.54, 174.61, 146.83, 220.00, 116.54, 174.61, 130.81, 146.83)),
        3: (49.00, 73.42, (98.00, 146.83, 116.54, 220.00, 98.00, 146.83, 174.61, 146.83)),
        4: (55.00, 82.41, (110.00, 164.81, 146.83, 138.59, 110.00, 196.00, 174.61, 164.81)),
        5: (65.41, 98.00, (130.81, 196.00, 174.61, 220.00, 146.83, 220.00, 261.63, 220.00)),
        6: (73.42, 110.00, (146.83, 220.00, 164.81, 174.61, 220.00, 293.66, 220.00, 174.61)),
    }
    act_windows: list[tuple[float, float, int]] = []
    for cut in edl.get("cuts") or []:
        a_no = max(1, min(6, int(cut.get("act") or 1)))
        cs0 = float(cut.get("out_start_sec") or 0.0)
        cs1 = float(cut.get("out_end_sec") or cs0)
        if act_windows and act_windows[-1][2] == a_no:
            act_windows[-1] = (act_windows[-1][0], cs1, a_no)
        else:
            act_windows.append((cs0, cs1, a_no))
    if not act_windows:
        act_windows = [(0.0, float(total_samples) / float(sr), 1)]

    def _act_at(sec_val: float) -> int:
        for w0, w1, a_no in act_windows:
            if w0 <= sec_val <= w1:
                return a_no
        return act_windows[-1][2]

    bed = np.zeros(total_samples, dtype=np.float32)
    xfade_n = int(0.18 * sr)
    for w0, w1, a_no in act_windows:
        i0 = max(0, min(total_samples, int(round(w0 * sr))))
        i1 = max(i0, min(total_samples, int(round(w1 * sr))))
        if i1 <= i0:
            continue
        b1_hz, b2_hz, _ = act_chords[a_no]
        seg_t = t[i0:i1]
        drone = (0.24 * np.sin(2.0 * math.pi * b1_hz * seg_t) + 0.14 * np.sin(2.0 * math.pi * b2_hz * seg_t)).astype(np.float32)
        if xfade_n > 0 and len(drone) > 2 * xfade_n:
            ramp = np.linspace(0.0, 1.0, xfade_n, dtype=np.float32)
            drone[:xfade_n] *= ramp
            drone[-xfade_n:] *= ramp[::-1]
        bed[i0:i1] += drone

    n_pulses = int(total_samples / max(1, int(sub_beat * sr))) + 1
    pulse_len = min(int(0.34 * sr), max(1, int(sub_beat * sr)))
    p_t = np.arange(pulse_len, dtype=np.float32) / float(sr)
    env = np.exp(-p_t * 11.5) * (1.0 - np.exp(-p_t * 140.0))
    for p_idx in range(n_pulses):
        s_i = int(round(p_idx * sub_beat * sr))
        if s_i >= total_samples:
            break
        e_i = min(total_samples, s_i + pulse_len)
        _, _, notes_hz = act_chords[_act_at(s_i / float(sr))]
        freq = notes_hz[p_idx % len(notes_hz)]
        tone = (0.65 * np.sin(2.0 * math.pi * freq * p_t[: e_i - s_i]) + 0.22 * np.sin(4.0 * math.pi * freq * p_t[: e_i - s_i])) * env[: e_i - s_i]
        bed[s_i:e_i] += tone.astype(np.float32)

    # Normalize raw bed to 0 dBFS peak before applying the -24 dB ducking & +8 dB outro swell envelope
    bed_peak = float(np.max(np.abs(bed))) or 1.0
    bed = bed / bed_peak

    duck_lin = 10.0 ** (DIORAMA_BGM_DUCK_DB / 20.0)
    swell_lin = 10.0 ** ((DIORAMA_BGM_DUCK_DB + DIORAMA_OUTRO_SWELL_GAIN_DB) / 20.0)
    gain_env = np.full(total_samples, duck_lin, dtype=np.float32)
    swell_start = min(total_samples, int(round(speech_end_sec * sr)))
    if swell_start < total_samples:
        ramp_n = min(int(0.35 * sr), total_samples - swell_start)
        gain_env[swell_start : swell_start + ramp_n] = np.linspace(duck_lin, swell_lin, ramp_n, dtype=np.float32)
        gain_env[swell_start + ramp_n :] = swell_lin
    fade_n = min(int(0.14 * sr), total_samples)
    if fade_n > 0:
        gain_env[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)
    bgm = bed * gain_env

    # Sparse physical analog foley on kinetic_trace_automata / recurring_gauge_motif cuts (max 1 every 6 cuts)
    foley = np.zeros(total_samples, dtype=np.float32)
    click_len = int(0.035 * sr)
    c_t = np.arange(click_len, dtype=np.float32) / float(sr)
    brass_click = (np.sin(2.0 * math.pi * 1180.0 * c_t) + 0.6 * np.sin(2.0 * math.pi * 420.0 * c_t)) * np.exp(-c_t * 130.0)
    last_foley_t = -10.0
    for cut in edl.get("cuts") or []:
        t0 = float(cut.get("out_start_sec") or 0.0)
        if t0 >= speech_end_sec - 0.5 or t0 - last_foley_t < 8.0:
            continue
        if cut.get("grammar") in ("kinetic_trace_automata", "recurring_gauge_motif"):
            s_i = min(total_samples, int(round((t0 + 0.12) * sr)))
            e_i = min(total_samples, s_i + click_len)
            foley[s_i:e_i] += (0.045 * brass_click[: e_i - s_i]).astype(np.float32)
            last_foley_t = t0

    return (bgm + foley).astype(np.float32)


def _synthesize_stereo_orchestral_bgm(
    total_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    R63 Schema v7 2-Channel Stereo Warm Orchestral / Acoustic Documentary Score:
      - Decorrelated stereo bowed cello + contrabass ensemble sustain (harmonics 1..7, warm wooden body filter).
      - Stereo felt-piano & marimba documentary arpeggio panned across `[-0.42, +0.42]`.
      - Convolved with a warm stereo wooden chamber impulse response (`fftconvolve`).
      - Ducked at `-22.0 dB` under centered voiceover and swelling `+8.0 dB` over the final `2.2s` sky card.
    """
    from scipy import signal as sp_signal

    t = np.arange(total_samples, dtype=np.float32) / float(sr)
    beat_sec = 60.0 / float(DIORAMA_BGM_BPM)
    sub_beat = beat_sec * 0.5

    act_chords: dict[int, tuple[float, float, tuple[float, ...]]] = {
        1: (73.42, 110.00, (146.83, 220.00, 261.63, 174.61, 164.81, 220.00, 293.66, 196.00)),
        2: (58.27, 87.31, (116.54, 174.61, 220.00, 261.63, 146.83, 174.61, 233.08, 196.00)),
        3: (65.41, 98.00, (130.81, 196.00, 220.00, 261.63, 174.61, 220.00, 293.66, 261.63)),
        4: (55.00, 82.41, (110.00, 164.81, 220.00, 196.00, 146.83, 174.61, 246.94, 164.81)),
        5: (58.27, 98.00, (146.83, 196.00, 233.08, 293.66, 220.00, 261.63, 329.63, 220.00)),
        6: (73.42, 110.00, (146.83, 220.00, 293.66, 329.63, 261.63, 220.00, 174.61, 293.66)),
    }
    act_windows: list[tuple[float, float, int]] = []
    for cut in edl.get("cuts") or []:
        a_no = max(1, min(6, int(cut.get("act") or 1)))
        cs0 = float(cut.get("out_start_sec") or 0.0)
        cs1 = float(cut.get("out_end_sec") or cs0)
        if act_windows and act_windows[-1][2] == a_no:
            act_windows[-1] = (act_windows[-1][0], cs1, a_no)
        else:
            act_windows.append((cs0, cs1, a_no))
    if not act_windows:
        act_windows = [(0.0, float(total_samples) / float(sr), 1)]

    def _act_at(sec_val: float) -> int:
        for w0, w1, a_no in act_windows:
            if w0 <= sec_val <= w1:
                return a_no
        return act_windows[-1][2]

    bed_l = np.zeros(total_samples, dtype=np.float32)
    bed_r = np.zeros(total_samples, dtype=np.float32)
    xfade_n = int(0.22 * sr)

    # Layer 1: Stereo bowed cello (L-weighted) + contrabass/viola fifth (R-weighted) with natural vibrato
    for w0, w1, a_no in act_windows:
        i0 = max(0, min(total_samples, int(round(w0 * sr))))
        i1 = max(i0, min(total_samples, int(round(w1 * sr))))
        if i1 <= i0:
            continue
        b1_hz, b2_hz, _ = act_chords[a_no]
        seg_t = t[i0:i1] - t[i0]
        vib_l = 1.0 + 0.0022 * np.sin(2.0 * math.pi * 4.55 * seg_t)
        vib_r = 1.0 + 0.0024 * np.sin(2.0 * math.pi * 4.90 * seg_t + 1.1)
        str_l = np.zeros_like(seg_t, dtype=np.float32)
        str_r = np.zeros_like(seg_t, dtype=np.float32)
        for h_k in range(1, 7):
            amp = 0.26 / (float(h_k) ** 1.38)
            ph_l = 2.0 * math.pi * (b1_hz * 0.9985 * h_k) * seg_t * vib_l
            ph_r = 2.0 * math.pi * (b2_hz * 1.0015 * h_k) * seg_t * vib_r + 0.65 * h_k
            str_l += (amp * np.sin(ph_l)).astype(np.float32)
            str_r += (amp * np.sin(ph_r)).astype(np.float32)
        if xfade_n > 0 and len(seg_t) > 2 * xfade_n:
            ramp = np.linspace(0.0, 1.0, xfade_n, dtype=np.float32)
            str_l[:xfade_n] *= ramp
            str_l[-xfade_n:] *= ramp[::-1]
            str_r[:xfade_n] *= ramp
            str_r[-xfade_n:] *= ramp[::-1]
        bed_l[i0:i1] += 0.82 * str_l + 0.28 * str_r
        bed_r[i0:i1] += 0.28 * str_l + 0.82 * str_r

    sos_body = sp_signal.butter(2, min(920.0, sr * 0.42), btype="low", fs=float(sr), output="sos")
    bed_l = sp_signal.sosfilt(sos_body, bed_l).astype(np.float32)
    bed_r = sp_signal.sosfilt(sos_body, bed_r).astype(np.float32)

    # Layer 2: Stereo felt-piano & marimba documentary arpeggio panned across [-0.42, +0.42]
    n_pulses = int(total_samples / max(1, int(sub_beat * sr))) + 1
    pulse_len = min(int(0.46 * sr), max(1, int(sub_beat * 1.35 * sr)))
    p_t = np.arange(pulse_len, dtype=np.float32) / float(sr)
    felt_env = (1.0 - np.exp(-p_t * 95.0)) * np.exp(-p_t * 6.2)
    pan_positions = (-0.42, -0.16, 0.18, 0.42, -0.28, 0.30)
    for p_idx in range(n_pulses):
        s_i = int(round(p_idx * sub_beat * sr))
        if s_i >= total_samples:
            break
        e_i = min(total_samples, s_i + pulse_len)
        seg_len = e_i - s_i
        _, _, notes_hz = act_chords[_act_at(s_i / float(sr))]
        freq = notes_hz[p_idx % len(notes_hz)]
        pt_slice = p_t[:seg_len]
        note_wave = (
            0.58 * np.sin(2.0 * math.pi * freq * pt_slice)
            + 0.24 * np.sin(4.0 * math.pi * freq * pt_slice) * np.exp(-pt_slice * 12.0)
            + 0.09 * np.sin(6.0 * math.pi * freq * pt_slice) * np.exp(-pt_slice * 20.0)
        ) * felt_env[:seg_len]
        pan = pan_positions[p_idx % len(pan_positions)]
        gain_l = math.cos((pan + 1.0) * math.pi * 0.25)
        gain_r = math.sin((pan + 1.0) * math.pi * 0.25)
        bed_l[s_i:e_i] += (note_wave * gain_l).astype(np.float32)
        bed_r[s_i:e_i] += (note_wave * gain_r).astype(np.float32)

    # Layer 3: Warm stereo wooden chamber impulse response convolution
    ir_len = max(64, int(0.46 * sr))
    ir_t = np.arange(ir_len, dtype=np.float32) / float(sr)
    rng = np.random.default_rng(707)
    ir_l = (rng.standard_normal(ir_len).astype(np.float32) * np.exp(-ir_t * 8.2)) * 0.06
    ir_r = (rng.standard_normal(ir_len).astype(np.float32) * np.exp(-ir_t * 8.0)) * 0.06
    for delay_ms, g_l, g_r in ((17.0, 0.32, 0.14), (29.0, 0.15, 0.30), (43.0, 0.22, 0.12), (61.0, 0.11, 0.21)):
        d_idx = min(ir_len - 1, int(round(delay_ms * 0.001 * sr)))
        ir_l[d_idx] += g_l
        ir_r[d_idx] += g_r
    sos_ir = sp_signal.butter(2, min(2600.0, sr * 0.45), btype="low", fs=float(sr), output="sos")
    ir_l = sp_signal.sosfilt(sos_ir, ir_l).astype(np.float32)
    ir_r = sp_signal.sosfilt(sos_ir, ir_r).astype(np.float32)
    wet_l = sp_signal.fftconvolve(bed_l, ir_l, mode="full")[:total_samples].astype(np.float32)
    wet_r = sp_signal.fftconvolve(bed_r, ir_r, mode="full")[:total_samples].astype(np.float32)
    st_l = 0.72 * bed_l + 0.28 * wet_l
    st_r = 0.72 * bed_r + 0.28 * wet_r

    # Carve a subtle 1.15-2.85 kHz vocal-formant pocket during active narration so pure sine overtones
    # never fuse into the narrator's vowels as an electronic sheen, while leaving the outro swell full-range.
    speech_samp = max(0, min(total_samples, int(round(speech_end_sec * sr))))
    if speech_samp > int(0.25 * sr) and sr >= 16000:
        sos_pocket = sp_signal.butter(
            2,
            [1150.0, min(2850.0, sr * 0.44)],
            btype="bandstop",
            fs=float(sr),
            output="sos",
        )
        p_l = sp_signal.sosfilt(sos_pocket, st_l[:speech_samp]).astype(np.float32)
        p_r = sp_signal.sosfilt(sos_pocket, st_r[:speech_samp]).astype(np.float32)
        # 55% pocket blend (~-4.5 dB smooth vocal-formant dip)
        pocket_mix = 0.55
        st_l[:speech_samp] = (1.0 - pocket_mix) * st_l[:speech_samp] + pocket_mix * p_l
        st_r[:speech_samp] = (1.0 - pocket_mix) * st_r[:speech_samp] + pocket_mix * p_r

    stereo_bed = np.column_stack([st_l, st_r]).astype(np.float32)
    bed_peak = float(np.max(np.abs(stereo_bed))) or 1.0
    stereo_bed = stereo_bed / bed_peak

    duck_lin = 10.0 ** (DIORAMA_V7_BGM_DUCK_DB / 20.0)
    swell_lin = 10.0 ** ((DIORAMA_V7_BGM_DUCK_DB + DIORAMA_OUTRO_SWELL_GAIN_DB) / 20.0)
    gain_env = np.full(total_samples, duck_lin, dtype=np.float32)
    swell_start = min(total_samples, int(round(speech_end_sec * sr)))
    if swell_start < total_samples:
        ramp_n = min(int(0.35 * sr), total_samples - swell_start)
        gain_env[swell_start : swell_start + ramp_n] = np.linspace(duck_lin, swell_lin, ramp_n, dtype=np.float32)
        gain_env[swell_start + ramp_n :] = swell_lin
    fade_n = min(int(0.14 * sr), total_samples)
    if fade_n > 0:
        gain_env[-fade_n:] *= np.linspace(1.0, 0.0, fade_n, dtype=np.float32)

    # Prosody stamp beats: drop the score to -30 dB inside the pre-stamp silence so the case stamp lands clean
    drop_lin = 10.0 ** (-30.0 / 20.0)
    ramp_d = max(8, int(0.04 * sr))
    for win in edl.get("prosody_stamp_windows") or []:
        try:
            w0, w1 = int(float(win[0]) * sr), int(float(win[1]) * sr)
        except (TypeError, ValueError, IndexError):
            continue
        w0, w1 = max(0, w0), min(total_samples, w1)
        if w1 - w0 <= 2 * ramp_d:
            continue
        seg = gain_env[w0:w1].copy()
        target = np.minimum(seg, drop_lin)
        target[:ramp_d] = np.linspace(seg[0], drop_lin, ramp_d, dtype=np.float32)
        target[-ramp_d:] = np.linspace(drop_lin, seg[-1], ramp_d, dtype=np.float32)
        gain_env[w0:w1] = target

    return (stereo_bed * gain_env[:, None]).astype(np.float32)


def _synthesize_v8_foley_oneshot(cue: str, dur_sec: float, sr: int, rng: np.random.Generator) -> np.ndarray:
    """Synthesizes a stereo procedural physical foley cue (`shape=(N, 2)`, normalized to peak 1.0)."""
    n = max(64, int(round(dur_sec * sr)))
    t = np.arange(n, dtype=np.float32) / float(sr)
    c_norm = str(cue or "pop").strip().lower()
    if c_norm == "thud":
        phase = 2.0 * np.pi * (28.0 * t + 38.0 * (1.0 - np.exp(-t / 0.028)) * 0.028)
        body = np.sin(phase) * np.exp(-t / 0.045) + 0.35 * np.sin(2.0 * np.pi * 135.0 * t) * np.exp(-t / 0.020)
        sig_l, sig_r = body, body * 0.96
    elif c_norm == "whoosh":
        nz_l = rng.standard_normal(n).astype(np.float32)
        nz_r = rng.standard_normal(n).astype(np.float32)
        freqs = np.fft.rfftfreq(n, d=1.0 / float(sr))
        bp = np.exp(-0.5 * ((freqs - 720.0) / 480.0) ** 2).astype(np.float32)
        env = np.maximum(0.0, np.sin(np.pi * np.linspace(0.0, 1.0, n, dtype=np.float32))) ** 1.4
        pan = np.linspace(0.32, 0.68, n, dtype=np.float32)
        sig_l = np.fft.irfft(np.fft.rfft(nz_l) * bp, n=n).astype(np.float32) * env * (1.0 - pan)
        sig_r = np.fft.irfft(np.fft.rfft(nz_r) * bp, n=n).astype(np.float32) * env * pan
    elif c_norm == "click":
        imp = (
            np.sin(2.0 * np.pi * 1850.0 * t) * np.exp(-t / 0.006)
            + 0.6 * np.sin(2.0 * np.pi * 3350.0 * t) * np.exp(-t / 0.0035)
        )
        sig_l, sig_r = imp, imp * 0.94
    elif c_norm == "crystal_shimmer":
        env = np.maximum(0.0, np.sin(np.pi * np.minimum(1.0, t / max(0.02, dur_sec)))) * np.exp(-t / max(0.05, dur_sec * 0.55))
        sh_l = (
            0.55 * np.sin(2.0 * np.pi * 1480.0 * t)
            + 0.30 * np.sin(2.0 * np.pi * 2220.0 * t + 0.4)
            + 0.15 * np.sin(2.0 * np.pi * 2960.0 * t + 1.1)
        ) * env
        sh_r = (
            0.55 * np.sin(2.0 * np.pi * 1483.0 * t + 0.5)
            + 0.30 * np.sin(2.0 * np.pi * 2217.0 * t + 1.2)
            + 0.15 * np.sin(2.0 * np.pi * 2964.0 * t + 0.2)
        ) * env
        sig_l, sig_r = sh_l * 0.72, sh_r * 0.72
    elif c_norm == "heartbeat_thump":
        t2 = np.maximum(0.0, t - min(0.095, dur_sec * 0.48))
        lub = np.sin(2.0 * np.pi * 48.0 * t) * np.exp(-t / 0.032)
        dub = (t >= min(0.095, dur_sec * 0.48)).astype(np.float32) * np.sin(2.0 * np.pi * 42.0 * t2) * np.exp(-t2 / 0.028)
        hb = lub + 0.82 * dub
        sig_l, sig_r = hb, hb
    else:  # "pop"
        phase = 2.0 * np.pi * (210.0 * t + 340.0 * (t ** 2) / max(0.03, dur_sec))
        pop = np.sin(phase) * np.exp(-t / 0.018)
        sig_l, sig_r = pop, pop * 0.97

    st = np.column_stack([sig_l.astype(np.float32), sig_r.astype(np.float32)])
    fade = min(n // 4, max(8, int(0.004 * sr)))
    if fade > 0:
        ramp = np.linspace(0.0, 1.0, fade, dtype=np.float32)[:, None]
        st[:fade, :] *= ramp
        st[-fade:, :] *= ramp[::-1]
    pk = float(np.max(np.abs(st))) if st.size else 0.0
    if pk > 1e-6:
        st /= pk
    return st


def _synthesize_expressive_v8_ambience_and_foley(
    n_samples: int,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> np.ndarray:
    """
    `expressive_25d_v8` Rising Dark-Suspense Soundscape (`@RicksClips3000`-calibrated):
      - Continuous minor/Phrygian dark synth-cello + sub-bass tension underscore (`C2 + G2 + C3 + Eb3 + Db3`
        slow breathing swell, zero 88-BPM beat grid, vocal-pocket low-passed below `520 Hz`, narrow/center-focused
        stereo with subtle `±0.22 Hz` chorus + `-30 dBFS` decorrelated room air).
      - Strictly monotonic rising envelope from `EXPRESSIVE_V8_BGM_START_DB` (`-25.0 dBFS` post-LUFS) at `0.0s` to
        `EXPRESSIVE_V8_BGM_PEAK_DB` / `EXPRESSIVE_V8_BGM_END_DB` (`-18.0 dBFS` post-LUFS) held through climax & ending
        with zero tail dip.
      - Crisp procedural physical foley + auto-placed camera-flight/styled-transition `whoosh`/`thud` accents.
    """
    from pipeline.config import (
        EXPRESSIVE_V8_3D_FLIGHT_MOVES,
        EXPRESSIVE_V8_BGM_BREATH_DB,
        EXPRESSIVE_V8_BGM_DUCK_DB,
        EXPRESSIVE_V8_BGM_END_DB,
        EXPRESSIVE_V8_BGM_MODE,
        EXPRESSIVE_V8_BGM_PEAK_DB,
        EXPRESSIVE_V8_BGM_START_DB,
        EXPRESSIVE_V8_BGM_TAIL_DBFS,
        EXPRESSIVE_V8_DEFAULT_BGM_MOOD,
        EXPRESSIVE_V8_FLIGHT_WHOOSH_DBFS,
        EXPRESSIVE_V8_FOLEY_PEAK_DBFS,
        EXPRESSIVE_V8_FOLEY_TYPES,
        EXPRESSIVE_V8_ROOM_AMBIENCE_DBFS,
        EXPRESSIVE_V8_ROOM_TONE_DBFS,
        EXPRESSIVE_V8_SYNTH_TONAL_FOLEY,
    )
    from pipeline.bgm import (
        synthesize_or_load_elevenlabs_bgm,
        synthesize_room_tone_only,
        synthesize_tonal_fixed_underscore,
    )

    if n_samples <= 0:
        return np.zeros((0, 2), dtype=np.float32)
    seed_val = sum(ord(ch) for ch in str(edl.get("style_profile") or "v8")) + int(n_samples % 9973)
    rng = np.random.default_rng(seed_val)
    t_sec = np.arange(n_samples, dtype=np.float32) / float(sr)
    total_sec = max(0.25, n_samples / float(sr))
    sp_end = max(0.20, min(total_sec, float(speech_end_sec or total_sec)))

    bgm_mode = str(edl.get("bgm_mode") or EXPRESSIVE_V8_BGM_MODE or "elevenlabs_music").strip().lower()
    bgm_mood = str(edl.get("bgm_mood") or EXPRESSIVE_V8_DEFAULT_BGM_MOOD).strip()
    gap_windows = edl.get("gap_windows") if isinstance(edl.get("gap_windows"), list) else []

    bgm_meta: dict[str, Any] = {"bgm_source": bgm_mode}
    if bgm_mode == "elevenlabs_music":
        unit_bgm_st, bgm_meta = synthesize_or_load_elevenlabs_bgm(
            mood_id=bgm_mood,
            duration_sec=total_sec,
            sr=sr,
            n_samples=n_samples,
        )
        if bgm_meta.get("bgm_source") == "room_tone_fallback":
            amb_st = unit_bgm_st.astype(np.float32)
        else:
            # Vocal-clear dynamic ducking: -21.5 dB pre-LUFS (~ -25.5 dB raw) during speech, gentle lift in breath gaps
            duck_db = float(EXPRESSIVE_V8_BGM_DUCK_DB) - 4.0
            breath_db = float(EXPRESSIVE_V8_BGM_BREATH_DB) - 4.0
            env_db = np.full(n_samples, duck_db, dtype=np.float32)
            for gw in gap_windows:
                if isinstance(gw, (list, tuple)) and len(gw) >= 2:
                    g0, g1 = float(gw[0]), float(gw[1])
                    i0 = max(0, min(n_samples, int(round((g0 - 0.08) * sr))))
                    i1 = max(i0, min(n_samples, int(round((g1 + 0.08) * sr))))
                    if i1 - i0 >= 16:
                        win_u = np.linspace(0.0, 1.0, i1 - i0, dtype=np.float32)
                        bump = (breath_db - duck_db) * np.sin(np.pi * win_u)
                        env_db[i0:i1] = np.maximum(env_db[i0:i1], duck_db + bump)
            bgm_st = unit_bgm_st * (10.0 ** (env_db / 20.0)).astype(np.float32)[:, None]
            room_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)
            amb_st = (bgm_st + room_st).astype(np.float32)
    elif bgm_mode == "tonal_fixed":
        tonal_st = synthesize_tonal_fixed_underscore(n_samples, sr=sr)
        tonal_rms = max(1e-6, float(np.sqrt(np.mean(np.square(tonal_st)))))
        tonal_st = tonal_st / tonal_rms
        gain_lin = float(10.0 ** ((-31.0 - 4.0) / 20.0))
        room_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)
        amb_st = (tonal_st * gain_lin + room_st).astype(np.float32)
    else:
        amb_st = synthesize_room_tone_only(n_samples, sr=sr, target_dbfs=EXPRESSIVE_V8_ROOM_TONE_DBFS, seed=seed_val)

    fade_in = min(n_samples // 6, int(0.045 * sr))
    if fade_in > 0:
        amb_st[:fade_in, :] *= np.linspace(0.15, 1.0, fade_in, dtype=np.float32)[:, None]
    fade_out = min(n_samples // 6, int(0.18 * sr))
    if fade_out > 0:
        amb_st[-fade_out:, :] *= np.linspace(1.0, 0.05, fade_out, dtype=np.float32)[:, None]

    # 2. Subtle non-tonal physical thud/whoosh foley on cut boundaries (all 1.4-3.3 kHz sine click/shimmer tones disabled)
    placed_foley: list[dict[str, Any]] = []
    cuts = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    outgoing_candidates = cuts[:-1] if len(cuts) > 1 else cuts
    foley_peak = float(10.0 ** ((float(EXPRESSIVE_V8_FOLEY_PEAK_DBFS) + 1.5) / 20.0))
    for gw in gap_windows:
        if not (isinstance(gw, (list, tuple)) and len(gw) >= 2):
            continue
        g0, g1 = float(gw[0]), float(gw[1])
        if g1 - g0 < 0.14 or g1 > sp_end + 0.05:
            continue
        w0, w1 = g0 + 0.015, g1 - 0.015
        avail = w1 - w0
        if avail < 0.08:
            continue
        mid_t = 0.5 * (w0 + w1)
        out_cut = None
        best_dt = 999.0
        for c_cand in outgoing_candidates:
            ce = float(c_cand.get("out_end_sec") or 0.0)
            dt = abs(ce - mid_t)
            if dt < best_dt and dt <= 0.45:
                best_dt = dt
                out_cut = c_cand
        tr_out = str((out_cut or {}).get("transition_out") or "").strip().lower()
        if tr_out == "action_impact_cut":
            cue_name = "thud"
        elif tr_out in ("whip_pan_blur_8f", "portal_crash_zoom_10f", "occlusion_wipe", "seamless_relay_cut") or bool(EXPRESSIVE_V8_SYNTH_TONAL_FOLEY):
            cue_name = "whoosh"
        else:
            continue
        dur_cue = min(avail, 0.13)
        oneshot = _synthesize_v8_foley_oneshot(cue_name, dur_cue, sr, rng) * foley_peak
        s0 = max(0, int(round((mid_t - 0.5 * dur_cue) * sr)))
        s1 = min(n_samples, s0 + oneshot.shape[0])
        if s1 > s0:
            amb_st[s0:s1, :] += oneshot[: s1 - s0, :]
            placed_foley.append({"time_sec": round(s0 / float(sr), 3), "cue": cue_name, "duration_sec": round((s1 - s0) / float(sr), 3)})

    # Rule R74: Subtle -21 dBFS bandpass (160-850 Hz) velvet air-glass portal whoosh (0.36s) on neural & portal dives
    from pipeline.config import (
        NEURAL_WHOOSH_BAND_HZ,
        NEURAL_WHOOSH_DURATION_SEC,
        NEURAL_WHOOSH_GAIN_DB,
    )

    neural_whoosh_events: list[dict[str, Any]] = []
    whoosh_moves = {
        "neural_fpv_dive_in",
        "neural_fpv_pullback_out",
        "neural_tract_relay_flight",
        "fpv_window_portal_breach",
    }
    w_len = max(64, int(round(float(NEURAL_WHOOSH_DURATION_SEC) * sr)))
    w_peak = float(10.0 ** (float(NEURAL_WHOOSH_GAIN_DB) / 20.0))
    cuts_for_whoosh = edl.get("cuts") if isinstance(edl.get("cuts"), list) else []
    for c_w in cuts_for_whoosh:
        if not isinstance(c_w, dict):
            continue
        cm_w = str(c_w.get("camera_move") or c_w.get("camera") or "").strip().lower()
        if cm_w not in whoosh_moves:
            continue
        t_w = max(0.0, float(c_w.get("out_start_sec") or 0.0))
        s0_w = max(0, int(round(t_w * sr)))
        s1_w = min(n_samples, s0_w + w_len)
        if s1_w - s0_w < 32:
            continue
        seg_n = s1_w - s0_w
        wn = rng.standard_normal(seg_n).astype(np.float64)
        freqs = np.fft.rfftfreq(seg_n, d=1.0 / float(sr))
        lo_hz, hi_hz = float(NEURAL_WHOOSH_BAND_HZ[0]), float(NEURAL_WHOOSH_BAND_HZ[1])
        spec_w = np.fft.rfft(wn)
        bp_mask = np.exp(-0.5 * ((np.maximum(0.0, lo_hz - freqs) / 45.0) ** 2)) * np.exp(
            -0.5 * ((np.maximum(0.0, freqs - hi_hz) / 180.0) ** 2)
        )
        velvet_mono = np.fft.irfft(spec_w * bp_mask, n=seg_n)
        t_axis = np.linspace(0.0, float(seg_n) / float(sr), seg_n, endpoint=False)
        chime_sub = 0.22 * np.sin(2.0 * math.pi * (420.0 if cm_w != "neural_fpv_pullback_out" else 340.0) * t_axis)
        raw_velvet = (velvet_mono / max(1e-6, float(np.max(np.abs(velvet_mono))))) * 0.78 + chime_sub
        env_w = np.hanning(seg_n)
        pan_l = np.linspace(0.92, 0.68, seg_n) if cm_w != "neural_fpv_pullback_out" else np.linspace(0.68, 0.92, seg_n)
        pan_r = np.linspace(0.68, 0.92, seg_n) if cm_w != "neural_fpv_pullback_out" else np.linspace(0.92, 0.68, seg_n)
        whoosh_st = np.column_stack([raw_velvet * env_w * pan_l, raw_velvet * env_w * pan_r]).astype(np.float32)
        mx_w = float(np.max(np.abs(whoosh_st)))
        if mx_w > 1e-6:
            whoosh_st = whoosh_st * (w_peak / mx_w)
        amb_st[s0_w:s1_w, :] += whoosh_st
        neural_whoosh_events.append(
            {
                "cut_index": c_w.get("cut_index"),
                "camera_move": cm_w,
                "time_sec": round(s0_w / float(sr), 3),
                "duration_sec": round(seg_n / float(sr), 3),
                "gain_dbfs": float(NEURAL_WHOOSH_GAIN_DB),
            }
        )

    edl["neural_whoosh_events"] = neural_whoosh_events
    edl["bgm_profile"] = str(bgm_meta.get("bgm_source") or bgm_mode)
    edl["bgm_mood"] = bgm_mood
    edl["bgm_model_id"] = bgm_meta.get("model_id")
    edl["bgm_file"] = bgm_meta.get("bgm_file")
    edl["bgm_start_dbfs"] = float(EXPRESSIVE_V8_BGM_DUCK_DB)
    edl["bgm_peak_dbfs"] = float(EXPRESSIVE_V8_BGM_BREATH_DB)
    edl["bgm_end_dbfs"] = float(EXPRESSIVE_V8_BGM_DUCK_DB)
    edl["bgm_tail_dbfs"] = float(EXPRESSIVE_V8_BGM_TAIL_DBFS)
    edl["bgm_melodic_ratio"] = 1.0
    edl["room_ambience_dbfs"] = float(EXPRESSIVE_V8_ROOM_TONE_DBFS)
    edl["foley_events_synthesized"] = len(placed_foley)
    edl["placed_foley"] = placed_foley
    return amb_st


def generate_diorama_audio_master(
    wav_path: Path,
    voice_pcm: np.ndarray,
    sr: int,
    speech_end_sec: float,
    edl: dict[str, Any],
) -> Path:
    """Mixes master voiceover + documentary score (or v8 room ambience + foley) and normalizes to target LUFS."""
    from pipeline.config import EXPRESSIVE_V8_TARGET_LUFS, is_expressive_v8_plan

    wav_path = Path(wav_path)
    wav_path.parent.mkdir(parents=True, exist_ok=True)
    n_samples = len(voice_pcm)
    is_v8 = is_expressive_v8_plan(edl)
    is_v7 = is_v8 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7

    if is_v7:
        stereo_bgm = (
            _synthesize_expressive_v8_ambience_and_foley(n_samples, sr, speech_end_sec, edl)
            if is_v8
            else _synthesize_stereo_orchestral_bgm(n_samples, sr, speech_end_sec, edl)
        )
        target_lufs = float(EXPRESSIVE_V8_TARGET_LUFS if is_v8 else DIORAMA_TARGET_LUFS)
        tp_target = -1.6 if is_v8 else -1.8
        lim_ceil = 0.831 if is_v8 else 0.812
        voice_mono = voice_pcm.astype(np.float32).reshape(-1)
        voice_st = np.column_stack([voice_mono, voice_mono])
        raw_sum = voice_st + stereo_bgm
        peak_raw = float(np.max(np.abs(raw_sum))) if raw_sum.size else 0.0
        # Stage unclipped 16-bit PCM with clean headroom before 2-pass EBU R128 linear normalization
        pre_scale = min(0.78, 0.92 / peak_raw) if peak_raw > 1e-5 else 0.78
        mixed_st = (raw_sum * pre_scale).astype(np.float32)
        with ram_tempdir(prefix="aab_diorama_mix_v7_") as td:
            td_p = Path(td)
            raw_wav = td_p / "raw_mix_st.wav"
            norm_wav = td_p / "norm_mix_st.wav"
            out_wav_tmp = td_p / "audio_master_st.wav"
            _write_stereo_wav(raw_wav, mixed_st, sr)
            # Pass 1: Measure integrated loudness & LRA so Schema v7/v8 uses pure constant scalar linear gain
            # rather than FFmpeg single-pass loudnorm's 3-second sliding-window dynamic AGC gain-rider.
            af = (
                f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5,"
                f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
            )
            res_p1 = subprocess.run(
                [
                    _ffmpeg(), "-nostdin", "-hide_banner", "-y",
                    "-i", str(raw_wav),
                    "-af", f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5:print_format=json",
                    "-f", "null", "-",
                ],
                capture_output=True, text=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
            )
            m_json = re.search(r"\{\s*\"input_i\"[\s\S]*?\}", res_p1.stderr or "")
            if m_json:
                try:
                    ln_stats = json.loads(m_json.group(0))
                    meas_i = float(ln_stats["input_i"])
                    meas_lra = float(ln_stats["input_lra"])
                    meas_tp = float(ln_stats["input_tp"])
                    meas_thresh = float(ln_stats["input_thresh"])
                    meas_offset = float(ln_stats["target_offset"])
                    if math.isfinite(meas_i) and meas_i > -70.0:
                        if meas_lra <= 8.5:
                            gain_db = max(-24.0, min(24.0, target_lufs - meas_i))
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"volume={gain_db:.4f}dB,alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
                            )
                        elif math.isfinite(meas_tp) and math.isfinite(meas_thresh) and math.isfinite(meas_offset):
                            af = (
                                f"{_cfg.DIORAMA_V7_MASTER_DEESSER},"
                                f"loudnorm=I={target_lufs}:TP={tp_target}:LRA=8.5"
                                f":measured_I={meas_i:.2f}:measured_TP={meas_tp:.2f}"
                                f":measured_LRA={meas_lra:.2f}:measured_thresh={meas_thresh:.2f}"
                                f":offset={meas_offset:.2f}:linear=true,"
                                f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled"
                            )
                except (KeyError, TypeError, ValueError, json.JSONDecodeError):
                    pass
            res = subprocess.run(
                [
                    _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-i", str(raw_wav), "-af", af, "-ar", str(sr), "-ac", str(DIORAMA_V7_AUDIO_CHANNELS), str(norm_wav),
                ],
                capture_output=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
            )
            if res.returncode == 0 and norm_wav.exists():
                with wave.open(str(norm_wav), "rb") as wf:
                    n_ch = max(1, wf.getnchannels())
                    raw_bytes = wf.readframes(wf.getnframes())
                raw_arr = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
                if n_ch >= 2:
                    pcm_st = raw_arr[: (len(raw_arr) // n_ch) * n_ch].reshape(-1, n_ch)[:, :2]
                else:
                    pcm_st = np.column_stack([raw_arr, raw_arr])
                if pcm_st.shape[0] >= n_samples:
                    pcm_st = pcm_st[:n_samples, :].copy()
                else:
                    pad_rows = n_samples - pcm_st.shape[0]
                    pcm_st = np.pad(pcm_st, ((0, pad_rows), (0, 0))).astype(np.float32)
            else:
                pcm_st = np.clip(raw_sum * 0.84, -lim_ceil, lim_ceil).astype(np.float32)
            mute_n = min(pcm_st.shape[0], int(0.095 * sr))
            if mute_n > 0:
                env_tail = np.linspace(1.0, 0.0, mute_n, dtype=np.float32)[:, None]
                pcm_st[-mute_n:, :] *= env_tail
            _write_stereo_wav(out_wav_tmp, pcm_st, sr)
            atomic_commit_from_scratch(out_wav_tmp, wav_path)
        return wav_path

    accompaniment = _synthesize_documentary_pulse_bgm(n_samples, sr, speech_end_sec, edl)
    mixed = np.clip(voice_pcm.astype(np.float32) + accompaniment, -0.96, 0.96)

    with ram_tempdir(prefix="aab_diorama_mix_") as td:
        td_p = Path(td)
        raw_wav = td_p / "raw_mix.wav"
        norm_wav = td_p / "norm_mix.wav"
        out_wav_tmp = td_p / "audio_master_mono.wav"
        _write_mono_wav(raw_wav, mixed, sr)
        af = (
            f"loudnorm=I={DIORAMA_TARGET_LUFS}:TP=-2.2:LRA=4.0,"
            "alimiter=limit=0.776:attack=5:release=50:level=disabled"
        )
        res = subprocess.run(
            [
                _ffmpeg(), "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(raw_wav), "-af", af, "-ar", str(sr), "-ac", "1", str(norm_wav),
            ],
            capture_output=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
        )
        if res.returncode == 0 and norm_wav.exists():
            # Ensure exact sample count matches video frame duration + clean 95ms tail mute
            with wave.open(str(norm_wav), "rb") as wf:
                raw_bytes = wf.readframes(wf.getnframes())
            pcm_out = np.frombuffer(raw_bytes, dtype=np.int16).astype(np.float32) / 32767.0
            if len(pcm_out) >= n_samples:
                pcm_out = pcm_out[:n_samples].copy()
            else:
                pcm_out = np.pad(pcm_out, (0, n_samples - len(pcm_out))).astype(np.float32)
        else:
            pcm_out = mixed * 0.84
        mute_n = min(len(pcm_out), int(0.095 * sr))
        if mute_n > 0:
            pcm_out[-mute_n:] *= np.linspace(1.0, 0.0, mute_n, dtype=np.float32)
        _write_mono_wav(out_wav_tmp, pcm_out, sr)
        atomic_commit_from_scratch(out_wav_tmp, wav_path)
    return wav_path


def _measure_true_peak_dbtp(path: Path) -> float | None:
    """4x-oversampled BS.1770 true peak (dBTP) of the first audio stream via FFmpeg `ebur128=peak=true`."""
    try:
        res = subprocess.run(
            [_ffmpeg(), "-nostdin", "-hide_banner", "-i", str(path), "-map", "0:a:0", "-af", "ebur128=peak=true", "-f", "null", "-"],
            capture_output=True, text=True, check=False, timeout=180, stdin=subprocess.DEVNULL,
        )
        m = re.findall(r"Peak:\s*(-?[\d.]+|-inf)\s*dBFS", res.stderr or "")
        if not m or m[-1] == "-inf":
            return None
        return float(m[-1])
    except Exception:  # noqa: BLE001
        return None

