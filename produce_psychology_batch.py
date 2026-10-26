"""
ALL ABOUT BRAIN - Native Google Flow audio, subtitle and video assembly engine (Production Contract v4).

- Assembles 5-10 native Google Flow (Omni 1.1, Puck voice) clips into one 1080x1920 @ 30fps Short.
- Per-clip speech-window detection (prompt-bleed cutoff, soft sentence-end preservation) drives a
  synchronized 1.08x video (setpts) + vocal (atempo) speedup with a +0.15s post-speech hold, a +0.30s
  hold before the pivot clip and a +0.20s tail on the final clip.
- 4-layer audio master: native voice (3-band EQ + 3.5:1 compression), two-phase synth bed split at the
  pivot ("Instead of ...") clip, action-synced Foley, and UI ticks at clip cuts plus the pivot start.
- Single-line 2-3 word ASS subtitles (MarginV=440) aligned to each clip's vocal envelope. No HUD overlays.
"""

import json
import re
import shutil
import subprocess
import sys
from pathlib import Path
from typing import Any

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Ensure project root in sys.path
WORKSPACE_ROOT = Path(__file__).resolve().parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

import imageio_ffmpeg  # noqa: E402
from pipeline.config import (  # noqa: E402
    AV_SPEEDUP_FACTOR,
    CLIP_COUNT_MAX,
    CLIP_COUNT_MIN,
    CLIP_PRE_PIVOT_HOLD_SEC,
    CLIP_PRE_ROLL_TRIM_SEC,
    CLIP_VISUAL_HOLD_SEC,
    EFFECTIVE_WPS,
    END_FADE_SEC,
    FINAL_TAIL_SEC,
    MASTER_TAIL_MUTE_SEC,
    MIN_CLIP_SIZE_BYTES,
    MIN_CLIPS_FOR_ASSEMBLY,
    PROMPT_BLEED_CUTOFF_RULES,
    PROMPT_BLEED_DEFAULT_SYLLABLES,
    PROMPT_BLEED_MIN_EXPECTED_SEC,
    PROMPT_BLEED_PAUSE_ALLOWANCE_SEC,
    PROMPT_BLEED_SYLLABLE_SEC,
    SOFT_TAIL_FLOOR_DB,
    SOFT_TAIL_MAX_GAP_SEC,
    SOFT_TAIL_P15_OFFSET_DB,
    SOFT_TAIL_P95_OFFSET_DB,
    SOFT_TAIL_SEARCH_SEC,
    SPEECH_END_PAD_BROKE_EARLY_SEC,
    SPEECH_END_PAD_SEC,
    SUBPROCESS_TIMEOUT_SEC,
    SUBTITLE_FONT_NAME,
    SUBTITLE_FONT_SIZE,
    SUBTITLE_MARGIN_V,
    SUBTITLE_MAX_LINES,
    SUBTITLE_MAX_WORDS_PER_EVENT,
    SUBTITLE_OUTLINE_WIDTH,
    SUBTITLE_SHADOW_DEPTH,
    VIDEO_FPS,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    VOCAL_BANDPASS_HZ,
    VOCAL_COMPRESSOR,
    VOCAL_EQ_BANDS,
    VOCAL_ONSET_PAD_SEC,
    VOCAL_ONSET_PROTECT_SEC,
    pivot_clip_index,
)
from pipeline.storage import ProjectStorage, numeric_clip_sort_key  # noqa: E402
from pipeline.topics_catalog import PSYCHOLOGY_TOPICS  # noqa: E402

_STAGE_TEXT_KEYS: tuple[tuple[str, tuple[str, ...]], ...] = (
    ("hook_text", ("hook",)),
    ("setup_text", ("setup", "dilemma")),
    ("core_text", ("core",)),
    ("payoff_text", ("payoff", "twist")),
)


