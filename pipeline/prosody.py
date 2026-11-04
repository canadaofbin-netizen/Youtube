"""
ALL ABOUT BRAIN - Sentence-level Prosody Engine (R63-P).

Three gears applied after a single edge-tts synthesis pass (timbre stays identical):
  - rush  : breathless delivery for hooks / climax beats (tight internal trims, ~0 inter-sentence gap)
  - stamp : a deliberate one-beat pause, then a clear declarative line (case stamp, signature hooks)
  - brisk : fast exposition (setup, experiment rules, anatomy glosses)

Also hosts the Prosody QA gates P1-P10 used by `main.py prosody-qa`.
"""

from __future__ import annotations

import json
import re
from difflib import SequenceMatcher
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    DIORAMA_V7_PROSODY_ACT_GAP_MIN,
    DIORAMA_V7_PROSODY_BASE_RATE,
    DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB,
    DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC,
    DIORAMA_V7_PROSODY_GEAR_RATES,
    DIORAMA_V7_PROSODY_GEARS,
    DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP,
    DIORAMA_V7_PROSODY_MODE,
    DIORAMA_V7_PROSODY_MODES,
    DIORAMA_V7_PROSODY_REHOOK_PHRASES,
    DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS,
    DIORAMA_V7_PROSODY_RUSH_MAX_STREAK,
    DIORAMA_V7_PROSODY_SPLICE_FADE_SEC,
    DIORAMA_V7_PROSODY_STAMP_PHRASES,
    DIORAMA_V7_PROSODY_UNIFORM_110,
    DIORAMA_V7_PROSODY_UNIFORM_110_RATE,
    DIORAMA_V7_US_PROSODY_BASE_RATE,
    DIORAMA_V7_US_PROSODY_GEAR_RATES,
    DIORAMA_V7_US_PROSODY_GEARS,
    DIORAMA_V7_US_PROSODY_MODE,
    PROSODY_P1_FIRST_ONSET_MAX_SEC,
    PROSODY_P2_HOOK_END_MAX_SEC,
    PROSODY_P2_STAMP_END_MAX_SEC,
    PROSODY_P3_TEMPO_TOLERANCE,
    PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC,
    PROSODY_P5_STAMP_PRE_SILENCE_RANGE,
    PROSODY_P6_ASR_MATCH_MIN,
    PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC,
)

GEARS: tuple[str, ...] = ("rush", "stamp", "brisk")
DYNAMIC_PROSODY_MODES: tuple[str, ...] = ("dynamic_rush_v7", DIORAMA_V7_US_PROSODY_MODE)


def _rate_to_speed(rate: str) -> float:
    m = re.fullmatch(r"\s*([+-]?\d+(?:\.\d+)?)%\s*", str(rate or ""))
    return round(1.0 + float(m.group(1)) / 100.0, 4) if m else 1.0


def _speed_to_rate(speed: float) -> str:
    """Nearest integer-percent edge-tts rate string for a tempo multiplier (1.12 -> "+12%")."""
    pct = int(round((float(speed) - 1.0) * 100.0))
    return f"{pct:+d}%"


def rate_to_speed(rate: str) -> float:
    """Public alias: edge-tts rate string -> tempo multiplier ("+15%" -> 1.15)."""
    return _rate_to_speed(rate)


def resolve_prosody_mode(explicit: str | None, script_doc: dict[str, Any] | None, v7_mode: bool) -> str:
    """explicit arg > script.json `prosody_mode` > channel default. Non-v7 projects always stay legacy."""
    if not v7_mode:
        return "uniform_108x"
    cand = str(explicit or (script_doc or {}).get("prosody_mode") or DIORAMA_V7_PROSODY_MODE).strip().lower()
    return cand if cand in DIORAMA_V7_PROSODY_MODES else DIORAMA_V7_PROSODY_MODE


def base_rate_for_mode(mode: str) -> str | None:
    """edge-tts rate used for synthesis (None = keep the legacy resolution chain)."""
    if mode == "uniform_110x":
        return DIORAMA_V7_PROSODY_UNIFORM_110_RATE
    if mode == "dynamic_rush_v7":
        return DIORAMA_V7_PROSODY_BASE_RATE
    if mode == DIORAMA_V7_US_PROSODY_MODE:
        return DIORAMA_V7_US_PROSODY_BASE_RATE
    return None


def _act_boundary_after(script_doc: dict[str, Any] | None, n: int) -> set[int]:
    out: set[int] = set()
    acts = (script_doc or {}).get("acts") if isinstance((script_doc or {}).get("acts"), list) else []
    running = 0
    for a_i, act in enumerate(acts):
        cnt = sum(1 for x in ((act or {}).get("sentences") or []) if str(x).strip()) if isinstance(act, dict) else 0
        running += cnt
        if cnt and a_i < len(acts) - 1 and 1 <= running < n:
            out.add(running)
    return out


