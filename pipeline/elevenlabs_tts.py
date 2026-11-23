"""
ALL ABOUT BRAIN — Hybrid ElevenLabs `eleven_v4` Narration Backend (Task 4).

Features:
  - Reads `XI_API_KEY` exclusively from env or `~/.config/aab/elevenlabs.env` (`0600`); never logs raw keys.
  - Pre-flight Creator quota guard (`GET /v1/user/subscription` -> `elevenlabs_credit_state.json`).
  - `POST /v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192` (`model_id='eleven_v4'`,
    `language_code='en'`, `stability=0.45`, `similarity_boost=0.78`).
  - Automatic perpetual/workspace Voice ID fallback (`Elara` -> `Bella` -> `Hope`; `Darian` -> `Sawyer` -> `Adam`)
    avoiding all 19 legacy Default voices expiring Dec 31, 2026.
  - Persistent SHA-256 per-sentence disk cache + `previous_request_ids` / `next_request_ids` (`previous_text` /
    `next_text`) stitching so unchanged episodes cost `0` credits and single-sentence edits re-bill only 1 sentence.
"""

from __future__ import annotations

import base64
import hashlib
import json
import os
import subprocess
import tempfile
import time
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np

from pipeline.config import (
    CAST_REGISTRY_PATH,
    CHANNEL_ROOT,
    ELEVENLABS_CREDIT_STATE_FILE,
    ELEVENLABS_DEFAULT_MODEL_ID,
    ELEVENLABS_DEFAULT_SIMILARITY_BOOST,
    ELEVENLABS_DEFAULT_STABILITY,
    ELEVENLABS_ENV_FILE,
    ELEVENLABS_MIN_RESERVE_CREDITS,
    ELEVENLABS_OUTPUT_FORMAT_CREATOR,
    ELEVENLABS_VOICE_BELLA_ID,
    ELEVENLABS_VOICE_BRIAN_ID,
    ELEVENLABS_VOICE_DARIAN_ID,
    ELEVENLABS_VOICE_ELARA_ID,
    ELEVENLABS_VOICE_ERIC_ID,
    ELEVENLABS_VOICE_HOPE_ID,
    ELEVENLABS_VOICE_LAURA_ID,
    ELEVENLABS_VOICE_ROGER_ID,
    ELEVENLABS_VOICE_SAWYER_ID,
    ELEVENLABS_VOICE_SIREN_ID,
)
from pipeline.plain_language import to_expressive_tts_text, to_tts_text

ELEVENLABS_API_BASE = "https://api.elevenlabs.io"
ELEVENLABS_PERSISTENT_CACHE_DIR = CHANNEL_ROOT / ".cache" / "elevenlabs_tts_v4"
ELEVENLABS_REQUEST_ID_TTL_SEC = 6900.0  # < 2h official stitching TTL

FEMALE_FALLBACK_VOICE_CHAIN: tuple[str, ...] = (
    ELEVENLABS_VOICE_SIREN_ID,
    ELEVENLABS_VOICE_HOPE_ID,
    ELEVENLABS_VOICE_LAURA_ID,
    ELEVENLABS_VOICE_ELARA_ID,
    ELEVENLABS_VOICE_BELLA_ID,
)
MALE_FALLBACK_VOICE_CHAIN: tuple[str, ...] = (
    ELEVENLABS_VOICE_ROGER_ID,
    ELEVENLABS_VOICE_BRIAN_ID,
    ELEVENLABS_VOICE_ERIC_ID,
    ELEVENLABS_VOICE_DARIAN_ID,
    ELEVENLABS_VOICE_SAWYER_ID,
)

DEFAULT_CAST_REGISTRY: dict[str, Any] = {
    "schema": "aab_cast_registry_v1",
    "max_voices_per_episode": 3,
    "default_narrator_role": "narrator",
    "cast": {
        "narrator": {
            "display_name": "Narrator (Siren)",
            "on_screen": False,
            "voice_preset": "el_siren_v4",
            "elevenlabs_voice_id": ELEVENLABS_VOICE_SIREN_ID,
            "elevenlabs_fallback_voice_id": ELEVENLABS_VOICE_HOPE_ID,
            "gender": "female",
            "share_target": "1.00",
            "eq_profile": "female_studio",
            "height_m": 1.72,
        },
        "researcher": {
            "display_name": "Dr. Ada (Researcher)",
            "on_screen": True,
            "voice_preset": "el_researcher_v4",
            "elevenlabs_voice_id": ELEVENLABS_VOICE_HOPE_ID,
            "elevenlabs_fallback_voice_id": ELEVENLABS_VOICE_ELARA_ID,
            "gender": "female",
            "max_lines": 2,
            "height_m": 1.72,
        },
        "mini_cortex": {
            "display_name": "Mini-Cortex",
            "on_screen": True,
            "voice_preset": "el_minicortex_v4",
            "elevenlabs_voice_id": ELEVENLABS_VOICE_LAURA_ID,
            "elevenlabs_fallback_voice_id": ELEVENLABS_VOICE_BELLA_ID,
            "gender": "female",
            "max_lines": 1,
            "height_m": 0.22,
        },
        "foil": {
            "display_name": "Skeptic Foil (Brian)",
            "on_screen": True,
            "voice_preset": "elevenlabs_v4_male",
            "elevenlabs_voice_id": ELEVENLABS_VOICE_BRIAN_ID,
            "elevenlabs_fallback_voice_id": ELEVENLABS_VOICE_ERIC_ID,
            "gender": "male",
            "max_lines": 2,
            "height_m": 1.74,
        },
    },
}