def _format_ass_time(seconds: float) -> str:
    s = max(0.0, float(seconds))
    hrs = int(s // 3600)
    mins = int((s % 3600) // 60)
    secs = s % 60.0
    return f"{hrs}:{mins:02d}:{secs:05.2f}"


def _count_english_syllables(word: str) -> int:
    """Estimates phonetic syllable count of an English word/number for acoustic CDF alignment."""
    clean = re.sub(r"[^a-zA-Z0-9]", "", word).lower()
    if not clean:
        return 1
    if clean.isdigit():
        return max(2, len(clean))
    vowels = "aeiouy"
    count = 0
    prev_v = False
    for ch in clean:
        is_v = ch in vowels
        if is_v and not prev_v:
            count += 1
        prev_v = is_v
    if clean.endswith("e") and not clean.endswith("le") and count > 1:
        count -= 1
    return max(1, count)


def _chunk_sentence_into_phrases(sentence: str, max_words: int = 5) -> list[list[str]]:
    """
    Splits a single sentence into short, rhythmic 3-5 word phrases ('신비한 건축사전' style)
    while respecting clause punctuation (commas, colons, semicolons) and never crossing sentences.
    """
    tokens = [t for t in sentence.strip().split() if t]
    if not tokens:
        return []
    if len(tokens) <= max_words:
        return [tokens]

    # First split by internal clause punctuation (, ; :)
    raw_clauses: list[list[str]] = []
    cur: list[str] = []
    for tok in tokens:
        cur.append(tok)
        if tok.endswith((",", ";", ":")):
            raw_clauses.append(cur)
            cur = []
    if cur:
        raw_clauses.append(cur)

    # Merge any 1-word introductory clause (e.g., "Inside,", "Incredibly,") into the next clause
    clauses: list[list[str]] = []
    idx_c = 0
    while idx_c < len(raw_clauses):
        if len(raw_clauses[idx_c]) == 1 and idx_c + 1 < len(raw_clauses):
            merged = raw_clauses[idx_c] + raw_clauses[idx_c + 1]
            clauses.append(merged)
            idx_c += 2
        else:
            clauses.append(raw_clauses[idx_c])
            idx_c += 1

    NO_SPLIT_AFTER = {
        "a", "an", "the", "to", "of", "in", "into", "on", "at", "by", "for", "with", "from",
        "without", "inside", "within", "through", "between", "under", "over", "after", "before",
        "your", "my", "its", "their", "his", "her", "our", "this", "that", "these", "those",
        "every", "single", "no", "any", "some", "all", "both", "each",
        "is", "are", "was", "were", "be", "been", "has", "have", "had", "can", "could", "will", "would",
        "not", "never", "ever", "very", "too", "so", "quite", "most", "more", "less",
        "human", "physical", "hidden", "conscious", "bad", "repeated", "silent", "imagined",
        "severe", "total", "full", "tiny", "automatic", "destructive", "forty-millivolt",
        "fiber-optic", "one", "hundred", "twenty-eight", "sixty-two", "vocal", "logic", "basal",
    }

    phrases: list[list[str]] = []
    for clause in clauses:
        n = len(clause)
        if n <= max_words:
            if phrases and len(clause) <= 2 and len(phrases[-1]) + len(clause) <= max_words:
                phrases[-1].extend(clause)
            else:
                phrases.append(clause)
        else:
            num_chunks = max(2, int(round(n / 3.8)))
            while (n + num_chunks - 1) // num_chunks > max_words:
                num_chunks += 1
            idx = 0
            for c_i in range(num_chunks):
                rem_words = n - idx
                rem_chunks = num_chunks - c_i
                if rem_chunks <= 1:
                    phrases.append(clause[idx:])
                    idx = n
                    break
                ideal_take = int(round(rem_words / float(rem_chunks)))
                best_take = max(2, min(max_words, ideal_take))
                best_cost = 1e9
                for cand_take in range(2, min(max_words, rem_words - 1) + 1):
                    rem_after = rem_words - cand_take
                    if rem_after < (rem_chunks - 1) * 2:
                        continue
                    if rem_after > (rem_chunks - 1) * max_words:
                        continue
                    last_w = re.sub(r"[^\w-]", "", clause[idx + cand_take - 1]).lower()
                    cost = abs(cand_take - ideal_take) * 1.0
                    if last_w in NO_SPLIT_AFTER:
                        cost += 4.0
                    if cost < best_cost:
                        best_cost = cost
                        best_take = cand_take
                phrases.append(clause[idx : idx + best_take])
                idx += best_take
            if idx < n:
                if phrases and len(phrases[-1]) + (n - idx) <= max_words:
                    phrases[-1].extend(clause[idx:])
                else:
                    phrases.append(clause[idx:])
    return [p for p in phrases if p]


def _clean_narrations(raw: Any) -> list[str] | None:
    """Returns stripped narrations when `raw` is a list of CLIP_COUNT_MIN..CLIP_COUNT_MAX non-empty strings, else None."""
    if not isinstance(raw, list):
        return None
    cleaned = [str(s).strip() for s in raw if str(s).strip()]
    if CLIP_COUNT_MIN <= len(cleaned) <= CLIP_COUNT_MAX:
        return cleaned
    return None


def _catalog_topic(project_id: str) -> dict[str, Any] | None:
    """Returns the topics_catalog entry for `project_id` (PSYCHOLOGY_TOPICS first, then ALL_PSYCHOLOGY_100_TOPICS)."""
    from pipeline.topics_catalog import ALL_PSYCHOLOGY_100_TOPICS

    for item in list(PSYCHOLOGY_TOPICS) + list(ALL_PSYCHOLOGY_100_TOPICS):
        if item.get("project_id") == project_id:
            return item
    return None


def _read_json_dict(path: Path) -> dict[str, Any]:
    """Reads a JSON object from `path`; returns {} when the file is absent. Malformed JSON raises ValueError."""
    if not path.exists():
        return {}
    data = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError(f"{path} must contain a JSON object, got {type(data).__name__}")
    return data


def _script_stage_texts(script_data: dict[str, Any]) -> dict[str, str]:
    """Extracts hook/setup/core/payoff texts from a script.json payload (flat or nested under 'script_stages')."""
    stages = script_data.get("script_stages", script_data)
    if not isinstance(stages, dict):
        stages = {}
    texts: dict[str, str] = {}
    for out_key, src_keys in _STAGE_TEXT_KEYS:
        value = ""
        for src_key in src_keys:
            obj = stages.get(src_key)
            if isinstance(obj, dict) and str(obj.get("text") or "").strip():
                value = str(obj["text"]).strip()
                break
        texts[out_key] = value
    return texts


def _script_clip_narrations(script_data: dict[str, Any]) -> list[str] | None:
    """Returns clip_narrations from a script.json payload (top level or nested under 'script_stages')."""
    narrations = _clean_narrations(script_data.get("clip_narrations"))
    if narrations:
        return narrations
    stages = script_data.get("script_stages")
    if isinstance(stages, dict):
        return _clean_narrations(stages.get("clip_narrations"))
    return None


def resolve_topic_item(project_dir: Path) -> dict[str, Any]:
    """
    Resolves the topic dict used for audio/subtitle/assembly of a project:
    1. The topics_catalog entry whose project_id equals the project folder name.
    2. Otherwise a dict rebuilt from 02_script/script.json (clip_narrations + stage texts), enriched with
       topic/pillar/story_context/visual_plan/doi from 01_ideation/research_card.json and title/pillar from
       00_project_manifest.json.
    Raises FileNotFoundError when script.json is missing and ValueError when it holds no usable narration.
    """
    project_dir = Path(project_dir)
    catalog_item = _catalog_topic(project_dir.name)
    if catalog_item is not None:
        return dict(catalog_item)

    script_file = project_dir / "02_script" / "script.json"
    if not script_file.exists():
        raise FileNotFoundError(
            f"Cannot resolve topic for '{project_dir.name}': it is not in topics_catalog and {script_file} is missing."
        )
    script_data = _read_json_dict(script_file)
    item: dict[str, Any] = {"project_id": project_dir.name, **_script_stage_texts(script_data)}
    narrations = _script_clip_narrations(script_data)
    if narrations:
        item["clip_narrations"] = narrations
    elif not item["hook_text"]:
        raise ValueError(
            f"{script_file} has neither {CLIP_COUNT_MIN}-{CLIP_COUNT_MAX} clip_narrations nor stage texts."
        )

    research_card = _read_json_dict(project_dir / "01_ideation" / "research_card.json")
    for key in ("topic", "pillar", "title", "story_context", "visual_plan", "doi"):
        if research_card.get(key):
            item[key] = research_card[key]
    manifest = _read_json_dict(project_dir / "00_project_manifest.json")
    for key in ("title", "pillar"):
        if not item.get(key) and manifest.get(key):
            item[key] = manifest[key]
    item.setdefault("topic", item.get("title") or project_dir.name)
    return item


def _load_project_clip_scripts(project_dir: Path, topic_item: dict[str, Any] | None = None) -> list[str]:
    """
    Returns the per-clip narration strings for a project, in priority order:
    topic_item['clip_narrations'] -> 02_script/script.json clip_narrations -> topics_catalog clip_narrations
    (each must hold CLIP_COUNT_MIN..CLIP_COUNT_MAX entries). Legacy 4-stage projects without clip narrations
    fall back to the 5-clip split [hook, setup, core part 1, core part 2, payoff].
    """
    from pipeline.generator import ContentGenerator

    if topic_item:
        narrations = _clean_narrations(topic_item.get("clip_narrations"))
        if narrations:
            return narrations

    texts = {key: str((topic_item or {}).get(key) or "").strip() for key, _ in _STAGE_TEXT_KEYS}

    script_file = project_dir / "02_script" / "script.json"
    if script_file.exists():
        script_data = _read_json_dict(script_file)
        narrations = _script_clip_narrations(script_data)
        if narrations:
            return narrations
        for key, value in _script_stage_texts(script_data).items():
            texts[key] = texts[key] or value

    if not topic_item:
        catalog_item = _catalog_topic(project_dir.name)
        if catalog_item is not None:
            narrations = _clean_narrations(catalog_item.get("clip_narrations"))
            if narrations:
                return narrations
            for key in texts:
                texts[key] = texts[key] or str(catalog_item.get(key) or "").strip()

    core = texts["core_text"]
    act_nar, rev_nar = ContentGenerator.split_core_text(core) if core else ("", "")
    return [texts["hook_text"], texts["setup_text"], act_nar, rev_nar, texts["payoff_text"]]


def _native_audio_unavailable_reason(project_dir: Path, topic_item: dict[str, Any] | None) -> str:
    """Explains why extract_native_flow_clip_speech() returned None for a project."""
    clips_dir = project_dir / "03_visuals" / "flow_native_clips"
    n_clips = len(list(clips_dir.glob("clip_*.mp4"))) if clips_dir.exists() else 0
    n_expected = len(_load_project_clip_scripts(project_dir, topic_item=topic_item))
    if n_clips < n_expected:
        return f"{clips_dir} holds {n_clips} clip_*.mp4 file(s) but the script has {n_expected} clip narrations"
    return (
        f"fewer than {n_expected - 1} of {n_expected} native Flow clips contain detectable speech "
        "(active vocal level must exceed -36 dBFS)"
    )


def align_clip_phrases_to_vocal_envelope(
    clip_path: Path,
    trim_start: float,
    trim_end: float,
    clip_text: str,
    timeline_offset_sec: float,
    max_words_per_event: int = 5,
) -> list[tuple[float, float, list[str]]]:
    """
    Aligns a single clip's spoken narration to its actual 300Hz-3000Hz human vocal syllable bursts at 10ms resolution:
    1. Computes 50ms linear-RMS smoothed vocal envelope inside [trim_start, trim_end].
    2. Detects sentence pauses (when a clip has 2 sentences) and maps each sentence to its exact vocal span [sw0, sw1].
    3. Distributes phrase durations inside each sentence using bounded soft-vocal CDF + syllable weighting
       with a guaranteed minimum display duration (>= 0.48s) so no phrase ever flashes for 0.25s.
    """
    import numpy as np
    from pipeline.config import SUBPROCESS_TIMEOUT_SEC

    clip_dur_trimmed = max(1.0, float(trim_end) - float(trim_start))
    sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", clip_text.strip()) if s.strip()]
    if not sentences:
        sentences = [clip_text.strip()]

    sr = 16000
    win = 160  # 10ms window at 16kHz
    dt = 0.01
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i", str(clip_path.resolve()),
        "-vn", "-af", "highpass=f=750,lowpass=f=6000",
        "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1",
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SEC, check=False)

    if res.returncode != 0 or len(res.stdout) < sr:
        all_phrases = [p for s in sentences for p in _chunk_sentence_into_phrases(s, max_words=max_words_per_event)]
        total_syl = max(1, sum(_count_english_syllables(w) for p in all_phrases for w in p))
        events: list[tuple[float, float, list[str]]] = []
        cur_t = timeline_offset_sec + 0.08
        usable = max(0.8, clip_dur_trimmed - 0.16)
        for p in all_phrases:
            w_syl = sum(_count_english_syllables(w) for w in p)
            dur = usable * (w_syl / total_syl)
            events.append((round(cur_t, 2), round(cur_t + dur, 2), p))
            cur_t += dur
        return events

    pcm_full = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    i0 = max(0, min(len(pcm_full) - 1, int(round(trim_start * sr))))
    i1 = max(i0 + win * 10, min(len(pcm_full), int(round(trim_end * sr))))
    pcm = pcm_full[i0:i1]

    n_w = len(pcm) // win
    if n_w < 10:
        return [(round(timeline_offset_sec, 2), round(timeline_offset_sec + clip_dur_trimmed, 2), clip_text.split())]

    rms = np.sqrt(np.mean(np.square(pcm[: n_w * win].reshape(n_w, win)), axis=1) + 1e-9)
    kernel = np.ones(5, dtype=np.float32) / 5.0
    smooth_rms = np.convolve(rms, kernel, mode="same")
    smooth_db = 20.0 * np.log10(smooth_rms + 1e-9)

    p95 = float(np.percentile(smooth_db, 95))
    p15 = float(np.percentile(smooth_db, 15))
    core_thresh = max(-27.5, p95 - 9.5)
    edge_thresh = max(-29.8, min(p95 - 12.0, p15 + 3.2))
    act_core = np.where(smooth_db > core_thresh)[0]
    act_edge = np.where(smooth_db > edge_thresh)[0]

    if len(act_core) > 0:
        c0_idx = int(act_core[0])
        c1_idx = int(act_core[-1])
        w_start = c0_idx
        for k in range(c0_idx - 1, -1, -1):
            if smooth_db[k] > edge_thresh:
                w_start = k
            elif (w_start - k) > 30:
                break
        w_end = c1_idx + 1
        for k in range(c1_idx + 1, n_w):
            if smooth_db[k] > edge_thresh:
                w_end = k + 1
            elif (k - w_end) > 25:
                break
        w_start = max(0, w_start - 10)
        w_end = min(n_w, w_end + 18)
    elif len(act_edge) > 0:
        w_start = int(act_edge[0])
        w_end = int(act_edge[-1] + 1)
    else:
        w_start = 6
        w_end = max(10, n_w - 10)

    w_start = max(0, min(w_start, n_w - 8))
    w_end = max(w_start + 8, min(w_end, n_w))

    # Map sentences to sub-spans separated by the deepest internal pause(s)
    sent_spans: list[tuple[int, int]] = []
    if len(sentences) == 2 and (w_end - w_start) >= 120:
        syl_0 = sum(_count_english_syllables(w) for w in sentences[0].split())
        syl_1 = sum(_count_english_syllables(w) for w in sentences[1].split())
        expected_ratio = max(0.22, min(0.78, syl_0 / float(max(1, syl_0 + syl_1))))
        search_lo = w_start + int(0.20 * (w_end - w_start))
        search_hi = w_start + int(0.82 * (w_end - w_start))
        expected_w = w_start + int(expected_ratio * (w_end - w_start))

        is_quiet = smooth_db[search_lo:search_hi] <= (core_thresh - 1.5)
        best_pause: tuple[int, int] | None = None
        best_score = -1e9
        run_s = -1
        for idx_q, q_val in enumerate(is_quiet):
            abs_w = search_lo + idx_q
            if q_val:
                if run_s < 0:
                    run_s = abs_w
            else:
                if run_s >= 0:
                    run_len = abs_w - run_s
                    if run_len >= 12:  # >= 0.12s pause
                        mid_w = (run_s + abs_w) // 2
                        dist_pen = abs(mid_w - expected_w) / float(max(1, w_end - w_start))
                        sc = (run_len * 0.01) - (dist_pen * 1.2)
                        if sc > best_score:
                            best_score = sc
                            best_pause = (run_s, abs_w)
                    run_s = -1
        if run_s >= 0:
            run_len = search_hi - run_s
            if run_len >= 12:
                mid_w = (run_s + search_hi) // 2
                dist_pen = abs(mid_w - expected_w) / float(max(1, w_end - w_start))
                sc = (run_len * 0.01) - (dist_pen * 1.2)
                if sc > best_score:
                    best_pause = (run_s, search_hi)

        if best_pause is not None and (best_pause[0] - w_start) >= 40 and (w_end - best_pause[1]) >= 40:
            sent_spans = [(w_start, best_pause[0]), (best_pause[1], w_end)]

    if not sent_spans:
        vocal_w_all = np.where(
            smooth_db[w_start:w_end] > edge_thresh,
            np.clip((smooth_db[w_start:w_end] - edge_thresh) / 12.0, 0.30, 1.0),
            0.05,
        )
        cdf_all = np.cumsum(vocal_w_all)
        cdf_all = cdf_all / float(max(1e-9, cdf_all[-1]))
        sent_syls = [max(1, sum(_count_english_syllables(w) for w in s.split())) for s in sentences]
        tot_s_syl = float(sum(sent_syls))
        cur_w = w_start
        acc_syl = 0.0
        for s_i, s_syl in enumerate(sent_syls):
            acc_syl += s_syl
            if s_i == len(sentences) - 1:
                nxt_w = w_end
            else:
                frac = acc_syl / tot_s_syl
                rel_w = int(np.searchsorted(cdf_all, frac))
                nxt_w = max(cur_w + 25, min(w_end - 25, w_start + rel_w))
            sent_spans.append((cur_w, nxt_w))
            cur_w = nxt_w

    aligned_events: list[tuple[float, float, list[str]]] = []
    for sent_text, (sw0, sw1) in zip(sentences, sent_spans):
        phrases = _chunk_sentence_into_phrases(sent_text, max_words=max_words_per_event)
        if not phrases:
            continue
        seg_db = smooth_db[sw0:sw1]
        # Tighten [sw0, sw1] to the sentence's active vocal edge bounds
        s_act = np.where(seg_db > edge_thresh)[0]
        if len(s_act) >= 4:
            sw1 = sw0 + int(s_act[-1]) + 1
            sw0 = sw0 + int(s_act[0])
            seg_db = smooth_db[sw0:sw1]

        sent_dur = max(0.50 * len(phrases), (sw1 - sw0) * dt)
        sent_t0 = timeline_offset_sec + sw0 * dt
        sent_t1 = sent_t0 + sent_dur

        # Combine syllable count with soft vocal density so no single loud syllable warps timing
        p_syls = [max(2, sum(_count_english_syllables(w) for w in p)) for p in phrases]
        tot_p_syl = float(sum(p_syls))
        raw_durs = [sent_dur * (ps / tot_p_syl) for ps in p_syls]
        min_durs = [max(0.48, min(0.68, 0.14 * ps)) for ps in p_syls]
        if sum(min_durs) < sent_dur:
            deficit = sum(max(0.0, md - rd) for md, rd in zip(min_durs, raw_durs))
            if deficit > 0:
                surplus_total = sum(max(0.0, rd - md) for md, rd in zip(min_durs, raw_durs))
                adj_durs = []
                for md, rd in zip(min_durs, raw_durs):
                    if rd < md:
                        adj_durs.append(md)
                    elif surplus_total > 1e-6:
                        adj_durs.append(rd - deficit * ((rd - md) / surplus_total))
                    else:
                        adj_durs.append(rd)
                raw_durs = adj_durs

        cur_t = sent_t0
        if aligned_events and cur_t < aligned_events[-1][1]:
            cur_t = aligned_events[-1][1]
        for p_i, (p_words, p_dur) in enumerate(zip(phrases, raw_durs)):
            t0 = round(cur_t, 2)
            t1 = round(sent_t1 if p_i == len(phrases) - 1 else (cur_t + p_dur), 2)
            if t1 <= t0 + 0.35:
                t1 = round(t0 + 0.45, 2)
            aligned_events.append((t0, t1, p_words))
            cur_t = t1

    return aligned_events


def generate_ass_subtitles(
    topic_item: dict[str, Any],
    output_path: Path,
    speech_end_sec: float | None = None,
    project_dir: Path | None = None,
) -> Path:
    """
    Generates single-line Y=74% ASS subtitles (MarginV=440, 2-3 words per event, 86px Arial Black, 7px outline):
    - When the project's native Flow clips are present, each clip's narration is force-aligned to its vocal
      envelope (10ms resolution) inside the same speech window used by the audio master and the video cut
      list, then mapped onto the AV_SPEEDUP_FACTOR (1.08x) timeline.
    - One gold keyword (&H00D7FF&) per event with a 110% micro-pop.
    - Without aligned clips, phrases are distributed by syllable weight over [0.08s, speech_end_sec];
      speech_end_sec defaults to total words / EFFECTIVE_WPS.
    """
    project_id = str(topic_item.get("project_id") or output_path.parent.parent.name)

    highlight_keywords = {
        "neurons", "neuron", "cortex", "cortical", "striatum", "ganglia", "electrodes", "electrode",
        "phonemes", "phonetic", "silicon", "hemisphere", "hemispheres", "axonal", "axon", "frontal", "prefrontal",
        "ventromedial", "amygdala", "millivolt", "millivolts", "glymphatic", "cerebrospinal", "amyloid",
        "synapses", "synaptic", "synapse", "hippocampal", "hippocampus", "microchip", "thalamus",
        "conduits", "cingulate", "subcortical", "dopamine", "excerebration", "cardiocentric",
        "retina", "optic", "fusiform", "gyrus", "limbic", "orbital", "skull", "iron", "rod",
        "imposter", "delusion", "terror", "panic", "hostility", "rage", "severed", "shattered",
        "callosum", "corpus", "cochlea", "auditory", "myelin", "circuit", "circuits", "bridge",
        "nightmare", "instead", "stunned", "autopilot", "decoder", "sensors", "micro-sensors",
        "brake", "pedal", "cable", "cables", "filter", "wax", "alarm", "tape", "recorder",
        "forty-millivolt", "sixty-two", "thirty-nine", "twenty-eight", "fifteen", "eleven",
    }

    def _is_highlight_candidate(w: str) -> tuple[bool, int]:
        clean_w = re.sub(r"[^\w-]", "", w).lower()
        has_digit = any(ch.isdigit() for ch in w)
        if has_digit:
            return True, 100 + len(clean_w)
        if clean_w in highlight_keywords or ("-" in clean_w and any(p in highlight_keywords for p in clean_w.split("-"))):
            return True, 50 + len(clean_w)
        return False, 0

    def _format_phrase_lines(words_list: list[str]) -> str:
        # Highlight at most 1 keyword/number per 2-3 word burst in gold with a 110% micro-pop
        best_idx = -1
        best_prio = 0
        for idx_w, w in enumerate(words_list):
            ok_h, prio = _is_highlight_candidate(w)
            if ok_h and prio > best_prio:
                best_prio = prio
                best_idx = idx_w

        styled_tokens: list[str] = []
        for idx_w, w in enumerate(words_list):
            if idx_w == best_idx:
                styled_tokens.append(
                    f"{{\\c&H00D7FF&\\fscx110\\fscy110\\t(0,140,\\fscx100\\fscy100)}}{w}{{\\c&HFFFFFF&\\fscx100\\fscy100}}"
                )
            else:
                styled_tokens.append(w)

        if SUBTITLE_MAX_LINES <= 1:
            return " ".join(styled_tokens)

        plain_len = sum(len(w) for w in words_list) + max(0, len(words_list) - 1)
        if len(styled_tokens) >= 4 or (len(styled_tokens) >= 3 and plain_len > 20):
            best_split = len(styled_tokens) // 2
            return " ".join(styled_tokens[:best_split]) + "\\N" + " ".join(styled_tokens[best_split:])
        return " ".join(styled_tokens)

    if project_dir is None:
        cand_dir = output_path.parent.parent
        if (cand_dir / "03_visuals" / "flow_native_clips").exists():
            project_dir = cand_dir

    dialogue_lines: list[str] = []
    used_acoustic_alignment = False

    if project_dir is not None:
        clips_dir = project_dir / "03_visuals" / "flow_native_clips"
        clip_files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key) if clips_dir.exists() else []
        clip_scripts = _load_project_clip_scripts(project_dir, topic_item=topic_item)
        n_expected = len(clip_scripts)
        if CLIP_COUNT_MIN <= n_expected <= CLIP_COUNT_MAX and len(clip_files) >= n_expected:
            fps_int = int(VIDEO_FPS)
            pivot_clip_idx = pivot_clip_index(n_expected)
            timeline_cursor = 0.0
            for c_idx, (cf, c_text) in enumerate(zip(clip_files[:n_expected], clip_scripts)):
                win_info = measure_clip_speech_window(
                    cf,
                    expected_text=c_text,
                    is_first_clip=(c_idx == 0),
                    is_final_clip=(c_idx == n_expected - 1),
                    is_pre_pivot_clip=(c_idx == pivot_clip_idx - 1),
                )
                speedup = float(win_info.get("speedup_factor", AV_SPEEDUP_FACTOR))
                c_frames = max(30, int(round(float(win_info["trimmed_dur"]) * fps_int)))
                c_start_sec = timeline_cursor
                c_end_sec = timeline_cursor + c_frames / float(fps_int)

                src_trim_start = float(win_info["trim_start"])
                src_trim_end = float(win_info["trim_end"])
                active_spk_end_src = min(
                    src_trim_end,
                    max(src_trim_start + 1.4, float(win_info.get("speech_end") or src_trim_end)),
                )
                clip_events_src = align_clip_phrases_to_vocal_envelope(
                    clip_path=cf,
                    trim_start=src_trim_start,
                    trim_end=active_spk_end_src,
                    clip_text=c_text,
                    timeline_offset_sec=0.0,
                    max_words_per_event=SUBTITLE_MAX_WORDS_PER_EVENT,
                )
                prev_end = c_start_sec
                for rel_t0, rel_t1, p_words in clip_events_src:
                    t0 = round(max(prev_end, c_start_sec + (rel_t0 / speedup)), 2)
                    t1 = round(min(c_end_sec - 0.04, max(t0 + 0.36, c_start_sec + (rel_t1 / speedup))), 2)
                    if t1 <= t0 + 0.25:
                        t1 = round(min(c_end_sec, t0 + 0.36), 2)
                    prev_end = t1
                    text_formatted = _format_phrase_lines(p_words)
                    dialogue_lines.append(
                        f"Dialogue: 0,{_format_ass_time(t0)},{_format_ass_time(t1)},Default,,0,0,0,,{text_formatted}"
                    )
                timeline_cursor = c_end_sec
            if len(dialogue_lines) >= 10:
                used_acoustic_alignment = True
            else:
                dialogue_lines = []

    if not used_acoustic_alignment:
        narrations = _clean_narrations(topic_item.get("clip_narrations"))
        if narrations:
            full_text = " ".join(narrations)
        else:
            full_text = " ".join(str(topic_item.get(key) or "").strip() for key, _ in _STAGE_TEXT_KEYS).strip()
        if not full_text:
            raise ValueError(f"Topic '{project_id}' has no clip_narrations or stage texts to subtitle.")
        if speech_end_sec is None:
            speech_end_sec = round(len(full_text.split()) / EFFECTIVE_WPS, 2)
        sentences = [s.strip() for s in re.split(r"(?<=[.!?])\s+", full_text) if s.strip()]
        chunks: list[list[str]] = []
        for s in sentences:
            chunks.extend(_chunk_sentence_into_phrases(s, max_words=SUBTITLE_MAX_WORDS_PER_EVENT))

        total_syls = max(1, sum(_count_english_syllables(w) for c in chunks for w in c))
        start_offset = 0.08
        usable_dur = max(0.5, float(speech_end_sec) - start_offset)
        cursor = start_offset
        for idx, chunk in enumerate(chunks):
            c_syls = sum(_count_english_syllables(w) for w in chunk)
            dur = usable_dur * (c_syls / float(total_syls))
            t0 = cursor
            t1 = cursor + dur if idx < len(chunks) - 1 else start_offset + usable_dur
            cursor = t1
            text_formatted = _format_phrase_lines(chunk)
            dialogue_lines.append(
                f"Dialogue: 0,{_format_ass_time(t0)},{_format_ass_time(t1)},Default,,0,0,0,,{text_formatted}"
            )

    ass_content = f"""[Script Info]
Title: ALL ABOUT BRAIN - {project_id}
ScriptType: v4.00+
WrapStyle: 0
ScaledBorderAndShadow: yes
YCbCr Matrix: TV.601
PlayResX: {VIDEO_WIDTH}
PlayResY: {VIDEO_HEIGHT}

[V4+ Styles]
Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding
Style: Default,{SUBTITLE_FONT_NAME},{SUBTITLE_FONT_SIZE},&H00FFFFFF,&H0000D7FF,&H00000000,&H00000000,1,0,0,0,88,104,-1,0,1,{SUBTITLE_OUTLINE_WIDTH},{SUBTITLE_SHADOW_DEPTH},2,55,55,{SUBTITLE_MARGIN_V},1

[Events]
Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text
{chr(10).join(dialogue_lines)}
"""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(ass_content, encoding="utf-8")
    return output_path