def _act_of_sentence(script_doc: dict[str, Any] | None, n: int) -> dict[int, int]:
    mapping: dict[int, int] = {}
    acts = (script_doc or {}).get("acts") if isinstance((script_doc or {}).get("acts"), list) else []
    cur = 1
    for a_i, act in enumerate(acts, start=1):
        for x in ((act or {}).get("sentences") or []) if isinstance(act, dict) else []:
            if str(x).strip() and cur <= n:
                mapping[cur] = a_i
                cur += 1
    for i in range(1, n + 1):
        mapping.setdefault(i, 1)
    return mapping


def classify_prosody_gears(sentences: list[str], script_doc: dict[str, Any] | None = None) -> list[str]:
    """
    Gear per sentence (1:1 with `sentences`):
      1. manual `script_doc["prosody_gears"][i]` (or {"<1-based>": gear} dict)
      2. stamp: `stamp_sentence_indices`, rotating natural transition banks, Act-boundary questions
      3. rush : sentences 1-2, sentences ending with '!', Act 5 lines with yet/then/suddenly/instead
      4. brisk: everything else
    A run of more than DIORAMA_V7_PROSODY_RUSH_MAX_STREAK automatic rush sentences demotes the extra one to brisk.
    """
    n = len(sentences)
    manual_raw = (script_doc or {}).get("prosody_gears")
    manual: dict[int, str] = {}
    if isinstance(manual_raw, list):
        manual = {i + 1: str(g).strip().lower() for i, g in enumerate(manual_raw) if str(g).strip().lower() in GEARS}
    elif isinstance(manual_raw, dict):
        for k, g in manual_raw.items():
            try:
                if str(g).strip().lower() in GEARS:
                    manual[int(k)] = str(g).strip().lower()
            except (TypeError, ValueError):
                continue
    explicit_stamps: set[int] = set()
    for raw_idx in (script_doc or {}).get("stamp_sentence_indices") or []:
        try:
            explicit_stamps.add(int(raw_idx))
        except (TypeError, ValueError):
            continue
    act_breaks = _act_boundary_after(script_doc, n)
    act_of = _act_of_sentence(script_doc, n)
    gears: list[str] = []
    auto_rush_streak = 0
    for i, raw in enumerate(sentences, start=1):
        s = str(raw or "").strip()
        low = s.lower()
        if i in manual:
            g = manual[i]
            auto_rush_streak = auto_rush_streak + 1 if g == "rush" else 0
            gears.append(g)
            continue
        is_boundary_q = s.endswith("?") and ((i in act_breaks) or (i - 1 in act_breaks) or (i + 1 in act_breaks))
        if i in explicit_stamps or any(p in low for p in DIORAMA_V7_PROSODY_STAMP_PHRASES) or is_boundary_q:
            g = "stamp"
        elif (
            i <= 2
            or s.endswith("!")
            or (act_of.get(i) == 5 and re.search(rf"\b(?:{'|'.join(DIORAMA_V7_PROSODY_RUSH_CLIMAX_WORDS)})\b", low))
        ):
            g = "rush"
        else:
            g = "brisk"
        if g == "rush":
            auto_rush_streak += 1
            if auto_rush_streak > DIORAMA_V7_PROSODY_RUSH_MAX_STREAK:
                g = "brisk"
                auto_rush_streak = 0
        else:
            auto_rush_streak = 0
        gears.append(g)
    return gears