def load_cast_registry(path: Path | None = None) -> dict[str, Any]:
    """Loads `cast_registry.json` with a deterministic fallback to `DEFAULT_CAST_REGISTRY`."""
    reg_p = Path(path) if path is not None else Path(CAST_REGISTRY_PATH)
    if reg_p.is_file():
        try:
            doc = json.loads(reg_p.read_text(encoding="utf-8"))
            if isinstance(doc, dict) and isinstance(doc.get("cast"), dict):
                return doc
        except Exception:  # noqa: BLE001
            pass
    return json.loads(json.dumps(DEFAULT_CAST_REGISTRY))

_RESOLVED_VOICE_IDS: dict[str, str] = {}


class ElevenLabsUnavailableError(RuntimeError):
    """Raised when API key is missing, quota is below reserve, or ElevenLabs API is unreachable."""


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def load_elevenlabs_api_key(env_path: Path | None = None) -> str | None:
    """Loads `XI_API_KEY` from process environment or `~/.config/aab/elevenlabs.env` without ever printing it."""
    for env_k in ("XI_API_KEY", "ELEVENLABS_API_KEY"):
        val = str(os.environ.get(env_k) or "").strip()
        if val:
            return val
    cfg_p = Path(env_path) if env_path is not None else Path(ELEVENLABS_ENV_FILE)
    if not cfg_p.exists():
        return None
    try:
        for raw_line in cfg_p.read_text(encoding="utf-8").splitlines():
            line = raw_line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            if line.startswith("export "):
                line = line[len("export ") :].strip()
            k, v = line.split("=", 1)
            if k.strip() in ("XI_API_KEY", "ELEVENLABS_API_KEY"):
                cleaned = v.strip().strip('"').strip("'")
                if cleaned:
                    return cleaned
    except OSError:
        return None
    return None


R78V_GEAR_VOICE_SETTINGS: dict[str, dict[str, Any]] = {
    "surprised_lift": {"tag": "[curious, slightly surprised]", "stability": 0.32, "style": 0.38},
    "insider_reveal": {"tag": "[conversational, warm]", "stability": 0.42, "style": 0.25},
    "brisk": {"tag": "", "stability": 0.48, "style": 0.15},
    "hushed_suspense": {"tag": "[softly, tense]", "stability": 0.38, "style": 0.30},
    "deadpan_drop": {"tag": "[low, matter-of-fact]", "stability": 0.46, "style": 0.22},
}
_R78V_EXCLUSIVE_GEARS: tuple[str, ...] = (
    "surprised_lift",
    "insider_reveal",
    "hushed_suspense",
    "deadpan_drop",
)


def gear_to_v4_tag(gear: str | None) -> str:
    """Maps R63-P / R78-V prosody gear to concise vocal-only `eleven_v4` delivery tags (never standalone SFX nouns)."""
    g = str(gear or "").strip().lower()
    if g in R78V_GEAR_VOICE_SETTINGS:
        return str(R78V_GEAR_VOICE_SETTINGS[g]["tag"])
    if g == "rush":
        return "[brisk, urgent voice]"
    if g == "stamp":
        return "[measured, deliberate voice]"
    return ""


def gear_to_v4_voice_settings(
    gear: str | None,
    default_stability: float = ELEVENLABS_DEFAULT_STABILITY,
    *,
    use_r78v_5tone: bool = False,
) -> tuple[float, float]:
    """Returns per-gear `(stability, style)` for Rule R78-V 5-tone acting while preserving legacy defaults."""
    g = str(gear or "").strip().lower()
    if g in _R78V_EXCLUSIVE_GEARS or (use_r78v_5tone and g in R78V_GEAR_VOICE_SETTINGS):
        spec = R78V_GEAR_VOICE_SETTINGS[g]
        return (float(spec["stability"]), float(spec["style"]))
    return (float(default_stability), 0.0)


def format_v4_tagged_sentence(sentence: str, gear: str | None = None, preserve_exclamation: bool = True) -> str:
    """Normalizes spoken text for `eleven_v4` and prepends a vocal delivery tag if the sentence doesn't already carry one."""
    base = to_expressive_tts_text(sentence) if preserve_exclamation else to_tts_text(sentence)
    base = base.strip()
    if not base:
        return ""
    if base.startswith("[") and "]" in base[:48]:
        return base
    tag = gear_to_v4_tag(gear)
    return f"{tag} {base}".strip() if tag else base