def measure_clip_speech_window(
    clip_path: Path,
    expected_text: str = "",
    is_first_clip: bool = False,
    is_final_clip: bool = False,
    is_pre_pivot_clip: bool = False,
) -> dict[str, Any]:
    """
    Measures the active vocal window [speech_start, speech_end] inside one native Google Flow clip using a
    750Hz-6000Hz formant/consonant bandpass at 16kHz (rejects the clip's low ambient bed), then derives the
    trimmed source window and its exact output duration at AV_SPEEDUP_FACTOR:
    - Prompt-bleed cutoff: once the spoken time reaches the syllable-based expectation, a long enough pause
      (PROMPT_BLEED_CUTOFF_RULES) ends speech so hallucinated trailing prompt speech is excluded.
    - Soft sentence-end preservation: otherwise quiet trailing syllables above the soft-tail threshold are kept.
    - Onset: VOCAL_ONSET_PROTECT_SEC + VOCAL_ONSET_PAD_SEC before the first voiced edge; clips 2..N trim at least
      CLIP_PRE_ROLL_TRIM_SEC of pre-roll when speech starts later than that.
    - Post-speech hold: CLIP_VISUAL_HOLD_SEC, CLIP_PRE_PIVOT_HOLD_SEC before the pivot clip, FINAL_TAIL_SEC on the
      final clip.
    Returns has_speech=False with a fixed 6.12s source window when no speech is detected.
    """
    import numpy as np
    from pipeline.media_integrity import MediaIntegrityValidator

    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    probe = MediaIntegrityValidator.probe_streams(clip_path)
    clip_dur = float(probe.get("video_stream_duration_seconds") or probe.get("duration_seconds") or 8.0)
    fps_f = float(VIDEO_FPS)
    speedup = float(AV_SPEEDUP_FACTOR)

    def _no_speech_window() -> dict[str, Any]:
        fallback_src = min(clip_dur, 6.12)
        fallback_out = round(max(60, int(round((fallback_src / speedup) * fps_f))) / fps_f, 4)
        return {
            "has_speech": False,
            "clip_dur": clip_dur,
            "speech_start": 0.0,
            "speech_end": min(clip_dur, 6.0),
            "trim_start": 0.0,
            "trim_end": fallback_src,
            "src_trimmed_dur": fallback_src,
            "trimmed_dur": fallback_out,
            "speedup_factor": speedup,
            "broke_early": False,
        }

    cmd = [
        ffmpeg_exe, "-hide_banner", "-loglevel", "error",
        "-i", str(clip_path.resolve()),
        "-vn", "-af", "highpass=f=750,lowpass=f=6000",
        "-ac", "1", "-ar", "16000", "-f", "s16le", "pipe:1",
    ]
    res = subprocess.run(cmd, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SEC, check=False)
    if res.returncode != 0 or len(res.stdout) < 16000:
        return _no_speech_window()

    pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
    win = 160  # 10ms at 16kHz
    n_w = len(pcm) // win
    if n_w < 20:
        return _no_speech_window()

    rms = np.sqrt(np.mean(np.square(pcm[:n_w * win].reshape(n_w, win)), axis=1) + 1e-9)
    smooth_rms = np.convolve(rms, np.ones(5, dtype=np.float32) / 5.0, mode="same")
    db = 20.0 * np.log10(smooth_rms + 1e-9)
    p95 = float(np.percentile(db, 95))
    p15 = float(np.percentile(db, 15))
    core_thresh = max(-27.5, p95 - 9.5)
    edge_thresh = max(-29.8, min(p95 - 12.0, p15 + 3.2))

    # Group active windows above core_thresh into formant syllable bursts (>= 40ms, bridge <= 180ms)
    act_core = np.where(db > core_thresh)[0]
    clusters: list[tuple[int, int]] = []
    if len(act_core) > 0:
        c0 = prev = int(act_core[0])
        for idx_val in act_core[1:]:
            iv = int(idx_val)
            if iv - prev > 18:  # > 180ms gap
                if prev - c0 >= 4:  # >= 40ms syllable burst
                    clusters.append((c0, prev))
                c0 = iv
            prev = iv
        if prev - c0 >= 4:
            clusters.append((c0, prev))

    if not (p95 > -32.0 and clusters):
        return _no_speech_window()

    if expected_text:
        tot_syl = sum(_count_english_syllables(w) for w in expected_text.split())
    else:
        tot_syl = PROMPT_BLEED_DEFAULT_SYLLABLES
    full_exp_sec = max(PROMPT_BLEED_MIN_EXPECTED_SEC, tot_syl * PROMPT_BLEED_SYLLABLE_SEC)

    if len(clusters) >= 3:
        # Drop an isolated leading blip (<= 0.75s burst followed by >= 1.25s silence) before the real narration
        c0_dur = (clusters[0][1] - clusters[0][0]) * 0.01
        gap0_sec = (clusters[1][0] - clusters[0][1]) * 0.01
        rem_span_sec = (clusters[-1][1] - clusters[1][0]) * 0.01
        if c0_dur <= 0.75 and gap0_sec >= 1.25 and rem_span_sec >= max(4.5, full_exp_sec * 0.80):
            clusters = clusters[1:]

    first_w = clusters[0][0]
    last_w = clusters[0][1]
    broke_early = False
    excess_pause_sec = 0.0
    for c_start, c_end in clusters[1:]:
        gap_sec = (c_start - last_w) * 0.01
        dur_so_far = ((last_w - first_w) * 0.01) - excess_pause_sec
        # Prompt-bleed cutoff: stop before post-script hallucinated speech once the expected syllables were spoken
        if any(
            dur_so_far >= full_exp_sec * ratio and gap_sec >= min_gap
            for ratio, min_gap in PROMPT_BLEED_CUTOFF_RULES
        ):
            broke_early = True
            break
        if gap_sec > PROMPT_BLEED_PAUSE_ALLOWANCE_SEC:
            excess_pause_sec += (gap_sec - PROMPT_BLEED_PAUSE_ALLOWANCE_SEC)
        last_w = c_end

    ext_start = first_w
    for k in range(first_w - 1, -1, -1):
        if db[k] > edge_thresh:
            ext_start = k
        elif (ext_start - k) > 35:
            break

    ext_end = last_w + 1
    if broke_early:
        # Strict stop before the post-script pause so trailing hallucinated prompt speech is never included
        for k in range(last_w + 1, n_w):
            if db[k] > edge_thresh:
                ext_end = k + 1
            elif (k - ext_end) > 14:
                break
        end_pad = SPEECH_END_PAD_BROKE_EARLY_SEC
    else:
        # Soft sentence-end preservation: keep quiet trailing syllables (e.g. 'begins', 'eyes', 'nightmare')
        soft_tail_thresh = max(
            SOFT_TAIL_FLOOR_DB,
            min(p95 - SOFT_TAIL_P95_OFFSET_DB, p15 + SOFT_TAIL_P15_OFFSET_DB),
        )
        search_windows = int(round(SOFT_TAIL_SEARCH_SEC * 100))
        max_gap_windows = int(round(SOFT_TAIL_MAX_GAP_SEC * 100))
        for k in range(last_w + 1, min(n_w, last_w + search_windows)):
            if db[k] > soft_tail_thresh:
                ext_end = k + 1
            elif (k - ext_end) > max_gap_windows:
                break
        end_pad = SPEECH_END_PAD_SEC

    # Protect low-frequency /w/ onsets below 750Hz, then apply the tight pre-speech pad
    s0 = round(max(0.0, (ext_start * 0.01) - VOCAL_ONSET_PROTECT_SEC), 3)
    s1 = round(min(clip_dur, (ext_end * 0.01) + end_pad), 3)
    trim_start = round(max(0.0, s0 - VOCAL_ONSET_PAD_SEC), 3)
    if not is_first_clip and s0 >= CLIP_PRE_ROLL_TRIM_SEC and trim_start < CLIP_PRE_ROLL_TRIM_SEC:
        trim_start = round(min(s0, CLIP_PRE_ROLL_TRIM_SEC), 3)

    if is_final_clip:
        tail_pad = float(FINAL_TAIL_SEC)
    elif is_pre_pivot_clip:
        tail_pad = float(CLIP_PRE_PIVOT_HOLD_SEC)
    else:
        tail_pad = float(CLIP_VISUAL_HOLD_SEC)

    # Audio-first master clock: the window may extend slightly past clip_dur when speech ends near the clip end
    # (video clone-pads the last frame via tpad, audio adds a clean silence tail)
    desired_end = s1 + tail_pad
    trim_end = round(min(clip_dur, desired_end), 4)
    extra_tail_sec = round(max(0.0, desired_end - clip_dur), 4)
    src_raw_dur = max(2.2, (trim_end - trim_start) + extra_tail_sec)
    out_raw_dur = src_raw_dur / speedup
    c_frames = max(60, int(round(out_raw_dur * fps_f)))
    out_exact_dur = round(c_frames / fps_f, 4)
    src_trimmed_dur = round(trim_end - trim_start, 4)
    return {
        "has_speech": True,
        "clip_dur": clip_dur,
        "speech_start": s0,
        "speech_end": s1,
        "trim_start": trim_start,
        "trim_end": trim_end,
        "src_trimmed_dur": src_trimmed_dur,
        "trimmed_dur": out_exact_dur,
        "speedup_factor": speedup,
        "broke_early": broke_early,
    }