def plan_sentence_prosody(
    sentences: list[str],
    script_doc: dict[str, Any] | None,
    mode: str,
) -> list[dict[str, Any]]:
    """
    Per-sentence plan: gear, trim thresholds, inserted gap BEFORE the sentence, the native edge-tts `synth_rate`
    the sentence is synthesized at, and the residual WSOLA factor on top of that rate.

    `dynamic_rush_v7` (+12/+8/+15%) and `dynamic_us_v7` (+10/+4/+7%) synthesize every gear natively, so `wsola_factor`
    is 1.0 unless the adjacent-tempo clamp lands between integer-percent rates (residual < 0.5%).
    `base_wsola_factor` keeps the legacy single-pass factor (target / base rate) for the atempo fallback path.
    """
    n = len(sentences)
    act_breaks = _act_boundary_after(script_doc, n)
    is_dynamic = mode in DYNAMIC_PROSODY_MODES
    gears = classify_prosody_gears(sentences, script_doc) if is_dynamic else [
        ("stamp" if any(p in str(s).lower() for p in DIORAMA_V7_PROSODY_STAMP_PHRASES) else "brisk") for s in sentences
    ]
    active_base_rate = DIORAMA_V7_US_PROSODY_BASE_RATE if mode == DIORAMA_V7_US_PROSODY_MODE else DIORAMA_V7_PROSODY_BASE_RATE
    active_gears_spec = DIORAMA_V7_US_PROSODY_GEARS if mode == DIORAMA_V7_US_PROSODY_MODE else DIORAMA_V7_PROSODY_GEARS
    active_gear_rates = DIORAMA_V7_US_PROSODY_GEAR_RATES if mode == DIORAMA_V7_US_PROSODY_MODE else DIORAMA_V7_PROSODY_GEAR_RATES
    base_speed = _rate_to_speed(active_base_rate)
    plan: list[dict[str, Any]] = []
    prev_factor = 1.0
    for i, g in enumerate(gears, start=1):
        after_act_break = (i - 1) in act_breaks
        if is_dynamic:
            spec = active_gears_spec[g]
            factor = round(float(spec["tempo"]) / base_speed, 4)
            gap = float(spec["gap_before"])
            if after_act_break:
                gap = max(gap, DIORAMA_V7_PROSODY_ACT_GAP_MIN)
            clamped = False
            if i > 1 and gap < 0.10 and abs(factor - prev_factor) > DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP:
                factor = round(prev_factor + DIORAMA_V7_PROSODY_MAX_ADJ_TEMPO_JUMP * (1 if factor > prev_factor else -1), 4)
                clamped = True
            trim_thresh, trim_keep = float(spec["trim_thresh"]), float(spec["trim_keep"])
            target_tempo = round(base_speed * factor, 4)
            synth_rate = active_gear_rates.get(g) if not clamped else None
            if not synth_rate or abs(_rate_to_speed(synth_rate) - target_tempo) > 0.005:
                synth_rate = _speed_to_rate(target_tempo)
        else:  # uniform_110x / uniform_108x
            spec_u = DIORAMA_V7_PROSODY_UNIFORM_110
            factor, clamped = 1.0, False
            gap = float(spec_u["stamp_gap_before"] if g == "stamp" else spec_u["gap_before"])
            if after_act_break:
                gap = max(gap, float(spec_u["act_gap_before"]))
            trim_thresh, trim_keep = float(spec_u["trim_thresh"]), float(spec_u["trim_keep"])
            target_tempo = _rate_to_speed(DIORAMA_V7_PROSODY_UNIFORM_110_RATE)
            synth_rate = DIORAMA_V7_PROSODY_UNIFORM_110_RATE
        residual = round(target_tempo / _rate_to_speed(synth_rate), 4)
        plan.append(
            {
                "sentence_index": i,
                "gear": g,
                "synth_rate": synth_rate,
                "wsola_factor": residual if abs(residual - 1.0) >= 0.006 else 1.0,  # <0.6% residual: skip WSOLA (P3 tol 3%)
                "base_wsola_factor": factor,
                "target_tempo": target_tempo,
                "tempo_clamped": clamped,
                "gap_before_sec": round(0.0 if i == 1 else gap, 3),
                "trim_thresh_sec": trim_thresh,
                "trim_keep_sec": trim_keep,
                "act_boundary_before": after_act_break,
            }
        )
        prev_factor = factor
    return plan


def _norm_word(w: str) -> str:
    return re.sub(r"[^a-z0-9]", "", str(w).lower())


def emphasis_words_for(script_doc: dict[str, Any] | None, sentence_index: int) -> list[str]:
    raw = (script_doc or {}).get("emphasis_words")
    if not isinstance(raw, dict):
        return []
    vals = raw.get(str(sentence_index)) or raw.get(sentence_index) or []  # type: ignore[call-overload]
    return [_norm_word(v) for v in vals if _norm_word(v)]