def extract_word_timestamps_from_alignment(alignment: dict[str, Any] | None) -> list[tuple[float, float, str]]:
    """
    Converts ElevenLabs character-level `alignment` / `normalized_alignment` into `(start_sec, end_sec, word)`
    tuples while stripping any inline `[audio tag]` bracket spans.
    """
    if not isinstance(alignment, dict):
        return []
    chars = alignment.get("characters") or []
    starts = alignment.get("character_start_times_seconds") or []
    ends = alignment.get("character_end_times_seconds") or []
    n = min(len(chars), len(starts), len(ends))
    if n <= 0:
        return []

    words: list[tuple[float, float, str]] = []
    cur_chars: list[str] = []
    cur_t0: float | None = None
    cur_t1: float = 0.0
    in_bracket_tag = False

    def _flush() -> None:
        nonlocal cur_chars, cur_t0, cur_t1
        token = "".join(cur_chars).strip()
        if token and cur_t0 is not None:
            t0 = max(0.0, float(cur_t0))
            t1 = max(t0 + 0.02, float(cur_t1))
            words.append((round(t0, 3), round(t1, 3), token))
        cur_chars = []
        cur_t0 = None

    for idx in range(n):
        ch = str(chars[idx])
        t0 = float(starts[idx])
        t1 = float(ends[idx])
        if ch == "[":
            _flush()
            in_bracket_tag = True
            continue
        if in_bracket_tag:
            if ch == "]":
                in_bracket_tag = False
            continue
        if not ch or ch.isspace():
            _flush()
            continue
        if cur_t0 is None:
            cur_t0 = t0
        cur_t1 = max(cur_t1, t1)
        cur_chars.append(ch)
    _flush()
    return words