def _vocal_filter_chain(t_in: float, t_out: float, speedup: float) -> str:
    """Builds the native-voice ffmpeg chain: trim -> bandpass -> 3-band EQ -> compressor -> atempo."""
    lo_hz, hi_hz = VOCAL_BANDPASS_HZ
    eq_chain = ",".join(f"equalizer=f={f_hz}:t=q:w={width_q}:g={gain_db}" for f_hz, width_q, gain_db in VOCAL_EQ_BANDS)
    comp = VOCAL_COMPRESSOR
    compressor = (
        f"acompressor=threshold={comp['threshold_db']}dB:ratio={comp['ratio']}:"
        f"attack={comp['attack_ms']}:release={comp['release_ms']}:makeup={comp['makeup_db']}dB"
    )
    return (
        f"atrim=start={t_in:.4f}:end={t_out:.4f},asetpts=PTS-STARTPTS,"
        f"highpass=f={lo_hz},lowpass=f={hi_hz},"
        f"{eq_chain},"
        f"{compressor},"
        f"atempo={speedup:.4f}"
    )


def extract_native_flow_clip_speech(
    project_dir: Path,
    sr: int = 48000,
    return_windows: bool = False,
    topic_item: dict[str, Any] | None = None,
) -> Any | None:
    """
    Extracts and concatenates the native Google Flow voiceover from
    03_visuals/flow_native_clips/clip_1.mp4 .. clip_N.mp4 (CLIP_COUNT_MIN <= N <= CLIP_COUNT_MAX) at AV_SPEEDUP_FACTOR:
    - Per clip: bandpass + 3-band EQ + 3.5:1 compressor (VOCAL_* constants) and pitch-preserving atempo.
    - A raised-cosine vocal envelope over [speech_start, speech_end] keeps inter-clip holds free of trailing or
      hallucinated speech without truncating sentence-final words.
    - +2.5 dB vocal presence lift from the pivot clip (pivot_clip_index) onward.
    - The final clip ends with an END_FADE_SEC ramp to silence.
    Returns None when clips are missing or fewer than N-1 clips contain speech.
    """
    import numpy as np

    clips_dir = project_dir / "03_visuals" / "flow_native_clips"
    if not clips_dir.exists():
        return None
    clip_files = sorted(clips_dir.glob("clip_*.mp4"), key=numeric_clip_sort_key)
    clip_scripts = _load_project_clip_scripts(project_dir, topic_item=topic_item)
    n_expected = len(clip_scripts)
    if not (CLIP_COUNT_MIN <= n_expected <= CLIP_COUNT_MAX) or len(clip_files) < n_expected:
        return None

    pivot_clip_idx = pivot_clip_index(n_expected)
    ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
    fps_int = int(VIDEO_FPS)
    segments: list[np.ndarray] = []
    windows: list[dict[str, Any]] = []
    active_clips = 0
    eps = 1e-9

    for c_idx, cf in enumerate(clip_files[:n_expected]):
        win_info = measure_clip_speech_window(
            cf,
            expected_text=clip_scripts[c_idx],
            is_first_clip=(c_idx == 0),
            is_final_clip=(c_idx == n_expected - 1),
            is_pre_pivot_clip=(c_idx == pivot_clip_idx - 1),
        )
        speedup = float(win_info.get("speedup_factor", AV_SPEEDUP_FACTOR))
        c_frames = max(30, int(round(float(win_info["trimmed_dur"]) * fps_int)))
        exact_dur = c_frames / float(fps_int)
        target_samples = int(round(exact_dur * sr))
        t_in = float(win_info["trim_start"])
        t_out = float(win_info["trim_end"])

        cmd = [
            ffmpeg_exe, "-hide_banner", "-loglevel", "error",
            "-i", str(cf.resolve()),
            "-vn", "-af", _vocal_filter_chain(t_in, t_out, speedup),
            "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1",
        ]
        res = subprocess.run(cmd, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SEC, check=False)
        if res.returncode != 0 or len(res.stdout) <= sr // 2:
            cmd_raw = [
                ffmpeg_exe, "-hide_banner", "-loglevel", "error",
                "-i", str(cf.resolve()),
                "-vn", "-af", f"atrim=start={t_in:.4f}:end={t_out:.4f},asetpts=PTS-STARTPTS,atempo={speedup:.4f}",
                "-ac", "1", "-ar", str(sr), "-f", "s16le", "pipe:1",
            ]
            res = subprocess.run(cmd_raw, capture_output=True, timeout=SUBPROCESS_TIMEOUT_SEC, check=False)

        if res.returncode == 0 and len(res.stdout) > sr // 2:
            pcm = np.frombuffer(res.stdout, dtype=np.int16).astype(np.float32) / 32768.0
            sliced = pcm.copy()
            if len(sliced) < target_samples:
                sliced = np.pad(sliced, (0, target_samples - len(sliced)))
            elif len(sliced) > target_samples:
                sliced = sliced[:target_samples]

            # Raised-cosine vocal envelope over [speech_start, speech_end] mapped to the sped-up timeline
            rel_s0 = max(0.0, (float(win_info["speech_start"]) - t_in) / speedup)
            rel_s1 = min(exact_dur, (float(win_info["speech_end"]) - t_in) / speedup)
            idx_s0 = max(0, int(round(rel_s0 * sr)))
            idx_s1 = min(len(sliced), int(round(rel_s1 * sr)))
            if idx_s1 > idx_s0 + int(0.20 * sr):
                vocal_env = np.zeros(len(sliced), dtype=np.float32)
                vocal_env[idx_s0:idx_s1] = 1.0
                fi_n = min(idx_s0, int(0.06 * sr))
                if fi_n > 0:
                    vocal_env[idx_s0 - fi_n : idx_s0] = 0.5 * (
                        1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, fi_n, dtype=np.float32))
                    )
                fo_dur = 0.08 if win_info.get("broke_early") else 0.18
                fo_n = min(len(sliced) - idx_s1, int(fo_dur * sr))
                if fo_n > 0:
                    vocal_env[idx_s1 : idx_s1 + fo_n] = 0.5 * (
                        1.0 + np.cos(np.pi * np.linspace(0.0, 1.0, fo_n, dtype=np.float32))
                    )
                sliced *= vocal_env

            active_mask = np.abs(sliced) > 0.022
            if np.any(active_mask):
                act_rms = float(np.sqrt(np.mean(np.square(sliced[active_mask])) + eps))
            else:
                act_rms = float(np.sqrt(np.mean(np.square(sliced)) + eps))
            db = 20.0 * float(np.log10(max(act_rms, eps)))
            if db > -36.0 and win_info["has_speech"]:
                active_clips += 1
                # +2.5 dB vocal presence lift from the pivot clip onward
                target_db = -12.2 if c_idx >= pivot_clip_idx else -14.7
                target_rms = 10.0 ** (target_db / 20.0)
                sliced = np.tanh(sliced * (target_rms / act_rms) * 1.12) * 0.90

            # Smooth raised-cosine (S-curve) fades at clip boundaries
            fade_in_n = min(len(sliced) // 6, int(0.04 * sr))
            fade_out_n = min(len(sliced) // 4, int((0.08 if c_idx == n_expected - 1 else 0.04) * sr))
            if fade_in_n > 0:
                s_in = 0.5 * (1.0 - np.cos(np.pi * np.linspace(0.0, 1.0, fade_in_n, dtype=np.float32)))
                sliced[:fade_in_n] *= s_in
            if fade_out_n > 0:
                s_out = 0.5 * (1.0 + np.cos(np.pi * np.linspace(0.0, 1.0, fade_out_n, dtype=np.float32)))
                sliced[-fade_out_n:] *= s_out
            end_fade_n = int(END_FADE_SEC * sr)
            if c_idx == n_expected - 1 and len(sliced) > end_fade_n + int(0.015 * sr):
                # Clean end: keeps the last-100ms level of the final master below the truncation threshold
                sliced[-end_fade_n:] *= np.linspace(0.20, 0.0, end_fade_n, dtype=np.float32)

            win_info["trimmed_dur"] = round(exact_dur, 4)
            win_info["pivot_clip_idx"] = pivot_clip_idx
            segments.append(sliced)
            windows.append(win_info)

    if active_clips >= (n_expected - 1) and len(segments) == n_expected:
        concat_pcm = np.concatenate(segments)
        if return_windows:
            return concat_pcm, windows
        return concat_pcm
    return None


def generate_audio_master_wav(
    topic_item: dict[str, Any] | None = None,
    output_path: Path | None = None,
    force: bool = False,
    precomputed_native_res: tuple[Any, list[dict[str, Any]]] | None = None,
) -> Path:
    """
    Renders the 48kHz stereo audio master from the native Google Flow clip voices (4 layers):
    - Layer 1 (voice): extract_native_flow_clip_speech() output (EQ, 3.5:1 compression, 1.08x atempo,
      +2.5 dB lift from the pivot clip).
    - Layer 2 (synth bed, sidechain-ducked under speech):
      * Phase 1 (0 .. pivot start): 216/432/108 Hz tension drone + 120 BPM clock tick + 68 BPM heartbeat sub-bass.
      * Phase 2 (pivot start .. end): 132 BPM synth-pulse arpeggio (432 -> 540 -> 648 -> 864 Hz) over the drone.
    - Layer 3 (Foley): action-synced transient ~0.48s into clips 1..N-1, a low transition pulse at each cut, and a
      latch click + 864/1080/1296/1728 Hz chime chord at the pivot cut.
    - Layer 4 (UI tick): 15ms 2.6/5.2 kHz tick at every clip cut point and the pivot clip start.
    The final MASTER_TAIL_MUTE_SEC is ramped to silence across all layers.
    Raises RuntimeError when native clip speech cannot be extracted (no local TTS fallback).
    """
    import wave
    import numpy as np

    if output_path is None:
        raise ValueError("output_path is required")
    if output_path.exists() and output_path.stat().st_size > 100_000 and not force:
        return output_path

    output_path.parent.mkdir(parents=True, exist_ok=True)
    sr = 48000
    project_dir = output_path.parent.parent

    native_res = precomputed_native_res if precomputed_native_res is not None else extract_native_flow_clip_speech(project_dir, sr=sr, return_windows=True, topic_item=topic_item)
    if native_res is None:
        raise RuntimeError(
            f"Native Google Flow clip speech unavailable for '{project_dir.name}': "
            f"{_native_audio_unavailable_reason(project_dir, topic_item)}."
        )
    native_pcm, clip_windows = native_res
    total_samples = len(native_pcm)
    speech_track = native_pcm.astype(np.float32)

    t = np.arange(total_samples, dtype=np.float32) / sr
    n_clips = len(clip_windows)
    pivot_clip_idx = pivot_clip_index(n_clips)
    pivot_sec = float(sum(float(w["trimmed_dur"]) for w in clip_windows[:pivot_clip_idx]))

    # Layer 2A — Phase 1 (0 .. pivot_sec): tension drone + 120 BPM clock tick + 68 BPM heartbeat sub-bass
    phase1_drone = (
        0.48 * np.sin(2.0 * np.pi * 216.0 * t)
        + 0.32 * np.sin(2.0 * np.pi * 432.0 * t)
        + 0.20 * np.sin(2.0 * np.pi * 108.0 * t)
    ).astype(np.float32)
    hb_period = 60.0 / 68.0
    hb_phase = np.mod(t, hb_period)
    hb_env = (
        np.exp(-((hb_phase - 0.08) / 0.035) ** 2)
        + 0.65 * np.exp(-((hb_phase - 0.24) / 0.045) ** 2)
    ).astype(np.float32)
    tick_period = 0.50  # 120 BPM clock-tick pulse
    tick_phase = np.mod(t, tick_period)
    tick_env = np.exp(-tick_phase / 0.008).astype(np.float32)
    clock_tick = 0.35 * tick_env * np.sin(2.0 * np.pi * 2400.0 * t).astype(np.float32)
    phase1_bed = phase1_drone + 1.35 * hb_env * np.sin(2.0 * np.pi * 58.0 * t).astype(np.float32) + clock_tick

    # Layer 2B — Phase 2 (pivot_sec .. end): 132 BPM synth-pulse arpeggio (432 -> 540 -> 648 -> 864 Hz)
    step_sec = (60.0 / 132.0) / 2.0  # 8th-note pulse (~0.227s)
    rel_t = np.maximum(0.0, t - pivot_sec)
    step_idx = np.floor(rel_t / step_sec).astype(np.int32) % 4
    arp_freqs = np.choose(step_idx, [432.0, 540.0, 648.0, 864.0]).astype(np.float32)
    note_pos = np.mod(rel_t, step_sec)
    note_env = (np.exp(-note_pos / 0.095) * np.minimum(1.0, note_pos / 0.008)).astype(np.float32)
    phase2_arp = (
        0.55 * np.sin(2.0 * np.pi * arp_freqs * rel_t) * note_env
        + 0.42 * np.sin(2.0 * np.pi * 432.0 * t)
        + 0.36 * np.sin(2.0 * np.pi * 216.0 * t)
        + 0.22 * np.sin(2.0 * np.pi * 108.0 * t)
    ).astype(np.float32)

    bgm_raw = np.where(t < pivot_sec, phase1_bed, phase2_arp).astype(np.float32)

    # Sidechain ducking (-39 dBFS during speech, -24 dBFS in micro-pauses so pauses never read as dead air)
    win_50 = int(sr * 0.05)
    n_wins = max(1, total_samples // win_50)
    speech_wins = speech_track[:n_wins * win_50].reshape((n_wins, win_50))
    win_rms = np.sqrt(np.mean(np.square(speech_wins), axis=1) + 1e-9)
    duck_gains = np.where(win_rms > 0.02, 0.014, 0.045).astype(np.float32)
    kernel = np.ones(5, dtype=np.float32) / 5.0
    drone_env = np.repeat(np.convolve(duck_gains, kernel, mode="same"), win_50)
    if len(drone_env) < total_samples:
        drone_env = np.pad(drone_env, (0, total_samples - len(drone_env)), mode="edge")

    # Layer 3 — Action-synced Foley (~0.48s into clips 1..N-1) + cut transition pulses + pivot latch & chime
    foley_track = np.zeros(total_samples, dtype=np.float32)
    cut_times: list[float] = []
    cursor_sec = 0.0
    for c_i, w_info in enumerate(clip_windows):
        c_dur = float(w_info["trimmed_dur"])
        c_start = cursor_sec
        c_end = cursor_sec + c_dur
        cursor_sec = c_end

        f_sec = c_start + min(0.48, c_dur * 0.22)
        f0_idx = max(0, min(total_samples - 1, int(round(f_sec * sr))))
        if c_i < 2:
            # Setup / symptom: crisp mechanical snap + spark transient
            f_len = min(int(0.08 * sr), total_samples - f0_idx)
            if f_len > 20:
                ft = np.linspace(0.0, f_len / sr, f_len, dtype=np.float32)
                f_env = np.exp(-ft / 0.014)
                foley_track[f0_idx : f0_idx + f_len] += 0.045 * (
                    np.sin(2.0 * np.pi * 1850.0 * ft)
                    + 0.7 * np.sin(2.0 * np.pi * 3400.0 * ft)
                    + 0.8 * np.sin(2.0 * np.pi * 95.0 * ft)
                ) * f_env
        elif c_i < pivot_clip_idx:
            # Failure / crisis: low static crackle + 62Hz crisis thud
            f_len = min(int(0.14 * sr), total_samples - f0_idx)
            if f_len > 20:
                ft = np.linspace(0.0, f_len / sr, f_len, dtype=np.float32)
                f_env = np.maximum(0.0, np.sin(np.pi * (ft / (f_len / sr)))) ** 1.5
                foley_track[f0_idx : f0_idx + f_len] += 0.042 * (
                    np.sin(2.0 * np.pi * 62.0 * ft) + 0.35 * np.sin(2.0 * np.pi * 1420.0 * ft)
                ) * f_env
        elif c_i < n_clips - 1:
            # Pivot / mechanism / breakthrough: 3 rapid telemetry clicks (45ms apart)
            for burst_k in range(3):
                b_idx = f0_idx + int(burst_k * 0.045 * sr)
                b_len = min(int(0.022 * sr), total_samples - b_idx)
                if b_len > 10:
                    bt = np.linspace(0.0, b_len / sr, b_len, dtype=np.float32)
                    b_env = np.exp(-bt / 0.005)
                    foley_track[b_idx : b_idx + b_len] += 0.040 * (
                        np.sin(2.0 * np.pi * 2450.0 * bt) + 0.6 * np.sin(2.0 * np.pi * 3680.0 * bt)
                    ) * b_env

        if c_i < n_clips - 1:
            cut_times.append(c_end)
            p_center = int(round(c_end * sr))
            if c_i == pivot_clip_idx - 1:
                # Pivot latch click + harmonic chime chord
                click_n = int(0.06 * sr)
                c0 = max(0, p_center - click_n)
                if p_center > c0 + 10:
                    ct = np.linspace(0.0, 0.06, p_center - c0, dtype=np.float32)
                    c_env = np.exp(-ct / 0.012)
                    foley_track[c0:p_center] += 0.060 * (
                        np.sin(2.0 * np.pi * 1950.0 * ct) + 0.65 * np.sin(2.0 * np.pi * 920.0 * ct)
                    ) * c_env
                chime_n = int(0.55 * sr)
                ch1 = min(total_samples, p_center + chime_n)
                if ch1 > p_center + 100:
                    cht = np.linspace(0.0, (ch1 - p_center) / sr, ch1 - p_center, dtype=np.float32)
                    ch_env = np.minimum(1.0, cht / 0.006) * np.exp(-cht / 0.18)
                    chime_wave = (
                        0.45 * np.sin(2.0 * np.pi * 864.0 * cht)
                        + 0.30 * np.sin(2.0 * np.pi * 1080.0 * cht)
                        + 0.25 * np.sin(2.0 * np.pi * 1296.0 * cht)
                        + 0.15 * np.sin(2.0 * np.pi * 1728.0 * cht)
                    ) * ch_env
                    sub_hit = 0.055 * np.sin(2.0 * np.pi * 68.0 * cht) * np.exp(-cht / 0.11)
                    foley_track[p_center:ch1] += (0.052 * chime_wave + sub_hit).astype(np.float32)
            else:
                p_half = int(0.06 * sr)
                p0 = max(0, p_center - p_half)
                p1 = min(total_samples, p_center + p_half)
                if p1 > p0 + 60:
                    pt = np.linspace(0.0, (p1 - p0) / sr, p1 - p0, dtype=np.float32)
                    p_env = np.sin(np.pi * (pt / ((p1 - p0) / sr))) ** 2
                    foley_track[p0:p1] += 0.032 * np.sin(2.0 * np.pi * 64.0 * pt) * p_env

    # Layer 4 — UI tick (15ms 2.6kHz/5.2kHz) at every clip cut point plus the pivot clip start
    ui_tick_track = np.zeros(total_samples, dtype=np.float32)
    ui_tick_times = sorted({round(c, 4) for c in cut_times} | {round(pivot_sec, 4)})
    tick_len = int(0.015 * sr)
    for ut_sec in ui_tick_times:
        u0 = max(0, min(total_samples - tick_len - 1, int(round(ut_sec * sr))))
        if u0 < total_samples - int(0.12 * sr):
            ut = np.linspace(0.0, 0.015, tick_len, dtype=np.float32)
            u_env = np.minimum(1.0, ut / 0.002) * np.exp(-ut / 0.004)
            ui_tick_track[u0 : u0 + tick_len] += 0.055 * (
                0.65 * np.sin(2.0 * np.pi * 2600.0 * ut) + 0.35 * np.sin(2.0 * np.pi * 5200.0 * ut)
            ) * u_env

    mixed_mono = speech_track + bgm_raw * drone_env + foley_track + ui_tick_track
    # Linear mute over the final MASTER_TAIL_MUTE_SEC across all 4 layers (last-100ms level check)
    tail_mute_n = min(total_samples // 4, int(MASTER_TAIL_MUTE_SEC * sr))
    if tail_mute_n > 0:
        mixed_mono[-tail_mute_n:] *= np.linspace(1.0, 0.0, tail_mute_n, dtype=np.float32)
    mixed_mono = np.nan_to_num(mixed_mono, nan=0.0, posinf=0.0, neginf=0.0)
    mixed_mono = np.clip(mixed_mono, -0.98, 0.98)
    stereo_pcm = np.column_stack((mixed_mono, mixed_mono)).flatten()
    pcm_int16 = (stereo_pcm * 32767.0).astype(np.int16)

    with wave.open(str(output_path.resolve()), "wb") as wf:
        wf.setnchannels(2)
        wf.setsampwidth(2)
        wf.setframerate(sr)
        wf.writeframes(pcm_int16.tobytes())

    return output_path


def assemble_final_shorts_video(
    storage: ProjectStorage,
    force: bool = False,
    topic_item: dict[str, Any] | None = None,
) -> Path:
    """
    Renders the 1080x1920 @ 30fps Short from the project's 5-10 native Google Flow clips:
    - Every clip in 03_visuals/flow_native_clips (>= MIN_CLIP_SIZE_BYTES) must pass MediaIntegrityValidator.
    - Each clip's video and native voice are trimmed to the same measured speech window and sped up
      AV_SPEEDUP_FACTOR (setpts / atempo) so lip-sync and cuts stay frame-locked; native Flow colour is untouched.
    - audio_master.wav and subtitles.ass are regenerated on every render; 05_assembly/concat_list.txt records the
      per-clip in point and output-timeline duration used for cut-sync auditing.
    Raises RuntimeError ("FATAL ERROR [Anti-Placeholder Policy]") for missing/invalid clips and RuntimeError when
    native clip speech cannot be extracted.
    """
    from pipeline.media_integrity import MediaIntegrityValidator

    assembly_dir = storage.get_stage_dir("05_assembly")
    final_video_path = assembly_dir / "final_shorts_1080x1920.mp4"
    if final_video_path.exists() and final_video_path.stat().st_size >= MIN_CLIP_SIZE_BYTES and not force:
        return final_video_path

    clips_dir = storage.project_dir / "03_visuals" / "flow_native_clips"
    raw_candidates = (
        sorted(
            (f for f in clips_dir.glob("clip_*.mp4") if f.is_file() and f.stat().st_size >= MIN_CLIP_SIZE_BYTES),
            key=numeric_clip_sort_key,
        )
        if clips_dir.exists()
        else []
    )
    if len(raw_candidates) < MIN_CLIPS_FOR_ASSEMBLY:
        raise RuntimeError(
            f"FATAL ERROR [Anti-Placeholder Policy]: {len(raw_candidates)} valid Google Flow clip(s) "
            f"(>= {MIN_CLIP_SIZE_BYTES} bytes) found in {clips_dir}; at least {MIN_CLIPS_FOR_ASSEMBLY} are required. "
            "Placeholder, stretched or frozen video is prohibited."
        )

    receipt_file = storage.project_dir / "03_visuals" / "flow_provenance_receipt.json"
    if not receipt_file.exists():
        for clip in raw_candidates:
            try:
                MediaIntegrityValidator.verify_not_synthetic_derivative(clip, strict=True)
                MediaIntegrityValidator.validate_video_file(
                    clip,
                    min_size_bytes=MIN_CLIP_SIZE_BYTES,
                    require_30s_shorts=False,
                    check_motion=True,
                    check_audio=False,
                )
            except Exception as exc:
                raise RuntimeError(
                    f"FATAL ERROR [Anti-Placeholder Policy]: Clip '{clip.name}' in {storage.project_id} "
                    f"failed MediaIntegrityValidator: {exc}"
                ) from exc

    if topic_item is None:
        topic_item = resolve_topic_item(storage.project_dir)

    fps_int = int(VIDEO_FPS)
    audio_dir = storage.get_stage_dir("04_audio")
    audio_path = audio_dir / "audio_master.wav"
    ass_path = audio_dir / "subtitles.ass"

    native_res = extract_native_flow_clip_speech(storage.project_dir, sr=48000, return_windows=True, topic_item=topic_item)
    if native_res is None:
        raise RuntimeError(
            f"Native Google Flow clip speech unavailable for '{storage.project_id}': "
            f"{_native_audio_unavailable_reason(storage.project_dir, topic_item)}."
        )
    _native_pcm, clip_windows = native_res
    clip_candidates = raw_candidates[: len(clip_windows)]

    generate_audio_master_wav(topic_item=topic_item, output_path=audio_path, force=True, precomputed_native_res=native_res)
    total_speech_sec = round(sum(float(w["trimmed_dur"]) for w in clip_windows), 2)
    generate_ass_subtitles(topic_item, ass_path, speech_end_sec=total_speech_sec, project_dir=storage.project_dir)
    clip_frame_targets = [max(30, int(round(float(w["trimmed_dur"]) * fps_int))) for w in clip_windows]
    target_total_frames = sum(clip_frame_targets)
    target_total_dur = round(target_total_frames / float(fps_int), 3)

    concat_file = assembly_dir / "concat_list.txt"
    with open(concat_file, "w", encoding="utf-8") as f:
        for clip, c_frames, w_info in zip(clip_candidates, clip_frame_targets, clip_windows):
            # outpoint - inpoint = the clip's duration on the output (sped-up) timeline
            in_pt = round(float(w_info["trim_start"]), 3)
            out_pt = round(in_pt + (c_frames / float(fps_int)), 3)
            f.write(f"file '{clip.resolve().as_posix()}'\n")
            f.write(f"inpoint {in_pt}\n")
            f.write(f"outpoint {out_pt}\n")
    storage.record_artifact("05_assembly", "concat_list.txt", concat_file)

    ffmpeg_exe = MediaIntegrityValidator.get_ffmpeg_exe()

    import os
    import tempfile
    use_local_tmp = os.name != "nt" and Path("/tmp").exists()
    tmp_stage_dir = Path(tempfile.mkdtemp(prefix=f"bci_enc_{storage.project_id}_", dir="/tmp")) if use_local_tmp else assembly_dir
    try:
        local_clips: list[Path] = []
        for idx, clip in enumerate(clip_candidates):
            if use_local_tmp:
                lc = tmp_stage_dir / f"clip_{idx + 1}.mp4"
                shutil.copy2(clip, lc)
                local_clips.append(lc)
            else:
                local_clips.append(clip)
        if use_local_tmp:
            local_audio = tmp_stage_dir / "audio_master.wav"
            shutil.copy2(audio_path, local_audio)
            local_ass = tmp_stage_dir / "subtitles.ass"
            shutil.copy2(ass_path, local_ass)
            tmp_final_video_path = tmp_stage_dir / "final_shorts_1080x1920.mp4"
        else:
            local_audio = audio_path
            local_ass = ass_path
            tmp_final_video_path = final_video_path

        input_args: list[str] = []
        filter_parts: list[str] = []
        concat_inputs: list[str] = []
        for idx, (clip, c_frames, w_info) in enumerate(zip(local_clips, clip_frame_targets, clip_windows)):
            input_args.extend(["-i", str(clip.resolve())])
            t_in = float(w_info["trim_start"])
            t_out = float(w_info["trim_end"])
            speedup = float(w_info.get("speedup_factor", AV_SPEEDUP_FACTOR))
            filter_parts.append(
                f"[{idx}:v]trim=start={t_in:.3f}:end={t_out:.3f},setpts=(PTS-STARTPTS)/{speedup:.4f},"
                f"fps={fps_int},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                f"tpad=stop_mode=clone:stop_duration=0.6,"
                f"trim=start_frame=0:end_frame={c_frames},setpts=PTS-STARTPTS,"
                f"format=yuv420p,setsar=1[v{idx}]"
            )
            concat_inputs.append(f"[v{idx}]")

        audio_input_idx = len(local_clips)
        input_args.extend(["-i", str(local_audio.resolve())])

        filter_parts.append(f"{''.join(concat_inputs)}concat=n={len(local_clips)}:v=1:a=0[vcat]")
        filter_complex_no_ass = ";".join(filter_parts)
        escaped_ass = str(local_ass.resolve()).replace("\\", "/").replace(":", "\\:")
        filter_complex_with_ass = f"{filter_complex_no_ass};[vcat]ass='{escaped_ass}'[vout]"

        def _encode_cmd(filter_complex: str, v_map: str) -> list[str]:
            return [
                ffmpeg_exe, "-y",
                *input_args,
                "-filter_complex", filter_complex,
                "-map", v_map,
                "-map", f"{audio_input_idx}:a:0",
                "-frames:v", str(target_total_frames),
                "-t", f"{target_total_dur:.3f}",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-crf", "20",
                "-pix_fmt", "yuv420p",
                "-r", str(fps_int),
                "-c:a", "aac",
                "-b:a", "192k",
                str(tmp_final_video_path.resolve()),
            ]

        encode_timeout = 900
        res = subprocess.run(
            _encode_cmd(filter_complex_with_ass, "[vout]"),
            capture_output=True, text=True, check=False, timeout=encode_timeout,
        )
        if res.returncode != 0 or not tmp_final_video_path.exists():
            stderr_tail = (res.stderr or "").strip()[-800:]
            print(
                f"[WARN] {storage.project_id}: subtitle burn-in failed (ffmpeg exit {res.returncode}); "
                f"re-encoding WITHOUT subtitles. ffmpeg stderr tail:\n{stderr_tail}",
                file=sys.stderr,
            )
            subprocess.run(
                _encode_cmd(filter_complex_no_ass, "[vcat]"),
                capture_output=True, text=True, check=True, timeout=encode_timeout,
            )

        if use_local_tmp:
            shutil.copy2(tmp_final_video_path, final_video_path)
        root_deliverable = storage.project_dir / f"final_shorts_{storage.project_id}.mp4"
        shutil.copy2(tmp_final_video_path, root_deliverable)

        probe_report = MediaIntegrityValidator.validate_video_file(
            tmp_final_video_path,
            min_size_bytes=MIN_CLIP_SIZE_BYTES,
            require_30s_shorts=True,
            check_motion=True,
            check_audio=True,
        )
        probe_report["file_path"] = str(final_video_path)
        video_sha = storage._calculate_sha256(tmp_final_video_path)
        video_sz = tmp_final_video_path.stat().st_size
        probe_report["final_mp4_sha256"] = video_sha
    finally:
        if use_local_tmp and tmp_stage_dir.exists():
            shutil.rmtree(tmp_stage_dir, ignore_errors=True)

    storage.save_json("05_assembly", "probe_report.json", probe_report)
    storage.record_artifact("05_assembly", "final_shorts_1080x1920.mp4", final_video_path, known_sha256=video_sha, known_size_bytes=video_sz)
    storage.update_stage_status("05_assembly", "completed")

    manifest = storage.get_manifest()
    manifest["final_video"] = {
        "path": str(final_video_path),
        "size_bytes": probe_report["file_size_bytes"],
        "duration": probe_report["duration_seconds"],
        "resolution": f"{probe_report['width']}x{probe_report['height']}",
        "source": "multi_clip_google_flow_assembly",
    }
    storage._write_manifest(manifest)
    return final_video_path


def dispatch_parallel_flow_batches_for_topics(
    topics: list[dict[str, Any]],
    cdp_port: int = 9222,
    max_batch_size: int = 5,
    trigger_first_clip: bool = False,
) -> dict[str, Any]:
    """
    Guard 6 (R37): Dispatches topics in strict chunks of at most 5 topics per batch
    (`FLOW_MAX_PARALLEL_BATCH_SIZE = 5`), where 1 Topic = 1 Dedicated FlowProjectSubagentWorker
    = 1 Dedicated Naver Whale Google Flow Tab.
    """
    from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE
    from pipeline.flow_browser import FlowParallelOrchestrator

    effective_max = min(int(max_batch_size), FLOW_MAX_PARALLEL_BATCH_SIZE)
    project_ids = [t["project_id"] for t in topics]
    orch = FlowParallelOrchestrator(cdp_port=cdp_port, max_batch_size=effective_max)
    return orch.run_parallel_batches(
        project_ids=project_ids,
        max_batch_size=effective_max,
        trigger_first_clip=trigger_first_clip,
    )


def main() -> None:
    from pipeline.config import FLOW_MAX_PARALLEL_BATCH_SIZE

    print(f"""
========================================================================
  ALL ABOUT BRAIN — R37 1:1:1 GOOGLE FLOW BATCH DISPATCH (MAX {FLOW_MAX_PARALLEL_BATCH_SIZE}/BATCH)
========================================================================
""")
    res = dispatch_parallel_flow_batches_for_topics(
        PSYCHOLOGY_TOPICS,
        cdp_port=9222,
        max_batch_size=FLOW_MAX_PARALLEL_BATCH_SIZE,
        trigger_first_clip=False,
    )
    print(f"Dispatched {res['total_projects']} topics across {res['total_batches']} batches (max {res['max_batch_size']} per batch).")


if __name__ == "__main__":
    main()