def apply_emphasis(
    pcm: np.ndarray,
    sr: int,
    word_list: list[tuple[float, float, str]],
    targets: list[str],
    pause_sec: float | None = None,
    gain_db: float | None = None,
) -> tuple[np.ndarray, list[tuple[float, float, str]], int]:
    """
    Applies smooth emphasis contour lift over target display words.
    When `pause_sec` (defaulting to `DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC == 0.0`) is `<= 0.0`,
    preserves 100% continuous co-articulated waveform length with a smooth 25ms raised-cosine gain lift
    (zero mid-sentence digital zero-slicing). When `pause_sec > 0.0`, inserts a cosine-faded micro-pause.
    """
    if not targets or not word_list:
        return pcm, word_list, 0
    arr = np.asarray(pcm, dtype=np.float32).copy()
    eff_gain_db = float(DIORAMA_V7_PROSODY_EMPHASIS_GAIN_DB if gain_db is None else gain_db)
    eff_pause_sec = float(DIORAMA_V7_PROSODY_EMPHASIS_PAUSE_SEC if pause_sec is None else pause_sec)
    gain = float(10.0 ** (eff_gain_db / 20.0))
    pause_n = max(0, int(round(eff_pause_sec * sr)))
    ramp_n = max(8, int((0.025 if pause_n == 0 else 0.005) * sr))
    hits = [k for k, (_, _, w) in enumerate(word_list) if _norm_word(w) in targets]
    if not hits:
        return arr, word_list, 0
    # Smooth raised-cosine gain contour (original timeline)
    for k in hits:
        t0, t1, _ = word_list[k]
        a, b = max(0, int(t0 * sr)), min(len(arr), int(t1 * sr))
        span = b - a
        if span > 16:
            r_n = min(ramp_n, span // 2)
            env = np.full(span, gain, dtype=np.float32)
            if r_n >= 2:
                up = 0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, r_n, dtype=np.float32))
                env[:r_n] = 1.0 + (gain - 1.0) * up
                env[-r_n:] = 1.0 + (gain - 1.0) * up[::-1]
            arr[a:b] *= env
    if pause_n <= 0:
        np.clip(arr, -0.98, 0.98, out=arr)
        return arr, list(word_list), len(hits)
    # Optional micro-pause insertion (back-to-front so earlier indices stay valid)
    new_words = list(word_list)
    for k in sorted(hits, reverse=True):
        t0 = new_words[k][0]
        a = int(t0 * sr)
        lo_s, hi_s = max(0, a - int(0.025 * sr)), min(len(arr), a + int(0.008 * sr))
        sub = max(8, int(0.002 * sr))
        if hi_s - lo_s > 2 * sub:
            e = np.convolve(np.square(arr[lo_s:hi_s]), np.ones(sub, dtype=np.float32), mode="valid")
            a = lo_s + int(np.argmin(e)) + sub // 2
        arr = np.concatenate([fade_edges(arr[:a], sr, fade_in=False), np.zeros(pause_n, dtype=np.float32),
                              fade_edges(arr[a:], sr, fade_out=False)])
        shift = pause_n / float(sr)
        new_words = [
            (round(w0 + shift, 3), round(w1 + shift, 3), w) if j >= k else (w0, w1, w)
            for j, (w0, w1, w) in enumerate(new_words)
        ]
    np.clip(arr, -0.98, 0.98, out=arr)
    return arr, new_words, len(hits)