def check_elevenlabs_quota(
    required_chars: int = 0,
    *,
    api_key: str | None = None,
    env_path: Path | None = None,
    reserve_credits: int = ELEVENLABS_MIN_RESERVE_CREDITS,
    state_file: Path | None = None,
    timeout_sec: float = 15.0,
) -> dict[str, Any]:
    """Queries `GET /v1/user/subscription` and persists non-secret credit telemetry to `elevenlabs_credit_state.json`."""
    key = api_key or load_elevenlabs_api_key(env_path=env_path)
    if not key:
        raise ElevenLabsUnavailableError("ElevenLabs API key missing (checked XI_API_KEY and ~/.config/aab/elevenlabs.env)")
    req = urllib.request.Request(
        f"{ELEVENLABS_API_BASE}/v1/user/subscription",
        headers={"xi-api-key": key, "Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
            sub = json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        raise ElevenLabsUnavailableError(f"ElevenLabs subscription check HTTP {exc.code}") from exc
    except Exception as exc:  # noqa: BLE001
        raise ElevenLabsUnavailableError(f"ElevenLabs subscription check failed: {type(exc).__name__}") from exc

    char_count = int(sub.get("character_count") or 0)
    char_limit = int(sub.get("character_limit") or 0)
    remaining = max(0, char_limit - char_count)
    need_total = max(0, int(required_chars)) + max(0, int(reserve_credits))
    out = {
        "tier": str(sub.get("tier") or ""),
        "status": str(sub.get("status") or ""),
        "character_count": char_count,
        "character_limit": char_limit,
        "remaining_credits": remaining,
        "required_chars": int(required_chars),
        "reserve_credits": int(reserve_credits),
        "available": bool(remaining >= need_total),
        "next_character_count_reset_unix": sub.get("next_character_count_reset_unix"),
        "checked_at_unix": int(time.time()),
    }
    st_path = Path(state_file) if state_file is not None else Path(ELEVENLABS_CREDIT_STATE_FILE)
    try:
        st_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_p = st_path.with_suffix(f".json.tmp.{os.getpid()}")
        tmp_p.write_text(json.dumps(out, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp_p, st_path)
    except OSError:
        pass
    return out


def _decode_mp3_bytes_to_pcm(mp3_bytes: bytes, sr: int = 48000) -> np.ndarray:
    from pipeline.media_cache import ram_tempdir

    with ram_tempdir(prefix="aab_el_mp3_") as td:
        mp3_p = Path(td) / "in.mp3"
        mp3_p.write_bytes(mp3_bytes)
        res = subprocess.run(
            [
                _ffmpeg_exe(),
                "-nostdin",
                "-hide_banner",
                "-loglevel",
                "error",
                "-i",
                str(mp3_p),
                "-af",
                f"aresample={sr}:resampler=soxr",
                "-f",
                "f32le",
                "-ac",
                "1",
                "pipe:1",
            ],
            capture_output=True,
            check=False,
            timeout=60,
            stdin=subprocess.DEVNULL,
        )
    if res.returncode != 0 or not res.stdout:
        raise ElevenLabsUnavailableError(f"Failed decoding ElevenLabs MP3 audio (rc={res.returncode})")
    return np.frombuffer(res.stdout, dtype=np.float32).copy()


def _candidate_voice_chain(primary_voice_id: str, fallback_voice_id: str | None = None, gender: str = "female") -> list[str]:
    chain: list[str] = []
    cached_primary = _RESOLVED_VOICE_IDS.get(primary_voice_id)
    if cached_primary:
        chain.append(cached_primary)
    for cand in (
        primary_voice_id,
        fallback_voice_id or "",
        *(MALE_FALLBACK_VOICE_CHAIN if str(gender).lower() == "male" else FEMALE_FALLBACK_VOICE_CHAIN),
    ):
        c = str(cand or "").strip()
        if c and c not in chain:
            chain.append(c)
    return chain


def _sentence_cache_stem(
    *,
    primary_voice_id: str,
    model_id: str,
    tagged_text: str,
    stability: float,
    similarity_boost: float,
    output_format: str,
    style: float = 0.0,
) -> str:
    style_val = float(style or 0.0)
    style_part = f"|style={style_val:.3f}" if style_val > 0.0 else ""
    payload = (
        f"v1|{model_id}|{primary_voice_id}|{stability:.3f}|{similarity_boost:.3f}{style_part}|{output_format}|{tagged_text}"
    )
    return "el_v4_" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:24]


def synthesize_elevenlabs_v4_sentence(
    text: str,
    *,
    voice_id: str = ELEVENLABS_VOICE_ELARA_ID,
    fallback_voice_id: str | None = ELEVENLABS_VOICE_BELLA_ID,
    gender: str = "female",
    gear: str | None = None,
    preserve_exclamation: bool = True,
    sr: int = 48000,
    model_id: str = ELEVENLABS_DEFAULT_MODEL_ID,
    output_format: str = ELEVENLABS_OUTPUT_FORMAT_CREATOR,
    stability: float = ELEVENLABS_DEFAULT_STABILITY,
    similarity_boost: float = ELEVENLABS_DEFAULT_SIMILARITY_BOOST,
    style: float = 0.0,
    previous_request_ids: list[str] | None = None,
    next_request_ids: list[str] | None = None,
    previous_text: str | None = None,
    next_text: str | None = None,
    cache_dir: Path | None = None,
    api_key: str | None = None,
    env_path: Path | None = None,
    force_refresh: bool = False,
    timeout_sec: float = 45.0,
) -> dict[str, Any]:
    """
    Synthesizes (or loads from persistent SHA-256 disk cache) ONE sentence via
    `POST /v1/text-to-speech/{voice_id}/with-timestamps?output_format=mp3_44100_192`.
    Supports surgical single-sentence regeneration via `previous_request_ids` and `next_request_ids`.
    """
    tagged = format_v4_tagged_sentence(text, gear=gear, preserve_exclamation=preserve_exclamation)
    if not tagged:
        raise ValueError("Empty sentence passed to synthesize_elevenlabs_v4_sentence")

    eff_style = max(0.0, min(1.0, float(style or 0.0)))
    c_dir = Path(cache_dir) if cache_dir is not None else Path(ELEVENLABS_PERSISTENT_CACHE_DIR)
    c_dir.mkdir(parents=True, exist_ok=True)
    stem = _sentence_cache_stem(
        primary_voice_id=voice_id,
        model_id=model_id,
        tagged_text=tagged,
        stability=stability,
        similarity_boost=similarity_boost,
        output_format=output_format,
        style=eff_style,
    )
    mp3_path = c_dir / f"{stem}.mp3"
    meta_path = c_dir / f"{stem}.json"

    if not force_refresh and mp3_path.exists() and meta_path.exists() and mp3_path.stat().st_size > 256:
        try:
            meta = json.loads(meta_path.read_text(encoding="utf-8"))
            pcm = _decode_mp3_bytes_to_pcm(mp3_path.read_bytes(), sr=sr)
            raw_wts = meta.get("word_timestamps") or []
            wts = [(float(x[0]), float(x[1]), str(x[2])) for x in raw_wts if isinstance(x, (list, tuple)) and len(x) == 3]
            return {
                "pcm": pcm,
                "voice_id": str(meta.get("voice_id") or voice_id),
                "request_id": str(meta.get("request_id") or ""),
                "created_at_unix": float(meta.get("created_at_unix") or 0.0),
                "characters_used": 0,
                "script_characters": len(tagged),
                "word_timestamps": wts,
                "tagged_text": tagged,
                "stability": float(meta.get("stability") or stability),
                "style": float(meta.get("style") or eff_style),
                "cached": True,
                "mp3_path": str(mp3_path),
            }
        except Exception:  # noqa: BLE001
            pass

    key = api_key or load_elevenlabs_api_key(env_path=env_path)
    if not key:
        raise ElevenLabsUnavailableError("ElevenLabs API key missing")

    voice_settings_obj: dict[str, Any] = {
        "stability": round(float(stability), 3),
        "similarity_boost": round(float(similarity_boost), 3),
    }
    if eff_style > 0.0:
        voice_settings_obj["style"] = round(eff_style, 3)

    body: dict[str, Any] = {
        "text": tagged,
        "model_id": model_id,
        "language_code": "en",
        "voice_settings": voice_settings_obj,
    }
    clean_prev_ids = [str(x).strip() for x in (previous_request_ids or []) if str(x).strip()][:3]
    clean_next_ids = [str(x).strip() for x in (next_request_ids or []) if str(x).strip()][:3]
    if clean_prev_ids:
        body["previous_request_ids"] = clean_prev_ids
    elif previous_text and str(previous_text).strip():
        body["previous_text"] = str(previous_text).strip()[-400:]
    if clean_next_ids:
        body["next_request_ids"] = clean_next_ids
    elif next_text and str(next_text).strip():
        body["next_text"] = str(next_text).strip()[:400]

    candidates = _candidate_voice_chain(voice_id, fallback_voice_id=fallback_voice_id, gender=gender)
    last_err: Exception | None = None
    resp_json: dict[str, Any] | None = None
    resp_headers: dict[str, str] = {}
    used_vid = voice_id

    for cand_vid in candidates:
        q = urllib.parse.urlencode({"output_format": output_format})
        url = f"{ELEVENLABS_API_BASE}/v1/text-to-speech/{cand_vid}/with-timestamps?{q}"
        try_body = dict(body)
        if cand_vid != voice_id:
            # Request IDs are voice-specific; swap to text continuity if falling back to another voice
            try_body.pop("previous_request_ids", None)
            try_body.pop("next_request_ids", None)
            if previous_text and str(previous_text).strip():
                try_body["previous_text"] = str(previous_text).strip()[-400:]
            if next_text and str(next_text).strip():
                try_body["next_text"] = str(next_text).strip()[:400]
        retry_delays = (1.5, 3.0, 6.0)
        voice_unavailable = False
        stripped_style_once = False
        attempt = 0
        while attempt <= len(retry_delays):
            req = urllib.request.Request(
                url,
                data=json.dumps(try_body, ensure_ascii=False).encode("utf-8"),
                headers={
                    "xi-api-key": key,
                    "Content-Type": "application/json",
                    "Accept": "application/json",
                },
                method="POST",
            )
            try:
                with urllib.request.urlopen(req, timeout=timeout_sec) as resp:
                    resp_headers = {k.lower(): v for k, v in resp.headers.items()}
                    resp_json = json.loads(resp.read().decode("utf-8"))
                    used_vid = cand_vid
                    _RESOLVED_VOICE_IDS[voice_id] = cand_vid
                    break
            except urllib.error.HTTPError as exc:
                err_body = ""
                try:
                    err_body = exc.read().decode("utf-8", errors="ignore")[:300]
                except Exception:  # noqa: BLE001
                    err_body = ""
                last_err = ElevenLabsUnavailableError(
                    f"ElevenLabs TTS HTTP {exc.code} on voice_id={cand_vid}: {err_body}"
                )
                err_low = err_body.lower()
                is_quota_err = any(
                    q_tok in err_low
                    for q_tok in ("quota_exceeded", "insufficient", "character_limit", "exceeds your quota", "out of credits")
                )
                # Fail-fast immediately on 401 auth errors or explicit quota exhaustion (never retry or downgrade)
                if exc.code == 401 or (exc.code in (402, 429) and is_quota_err):
                    raise last_err from exc
                # If ElevenLabs rejects optional `style` parameter with 400/422, retry once without `style`
                vs_dict = try_body.get("voice_settings") if isinstance(try_body.get("voice_settings"), dict) else None
                if exc.code in (400, 422) and vs_dict is not None and "style" in vs_dict and not stripped_style_once:
                    try_body = dict(try_body)
                    try_body["voice_settings"] = {k: v for k, v in vs_dict.items() if k != "style"}
                    stripped_style_once = True
                    continue
                # Retry next candidate voice on 400/403/404 voice-availability errors
                if exc.code in (400, 403, 404):
                    voice_unavailable = True
                    break
                # Transient rate-limit (429) or server errors (500/502/503/504): 3x exponential backoff (1.5s -> 3.0s -> 6.0s)
                if exc.code in (429, 500, 502, 503, 504) and attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    attempt += 1
                    continue
                raise last_err from exc
            except Exception as exc:  # noqa: BLE001
                last_err = ElevenLabsUnavailableError(f"ElevenLabs TTS network error: {type(exc).__name__}: {exc}")
                if attempt < len(retry_delays):
                    time.sleep(retry_delays[attempt])
                    attempt += 1
                    continue
                raise last_err from exc
        if resp_json is not None:
            break
        if voice_unavailable:
            continue

    if resp_json is None:
        raise last_err or ElevenLabsUnavailableError("ElevenLabs TTS failed across all candidate voices")

    b64_audio = str(resp_json.get("audio_base64") or "")
    if not b64_audio:
        raise ElevenLabsUnavailableError("ElevenLabs TTS returned empty audio_base64")
    mp3_bytes = base64.b64decode(b64_audio)
    pcm = _decode_mp3_bytes_to_pcm(mp3_bytes, sr=sr)
    align_obj = resp_json.get("normalized_alignment") or resp_json.get("alignment")
    word_ts = extract_word_timestamps_from_alignment(align_obj)
    req_id = str(resp_headers.get("request-id") or resp_headers.get("x-request-id") or "")
    hdr_cost = resp_headers.get("character-cost") or resp_headers.get("x-character-count")
    try:
        chars_used = int(hdr_cost) if hdr_cost is not None else len(tagged)
    except ValueError:
        chars_used = len(tagged)

    now_ts = round(time.time(), 3)
    meta_doc = {
        "voice_id": used_vid,
        "requested_voice_id": voice_id,
        "model_id": model_id,
        "output_format": output_format,
        "stability": stability,
        "similarity_boost": similarity_boost,
        "style": eff_style,
        "tagged_text": tagged,
        "request_id": req_id,
        "characters_billed": chars_used,
        "created_at_unix": now_ts,
        "word_timestamps": [[t0, t1, w] for t0, t1, w in word_ts],
    }
    try:
        tmp_mp3 = mp3_path.with_suffix(f".mp3.tmp.{os.getpid()}")
        tmp_meta = meta_path.with_suffix(f".json.tmp.{os.getpid()}")
        tmp_mp3.write_bytes(mp3_bytes)
        tmp_meta.write_text(json.dumps(meta_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp_mp3, mp3_path)
        os.replace(tmp_meta, meta_path)
    except OSError:
        pass

    return {
        "pcm": pcm,
        "voice_id": used_vid,
        "request_id": req_id,
        "created_at_unix": now_ts,
        "characters_used": chars_used,
        "script_characters": len(tagged),
        "word_timestamps": word_ts,
        "tagged_text": tagged,
        "stability": float(stability),
        "style": eff_style,
        "cached": False,
        "mp3_path": str(mp3_path),
    }


def is_episode_fully_cached(
    sentences: list[str],
    *,
    voice_id: str = ELEVENLABS_VOICE_ROGER_ID,
    gears: list[str | None] | None = None,
    foil_indices: set[int] | None = None,
    foil_voice_id: str | None = None,
    speaker_voice_by_idx: dict[int, dict[str, Any] | str] | None = None,
    preserve_exclamation: bool = True,
    model_id: str = ELEVENLABS_DEFAULT_MODEL_ID,
    output_format: str = ELEVENLABS_OUTPUT_FORMAT_CREATOR,
    stability: float = ELEVENLABS_DEFAULT_STABILITY,
    similarity_boost: float = ELEVENLABS_DEFAULT_SIMILARITY_BOOST,
    r78v_5tone: bool = False,
    cache_dir: Path | None = None,
) -> bool:
    """Returns True when every sentence in `sentences` already has a verified cached `.mp3` + `.json` on disk."""
    c_dir = Path(cache_dir) if cache_dir is not None else Path(ELEVENLABS_PERSISTENT_CACHE_DIR)
    if not c_dir.exists():
        return False
    foils = foil_indices or set()
    sp_by_idx = speaker_voice_by_idx or {}
    use_r78v = bool(r78v_5tone) or any(str(g or "").strip().lower() in _R78V_EXCLUSIVE_GEARS for g in (gears or []))
    for idx, sent in enumerate(sentences, start=1):
        sp_spec = sp_by_idx.get(idx)
        if isinstance(sp_spec, str) and sp_spec.strip():
            vid = sp_spec.strip()
        elif isinstance(sp_spec, dict) and sp_spec.get("voice_id"):
            vid = str(sp_spec["voice_id"])
        else:
            vid = (foil_voice_id or voice_id) if idx in foils else voice_id
        gear = gears[idx - 1] if (gears and idx - 1 < len(gears)) else None
        sent_stab, sent_style = gear_to_v4_voice_settings(gear, stability, use_r78v_5tone=use_r78v)
        tagged = format_v4_tagged_sentence(sent, gear=gear, preserve_exclamation=preserve_exclamation)
        stem = _sentence_cache_stem(
            primary_voice_id=vid,
            model_id=model_id,
            tagged_text=tagged,
            stability=sent_stab,
            similarity_boost=similarity_boost,
            output_format=output_format,
            style=sent_style,
        )
        if not ((c_dir / f"{stem}.mp3").exists() and (c_dir / f"{stem}.json").exists()):
            return False
    return True


def synthesize_elevenlabs_v4_episode(
    sentences: list[str],
    *,
    voice_id: str = ELEVENLABS_VOICE_ROGER_ID,
    fallback_voice_id: str | None = ELEVENLABS_VOICE_BRIAN_ID,
    gender: str = "male",
    gears: list[str | None] | None = None,
    foil_indices: set[int] | None = None,
    foil_voice_id: str | None = ELEVENLABS_VOICE_BRIAN_ID,
    foil_fallback_voice_id: str | None = ELEVENLABS_VOICE_ERIC_ID,
    foil_gender: str = "male",
    speaker_voice_by_idx: dict[int, dict[str, Any]] | None = None,
    preserve_exclamation: bool = True,
    sr: int = 48000,
    model_id: str = ELEVENLABS_DEFAULT_MODEL_ID,
    output_format: str = ELEVENLABS_OUTPUT_FORMAT_CREATOR,
    stability: float = ELEVENLABS_DEFAULT_STABILITY,
    similarity_boost: float = ELEVENLABS_DEFAULT_SIMILARITY_BOOST,
    r78v_5tone: bool = False,
    force_refresh_indices: set[int] | None = None,
    cache_dir: Path | None = None,
    api_key: str | None = None,
    env_path: Path | None = None,
) -> dict[str, Any]:
    """
    Synthesizes an entire episode's sentences with `eleven_v4` (supporting up to 3 cast voices:
    e.g. `Roger` narrator + `Hope` researcher + `Laura` Mini-Cortex):
      - Reuses cached sentences at `0` credit cost.
      - Checks live Creator subscription quota ONLY for uncached sentences before spending credits.
      - Uses per-speaker `previous_request_ids` / `next_request_ids` (within 2h TTL) and `previous_text` / `next_text`
        for seamless multi-sentence & surgical single-sentence prosody continuity.
    """
    c_dir = Path(cache_dir) if cache_dir is not None else Path(ELEVENLABS_PERSISTENT_CACHE_DIR)
    c_dir.mkdir(parents=True, exist_ok=True)
    foils = set(foil_indices or set())
    sp_by_idx = dict(speaker_voice_by_idx or {})
    force_set = set(force_refresh_indices or set())

    def _voice_spec_for_sentence(idx_1based: int) -> tuple[str, str | None, str, str]:
        sp_entry = sp_by_idx.get(idx_1based)
        if isinstance(sp_entry, str) and sp_entry.strip():
            s_vid = sp_entry.strip()
            s_gen = "female" if s_vid in FEMALE_FALLBACK_VOICE_CHAIN else gender
            return (
                s_vid,
                (ELEVENLABS_VOICE_ELARA_ID if s_gen == "female" else fallback_voice_id),
                s_gen,
                ("narrator" if s_vid == str(voice_id) else "character"),
            )
        if isinstance(sp_entry, dict) and sp_entry.get("voice_id"):
            return (
                str(sp_entry["voice_id"]),
                (str(sp_entry["fallback_voice_id"]) if sp_entry.get("fallback_voice_id") else None),
                str(sp_entry.get("gender") or gender),
                str(sp_entry.get("role") or "character"),
            )
        if idx_1based in foils:
            return (
                str(foil_voice_id or ELEVENLABS_VOICE_BRIAN_ID),
                foil_fallback_voice_id,
                foil_gender,
                "foil",
            )
        return (str(voice_id), fallback_voice_id, gender, "narrator")

    # Pre-scan cache status & compute exact uncached character requirement
    use_r78v = bool(r78v_5tone) or any(str(g or "").strip().lower() in _R78V_EXCLUSIVE_GEARS for g in (gears or []))
    tagged_list: list[str] = []
    cached_meta_by_idx: dict[int, dict[str, Any]] = {}
    uncached_chars = 0
    for idx, sent in enumerate(sentences, start=1):
        vid, _fb_v, _gen_v, _role_v = _voice_spec_for_sentence(idx)
        gear = gears[idx - 1] if (gears and idx - 1 < len(gears)) else None
        sent_stab, sent_style = gear_to_v4_voice_settings(gear, stability, use_r78v_5tone=use_r78v)
        tagged = format_v4_tagged_sentence(sent, gear=gear, preserve_exclamation=preserve_exclamation)
        tagged_list.append(tagged)
        stem = _sentence_cache_stem(
            primary_voice_id=vid,
            model_id=model_id,
            tagged_text=tagged,
            stability=sent_stab,
            similarity_boost=similarity_boost,
            output_format=output_format,
            style=sent_style,
        )
        mp3_p = c_dir / f"{stem}.mp3"
        meta_p = c_dir / f"{stem}.json"
        if idx not in force_set and mp3_p.exists() and meta_p.exists() and mp3_p.stat().st_size > 256:
            try:
                cached_meta_by_idx[idx] = json.loads(meta_p.read_text(encoding="utf-8"))
                continue
            except Exception:  # noqa: BLE001
                pass
        uncached_chars += len(tagged)

    quota_info: dict[str, Any] | None = None
    key: str | None = None
    if uncached_chars > 0:
        key = api_key or load_elevenlabs_api_key(env_path=env_path)
        if not key:
            raise ElevenLabsUnavailableError("ElevenLabs API key not configured")
        quota_info = check_elevenlabs_quota(
            required_chars=uncached_chars,
            api_key=key,
            env_path=env_path,
        )
        if not quota_info.get("available"):
            raise ElevenLabsUnavailableError(
                f"ElevenLabs quota insufficient: remaining={quota_info.get('remaining_credits')} "
                f"< required={uncached_chars} + reserve={quota_info.get('reserve_credits')}"
            )

    pcms: list[np.ndarray] = []
    word_ts_by_idx: dict[int, list[tuple[float, float, str]]] = {}
    request_ids: list[str] = []
    used_voices_by_idx: dict[int, str] = {}
    speaker_roles_by_idx: dict[int, str] = {}
    recent_by_voice: dict[str, list[tuple[str, float]]] = {}
    total_chars_billed = 0
    resolved_narrator_vid = voice_id
    resolved_foil_vid = foil_voice_id or ELEVENLABS_VOICE_BRIAN_ID
    now_now = time.time()

    for idx, sent in enumerate(sentences, start=1):
        req_vid, req_fb, req_gender, req_role = _voice_spec_for_sentence(idx)
        speaker_roles_by_idx[idx] = req_role
        gear = gears[idx - 1] if (gears and idx - 1 < len(gears)) else None

        prev_txt = " ".join(sentences[max(0, idx - 3) : idx - 1])
        next_txt = " ".join(sentences[idx : min(len(sentences), idx + 2)])

        # Collect fresh (<2h) previous request IDs on the same voice
        prev_rids = [
            rid
            for rid, ts in (recent_by_voice.get(_RESOLVED_VOICE_IDS.get(req_vid, req_vid)) or [])
            if rid and (now_now - ts) < ELEVENLABS_REQUEST_ID_TTL_SEC
        ][-3:]

        # Collect fresh (<2h) next request IDs from cached future sentences on the same voice (for surgical 1-line regen)
        next_rids: list[str] = []
        for fut_i in range(idx + 1, min(len(sentences) + 1, idx + 4)):
            fut_vid, _, _, _ = _voice_spec_for_sentence(fut_i)
            if fut_vid != req_vid:
                break
            fut_meta = cached_meta_by_idx.get(fut_i)
            if not fut_meta:
                break
            f_rid = str(fut_meta.get("request_id") or "")
            f_ts = float(fut_meta.get("created_at_unix") or 0.0)
            if f_rid and (now_now - f_ts) < ELEVENLABS_REQUEST_ID_TTL_SEC:
                next_rids.append(f_rid)

        sent_stab, sent_style = gear_to_v4_voice_settings(gear, stability, use_r78v_5tone=use_r78v)
        res_i = synthesize_elevenlabs_v4_sentence(
            sent,
            voice_id=req_vid,
            fallback_voice_id=req_fb,
            gender=req_gender,
            gear=gear,
            preserve_exclamation=preserve_exclamation,
            sr=sr,
            model_id=model_id,
            output_format=output_format,
            stability=sent_stab,
            similarity_boost=similarity_boost,
            style=sent_style,
            previous_request_ids=prev_rids or None,
            next_request_ids=next_rids or None,
            previous_text=prev_txt or None,
            next_text=next_txt or None,
            cache_dir=c_dir,
            api_key=key,
            env_path=env_path,
            force_refresh=(idx in force_set),
        )
        pcms.append(res_i["pcm"])
        if res_i["word_timestamps"]:
            word_ts_by_idx[idx - 1] = res_i["word_timestamps"]
        rid_i = str(res_i.get("request_id") or "")
        request_ids.append(rid_i)
        used_v = str(res_i["voice_id"])
        used_voices_by_idx[idx] = used_v
        if req_role == "narrator":
            resolved_narrator_vid = used_v
        elif req_role == "foil":
            resolved_foil_vid = used_v
        if rid_i:
            recent_by_voice.setdefault(used_v, []).append((rid_i, float(res_i.get("created_at_unix") or time.time())))
        total_chars_billed += int(res_i.get("characters_used") or 0)

    return {
        "pcms": pcms,
        "word_timestamps_by_idx": word_ts_by_idx,
        "characters_used": total_chars_billed,
        "script_characters": sum(len(t) for t in tagged_list),
        "voice_id": resolved_narrator_vid,
        "foil_voice_id": (resolved_foil_vid if foils else None),
        "used_voices_by_idx": used_voices_by_idx,
        "speaker_roles_by_idx": speaker_roles_by_idx,
        "model_id": model_id,
        "output_format": output_format,
        "request_ids": request_ids,
        "r78v_5tone": use_r78v,
        "quota": quota_info,
    }