def fade_edges(
    pcm: np.ndarray,
    sr: int,
    fade_sec: float | None = None,
    fade_in: bool = True,
    fade_out: bool = True,
) -> np.ndarray:
    """Raised-cosine fade-in / fade-out (`DIORAMA_V7_PROSODY_SPLICE_FADE_SEC`) so a segment starts/ends at zero."""
    arr = np.asarray(pcm, dtype=np.float32).copy()
    n = int(round(float(DIORAMA_V7_PROSODY_SPLICE_FADE_SEC if fade_sec is None else fade_sec) * sr))
    n = min(n, len(arr) // 2)
    if n < 2:
        return arr
    ramp = (0.5 - 0.5 * np.cos(np.linspace(0.0, np.pi, n, dtype=np.float32))).astype(np.float32)
    if fade_in:
        arr[:n] *= ramp
    if fade_out:
        arr[-n:] *= ramp[::-1]
    return arr


def _silence_mask(pcm: np.ndarray, sr: int) -> tuple[np.ndarray, int]:
    win = max(64, int(0.010 * sr))
    n_w = len(pcm) // win
    if n_w < 3:
        return np.zeros(0, dtype=bool), win
    framed = np.asarray(pcm[: n_w * win], dtype=np.float32).reshape(n_w, win)
    db = 20.0 * np.log10(np.sqrt(np.mean(np.square(framed), axis=1) + 1e-10))
    thresh = max(-43.0, float(np.percentile(db, 95)) - 27.5)
    return db < thresh, win


def measure_internal_max_silence(pcm: np.ndarray, sr: int) -> float:
    """Longest silent run strictly between the first and last voiced 10ms windows."""
    silent, win = _silence_mask(pcm, sr)
    if silent.size == 0 or silent.all():
        return 0.0
    voiced_idx = np.where(~silent)[0]
    inner = silent[voiced_idx[0] : voiced_idx[-1] + 1]
    best = cur = 0
    for v in inner:
        cur = cur + 1 if v else 0
        best = max(best, cur)
    return round(best * win / float(sr), 3)


def measure_edge_silences(pcm: np.ndarray, sr: int) -> tuple[float, float]:
    """(leading_silence_sec, trailing_silence_sec) of a sentence slice."""
    silent, win = _silence_mask(pcm, sr)
    if silent.size == 0 or silent.all():
        return 0.0, 0.0
    voiced_idx = np.where(~silent)[0]
    lead = voiced_idx[0] * win / float(sr)
    trail = (len(silent) - 1 - voiced_idx[-1]) * win / float(sr) + (len(pcm) - len(silent) * win) / float(sr)
    return round(lead, 3), round(trail, 3)


# ------------------------------------------------------------------------------
# Prosody QA gates P1-P10
# ------------------------------------------------------------------------------
def _resolve_project_dir(project_id_or_dir: str | Path) -> Path:
    from pipeline.config import PROJECTS_DIR

    p = Path(str(project_id_or_dir))
    return p if p.exists() else PROJECTS_DIR / str(project_id_or_dir)


def _asr_tokens(text: str) -> list[str]:
    """
    ASR-comparison tokens: hyphenated compounds split ("brand-new" -> brand, new), dotted initials joined
    ("H.M." -> hm), and a light inflection fold (juggled/juggle, tests/test, tuned/tunes) so Whisper's
    orthographic variants are not scored as mis-spoken words.
    """
    from pipeline.plain_language import to_tts_text

    t = re.sub(r"\b((?:[A-Za-z]\.){2,})", lambda m: m.group(1).replace(".", ""), str(text or ""))
    t = re.sub(r"\b(\d{1,3})((?:\s+\d{3})+)\b", lambda m: m.group(1) + m.group(2).replace(" ", ","), t)
    t = re.sub(r"\bdr\b\.?", "doctor", t, flags=re.IGNORECASE)
    t = to_tts_text(t).replace("-", " ").replace("—", " ")
    out: list[str] = []
    for raw in t.split():
        w = _norm_word(raw)
        if not w:
            continue
        if len(w) > 3:
            w = re.sub(r"(?:es|ed|s|d|e)$", "", w)
            w = re.sub(r"ss$", "s", w)
        out.append(w)
    # join runs of single letters left over from spaced initials ("h m" -> "hm")
    joined: list[str] = []
    prev_single = False
    for w in out:
        if len(w) == 1 and prev_single and joined:
            joined[-1] += w
        else:
            joined.append(w)
            prev_single = len(w) == 1
    return joined


DEFAULT_AUDIO_PROSODY_GATES: tuple[str, ...] = (
    "P1_first_onset",
    "P2_hook_timing",
    "P3_gear_tempo",
    "P4_rush_breathless",
    "P5_stamp_beat",
    "P6_asr_by_gear",
    "P8_runtime_density",
    "P10_open_loop_spacing",
)

_PROSODY_GATE_ALIASES: dict[str, str] = {
    "P1": "P1_first_onset",
    "P2": "P2_hook_timing",
    "P3": "P3_gear_tempo",
    "P4": "P4_rush_breathless",
    "P5": "P5_stamp_beat",
    "P6": "P6_asr_by_gear",
    "P7": "P7_audio_integrity",
    "P8": "P8_runtime_density",
    "P9": "P9_font_resolution",
    "P10": "P10_open_loop_spacing",
}


def _normalize_gate_names(gates: tuple[str, ...] | list[str] | None) -> list[str] | None:
    if gates is None:
        return None
    out: list[str] = []
    for g in gates:
        key = str(g).strip()
        resolved = _PROSODY_GATE_ALIASES.get(key.upper(), key)
        if resolved and resolved not in out:
            out.append(resolved)
    return out


def _asr_match_by_sentence(media_path: Path, spans: list[dict[str, Any]]) -> dict[int, float]:
    from pipeline.media_cache import cached_asr_word_timeline

    words = cached_asr_word_timeline(Path(media_path))
    out: dict[int, float] = {}
    for sp in spans:
        s0, s1 = float(sp["start_sec"]) - 0.15, float(sp["end_sec"]) + 0.15
        heard = _asr_tokens(" ".join(w for (a, b, w) in words if s0 <= 0.5 * (a + b) <= s1))
        ref = _asr_tokens(str(sp.get("text") or ""))
        if not ref:
            continue
        sm = SequenceMatcher(a=ref, b=heard, autojunk=False)
        out[int(sp["sentence_index"])] = round(sum(b.size for b in sm.get_matching_blocks()) / float(len(ref)), 4)
    return out


def _compute_core_prosody_gates(
    p_dir: Path,
    *,
    asr_media_path: Path | None,
    run_asr: bool = True,
    include_mp4_post_gates: bool = True,
) -> tuple[str | None, dict[str, dict[str, Any]]]:
    from pipeline.config import (
        DIORAMA_DURATION_MAX_SEC,
        DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN,
        DIORAMA_V7_DURATION_MIN_SEC,
        DIORAMA_V7_WPM_MAX,
    )

    pr = json.loads((p_dir / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
    vr = json.loads((p_dir / "04_audio" / "voice_report.json").read_text(encoding="utf-8"))
    spans = vr.get("sentence_spans") or []
    sents = pr.get("sentences") or []
    mode = pr.get("prosody_mode")
    gates: dict[str, dict[str, Any]] = {}

    first_onset = float(spans[0]["start_sec"]) + float((sents[0] if sents else {}).get("lead_silence_sec") or 0.0) if spans else 99.0
    gates["P1_first_onset"] = {"passed": first_onset <= PROSODY_P1_FIRST_ONSET_MAX_SEC, "first_onset_sec": round(first_onset, 3)}

    s2_end = float(spans[1]["end_sec"]) if len(spans) >= 2 else 99.0
    p2: dict[str, Any] = {"s2_end_sec": s2_end, "passed": s2_end <= PROSODY_P2_HOOK_END_MAX_SEC}
    if len(sents) >= 3 and sents[2].get("gear") == "stamp" and len(spans) >= 3:
        p2["s3_end_sec"] = float(spans[2]["end_sec"])
        p2["passed"] = p2["passed"] and p2["s3_end_sec"] <= PROSODY_P2_STAMP_END_MAX_SEC
    gates["P2_hook_timing"] = p2

    raw_engine = str(vr.get("engine") or "edge_tts").strip().lower()
    engine_ok = raw_engine in ("edge_tts", "edge-tts")
    tempo_bad = [
        s["sentence_index"]
        for s in sents
        if s.get("measured_tempo") and abs(float(s["measured_tempo"]) / float(s["target_tempo"]) - 1.0) > PROSODY_P3_TEMPO_TOLERANCE
    ]
    is_dyn = mode in DYNAMIC_PROSODY_MODES
    wsola_fallback_sents = [
        s["sentence_index"]
        for s in sents
        if is_dyn and not s.get("tempo_clamped") and (not bool(s.get("native_gear_synth", True)) or abs(float(s.get("wsola_factor", 1.0)) - 1.0) > 0.035)
    ]
    gear_wpm: dict[str, float] = {}
    gear_wps: dict[str, float] = {}
    span_by_idx = {int(sp.get("sentence_index") or i + 1): sp for i, sp in enumerate(spans)}
    for g in GEARS:
        g_sents = [s for s in sents if s.get("gear") == g]
        vals = [float(s["wpm"]) for s in g_sents if s.get("wpm")]
        if vals:
            gear_wpm[g] = round(float(np.median(vals)), 1)
        tot_w = 0
        tot_d = 0.0
        for s in g_sents:
            sp_item = span_by_idx.get(int(s.get("sentence_index") or 0))
            w_cnt = int(s.get("words") or (len(str((sp_item or {}).get("text") or "").split())))
            if sp_item and sp_item.get("end_sec") is not None and sp_item.get("start_sec") is not None:
                d_sec = max(0.05, float(sp_item["end_sec"]) - float(sp_item["start_sec"]))
            else:
                d_sec = max(0.05, float(s.get("duration_sec") or 0.0) - float(s.get("lead_silence_sec") or 0.0) - float(s.get("trail_silence_sec") or 0.0))
            if w_cnt > 0 and d_sec > 0.05:
                tot_w += w_cnt
                tot_d += d_sec
        if tot_d > 0.05:
            gear_wps[g] = round(tot_w / tot_d, 3)
    acoustic_wps_ok = all(1.4 <= v <= 4.5 for v in gear_wps.values()) if gear_wps else True
    dyn_spread_ok = True
    if is_dyn and len(gear_wps) >= 2:
        wps_spread = max(gear_wps.values()) - min(gear_wps.values())
        wpm_spread = (max(gear_wpm.values()) - min(gear_wpm.values())) if len(gear_wpm) >= 2 else 0.0
        dyn_spread_ok = (wps_spread >= 0.04) or (wpm_spread >= 3.0)
    native_gear_ok = (not is_dyn) or (bool(pr.get("native_gear_synthesis", True)) and not wsola_fallback_sents)
    gates["P3_gear_tempo"] = {
        "passed": bool(engine_ok and not tempo_bad and native_gear_ok and acoustic_wps_ok and dyn_spread_ok),
        "engine": vr.get("engine") or "edge_tts",
        "engine_ok": engine_ok,
        "native_gear_ok": native_gear_ok,
        "wsola_fallback_sentences": wsola_fallback_sents,
        "off_target_sentences": tempo_bad,
        "median_wpm_by_gear": gear_wpm,
        "words_per_sec_by_gear": gear_wps,
    }

    rush_bad = [
        {"sentence_index": s["sentence_index"], "max_internal_silence_sec": s["max_internal_silence_sec"]}
        for s in sents
        if s.get("gear") == "rush" and float(s.get("max_internal_silence_sec") or 0.0) > PROSODY_P4_RUSH_MAX_INTERNAL_SILENCE_SEC
    ]
    is_dyn = mode in DYNAMIC_PROSODY_MODES
    gates["P4_rush_breathless"] = {"passed": (not rush_bad) or not is_dyn, "violations": rush_bad, "applies": is_dyn}

    lo, hi = PROSODY_P5_STAMP_PRE_SILENCE_RANGE
    stamp_bad = [
        {"sentence_index": s["sentence_index"], "acoustic_pre_silence_sec": s.get("acoustic_pre_silence_sec")}
        for s in sents
        if s.get("gear") == "stamp" and s["sentence_index"] > 1 and not s.get("act_boundary_before")
        and not (lo <= float(s.get("acoustic_pre_silence_sec") or 0.0) <= hi)
    ]
    gates["P5_stamp_beat"] = {"passed": not stamp_bad, "violations": stamp_bad}

    if run_asr and asr_media_path is not None and asr_media_path.exists():
        match = _asr_match_by_sentence(asr_media_path, spans)
        by_gear: dict[str, float] = {}
        for g in GEARS:
            idxs = [s["sentence_index"] for s in sents if s.get("gear") == g and s["sentence_index"] in match]
            if idxs:
                by_gear[g] = round(float(np.mean([match[i] for i in idxs])), 4)
        low_s = sorted(i for i, v in match.items() if v < 0.80)
        low_detail = {str(i): match[i] for i in low_s}
        gates["P6_asr_by_gear"] = {
            "passed": bool(by_gear) and all(v >= PROSODY_P6_ASR_MATCH_MIN for v in by_gear.values()),
            "match_by_gear": by_gear,
            "low_sentences_lt_0_80": low_s,
            "low_sentence_scores": low_detail,
        }
    else:
        gates["P6_asr_by_gear"] = {"passed": False, "skipped": True, "reason": "target audio/mp4 missing or ASR disabled"}

    total = float(vr.get("total_duration_sec") or 0.0)
    speech_end = float(vr.get("speech_end_sec") or 1.0)

    if include_mp4_post_gates:
        final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        aut_p = p_dir / "05_assembly" / "video_autopsy_report.json"
        if not aut_p.exists():
            aut_p = p_dir / "05_assembly" / "autopsy_report.json"
        a_s: dict[str, Any] | None = None
        if aut_p.exists() and (not final_mp4.exists() or aut_p.stat().st_mtime >= final_mp4.stat().st_mtime - 1.0):
            aut = json.loads(aut_p.read_text(encoding="utf-8"))
            a_s = aut.get("audio_stream") or {}
        elif final_mp4.exists():
            from pipeline.video_autopsy import VideoAutopsyEngine

            a_s = VideoAutopsyEngine.inspect_audio_stream(final_mp4, expected_duration_sec=max(1.0, total))
        if a_s:
            lufs = float(a_s.get("integrated_lufs") if a_s.get("integrated_lufs") is not None else -99)
            tp = float(a_s.get("true_peak_dbtp") if a_s.get("true_peak_dbtp") is not None else 0)
            gates["P7_audio_integrity"] = {
                "passed": (not a_s.get("sibilance_tear_detected")) and abs(lufs + 15.5) <= 0.5 and tp <= -1.5,
                "integrated_lufs": lufs,
                "true_peak_dbtp": tp,
                "sibilance_tear_detected": a_s.get("sibilance_tear_detected"),
            }
        else:
            gates["P7_audio_integrity"] = {"passed": False, "skipped": True, "reason": "autopsy_report.json missing"}

    n_words = sum(len(str(s.get("text") or "").split()) for s in spans)
    wpm = round(n_words / max(0.1, speech_end / 60.0), 1)
    voiced = float(vr.get("true_rms_voiced_ratio") or 0.0)
    gates["P8_runtime_density"] = {
        "passed": DIORAMA_V7_DURATION_MIN_SEC <= total <= min(179.0, DIORAMA_DURATION_MAX_SEC)
        and wpm <= DIORAMA_V7_WPM_MAX
        and voiced >= DIORAMA_V7_ACTIVE_VOICED_RMS_RATIO_MIN,
        "total_duration_sec": total,
        "wpm": wpm,
        "true_rms_voiced_ratio": voiced,
    }

    if include_mp4_post_gates:
        fp = p_dir / "05_assembly" / "font_probe.json"
        if fp.exists():
            fpd = json.loads(fp.read_text(encoding="utf-8"))
            gates["P9_font_resolution"] = {"passed": bool(fpd.get("passed")), "fallbacks": fpd.get("fallbacks", [])}
        else:
            gates["P9_font_resolution"] = {"passed": False, "skipped": True, "reason": "font_probe.json missing"}

    rehook_indices: set[int] = set()
    script_p = p_dir / "02_script" / "script.json"
    if script_p.exists():
        try:
            sdoc = json.loads(script_p.read_text(encoding="utf-8"))
            for r_idx in sdoc.get("rehook_sentence_indices") or []:
                rehook_indices.add(int(r_idx))
        except Exception:
            pass
    markers = [0.0]
    for sp, s in zip(spans, sents or [{}] * len(spans)):
        txt = str(sp.get("text") or "")
        low = txt.lower()
        s_idx = int(sp.get("sentence_index") or 0)
        if (
            txt.strip().endswith("?")
            or s.get("gear") == "stamp"
            or s_idx in rehook_indices
            or any(p in low for p in DIORAMA_V7_PROSODY_REHOOK_PHRASES)
        ):
            markers.append(float(sp["start_sec"]))
    markers.append(speech_end)
    gaps = [round(b - a, 2) for a, b in zip(markers, markers[1:])]
    worst = max(gaps) if gaps else 0.0
    gates["P10_open_loop_spacing"] = {
        "passed": worst <= PROSODY_P10_OPEN_LOOP_MAX_GAP_SEC,
        "max_gap_sec": worst,
        "marker_times_sec": [round(m, 2) for m in markers],
    }
    return mode, gates


def evaluate_prosody_gates_on_audio(
    project_id_or_dir: str | Path,
    audio_path: str | Path | None = None,
    gates: tuple[str, ...] | list[str] | None = DEFAULT_AUDIO_PROSODY_GATES,
    run_asr: bool = True,
) -> dict[str, Any]:
    """
    Pre-flight / audio-only Prosody QA wrapper: evaluates P1-P6, P8, P10 (or requested `gates` subset)
    directly against `audio_path` (defaulting to `04_audio/audio_master.wav`, then `final_shorts_1080x1920.mp4`)
    using the exact same thresholds (`PROSODY_P6_ASR_MATCH_MIN`, etc.) as post-assembly `evaluate_prosody_gates`.
    """
    p_dir = _resolve_project_dir(project_id_or_dir)
    if audio_path is not None:
        target_audio = Path(audio_path)
    else:
        wav_cand = p_dir / "04_audio" / "audio_master.wav"
        mp4_cand = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
        target_audio = wav_cand if wav_cand.exists() else mp4_cand

    mode, all_gates = _compute_core_prosody_gates(
        p_dir,
        asr_media_path=target_audio,
        run_asr=run_asr,
        include_mp4_post_gates=False,
    )
    wanted = _normalize_gate_names(gates)
    selected = (
        {k: all_gates[k] for k in wanted if k in all_gates}
        if wanted is not None
        else all_gates
    )
    passed_n = sum(1 for g in selected.values() if g.get("passed"))
    return {
        "project_id": p_dir.name,
        "prosody_mode": mode,
        "audio_path": str(target_audio),
        "passed": bool(selected) and passed_n == len(selected),
        "gates_passed": f"{passed_n}/{len(selected)}",
        "gates": selected,
    }


def evaluate_prosody_gates(project_id_or_dir: str | Path, run_asr: bool = True, save_report: bool = True) -> dict[str, Any]:
    """Runs P1-P10 against 04_audio/prosody_report.json, voice_report.json, autopsy + font probe reports."""
    p_dir = _resolve_project_dir(project_id_or_dir)
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    mode, gates = _compute_core_prosody_gates(
        p_dir,
        asr_media_path=final_mp4,
        run_asr=run_asr,
        include_mp4_post_gates=True,
    )
    passed_n = sum(1 for g in gates.values() if g.get("passed"))
    rep = {
        "project_id": p_dir.name,
        "prosody_mode": mode,
        "passed": passed_n == len(gates),
        "gates_passed": f"{passed_n}/{len(gates)}",
        "gates": gates,
    }
    if save_report:
        from pipeline.storage import ProjectStorage

        out_rep = p_dir / "05_assembly" / "prosody_qa_report.json"
        out_rep.write_text(json.dumps(rep, indent=2, ensure_ascii=False), encoding="utf-8")
        ProjectStorage.record_if_manifest_tracks_stages(p_dir, "05_assembly", "prosody_qa_report.json", out_rep)
    return rep


__all__ = [
    "DEFAULT_AUDIO_PROSODY_GATES",
    "GEARS",
    "apply_emphasis",
    "base_rate_for_mode",
    "classify_prosody_gears",
    "emphasis_words_for",
    "evaluate_prosody_gates",
    "evaluate_prosody_gates_on_audio",
    "fade_edges",
    "measure_edge_silences",
    "measure_internal_max_silence",
    "plan_sentence_prosody",
    "rate_to_speed",
    "resolve_prosody_mode",
]
