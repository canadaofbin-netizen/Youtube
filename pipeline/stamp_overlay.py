"""
ALL ABOUT BRAIN — R70 v2 Hand-Drawn Crayon / Ink-Pen HERO Graph Overlay (`pipeline/stamp_overlay.py`).

Upgrades R70 from a small boxy dashboard card into a full-focus HERO editorial sketch (`Y = 10%..62%`, ~1,000px tall):
  - Zero rectangular UI card, zero yellow pill badge.
  - Underlying video receives a cinema focus-pull (`gblur=sigma=14` + `35%` dim across the upper canvas, keeping
    lower `Y >= 68%` burned subtitles 100% razor-sharp).
  - Progressive left-to-right hand-textured strokes (`crayon`, `ink_pen`, `marker`) using bundled OFL handwriting
    fonts (`PatrickHand-Regular.ttf` / `Caveat-Variable.ttf`).
  - Natural wrist-arc cubic-Bezier comparison arrow with pressure tapering, ease-in-out speed, deterministic
    hand-tremor normal jitter (`±1.5px`), delayed asymmetric two-stroke arrowhead (`>=15%` wing length difference),
    and a `1.32`-turn open tilted-ellipse highlight around hand-lettered `4×`.
"""

from __future__ import annotations

import math
import os
import re
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image, ImageDraw, ImageFilter, ImageFont

from pipeline.charts import (
    compute_stamp_complexity_and_hold_sec,
    is_legacy_bar_compare_only,
    parse_chart_spec,
    render_chart_spec_rgba_frame,
    route_chart_for_stat,
)
from pipeline.charts.layers import _display_unit
from pipeline.config import (
    DATA_STAMP_BANNED_PLACEHOLDER_PATTERNS,
    DATA_STAMP_BANNED_PRESETS,
    DATA_STAMP_BG_BLUR_SIGMA,
    DATA_STAMP_BG_DIM,
    DATA_STAMP_DEFAULT_STYLE,
    DATA_STAMP_HERO_MODE,
    DATA_STAMP_LAYER_TYPES,
    DATA_STAMP_MAX_GROUPS,
    DATA_STAMP_MAX_LAYERS_PER_PANEL,
    DATA_STAMP_MAX_PANELS,
    DATA_STAMP_MAX_PER_EPISODE,
    DATA_STAMP_MAX_SCATTER_POINTS,
    DATA_STAMP_MIN_HOLD_SEC,
    DATA_STAMP_MIN_PER_EPISODE,
    DATA_STAMP_MIN_SENTENCE_GAP,
    DATA_STAMP_MODES,
    DATA_STAMP_PRESETS,
    DATA_STAMP_Y_FRAC_RANGE,
    FONT_CONDENSED_BLACK_PATH,
    FONT_PRIMARY_PATH,
    UNIVERSAL_SAFE_X_RIGHT_PX,
    VIDEO_HEIGHT,
    VIDEO_WIDTH,
    WORKSPACE_ROOT,
)

HAND_FONTS_DIR = WORKSPACE_ROOT / "pipeline" / "assets" / "fonts"
PATRICK_HAND_TTF = HAND_FONTS_DIR / "PatrickHand-Regular.ttf"
CAVEAT_TTF = HAND_FONTS_DIR / "Caveat-Variable.ttf"

_NUMBER_WORDS: dict[int, tuple[str, ...]] = {
    0: ("zero", "none", "no"),
    1: ("one", "single", "once", "first", "a single"),
    2: ("two", "twice", "double", "doubled", "pair", "second", "half"),
    3: ("three", "triple", "tripled", "third"),
    4: ("four", "quadruple", "quadrupled", "fourfold", "quarter"),
    5: ("five", "fivefold"),
    6: ("six", "sixfold"),
    7: ("seven",),
    8: ("eight",),
    9: ("nine",),
    10: ("ten", "tenfold"),
    11: ("eleven",),
    12: ("twelve", "dozen"),
    13: ("thirteen",),
    14: ("fourteen",),
    15: ("fifteen",),
    16: ("sixteen",),
    18: ("eighteen",),
    20: ("twenty",),
    24: ("twenty-four", "twenty four"),
    25: ("twenty-five", "twenty five", "quarter"),
    30: ("thirty",),
    40: ("forty",),
    50: ("fifty", "half"),
    60: ("sixty",),
    70: ("seventy",),
    75: ("seventy-five", "seventy five", "three quarters"),
    80: ("eighty",),
    90: ("ninety",),
    100: ("hundred", "one hundred", "every single"),
}

_DOI_RE = re.compile(r"^10\.\d{4,9}/[-._;()/:A-Za-z0-9]+$")


def _ffmpeg_exe() -> str:
    import imageio_ffmpeg  # type: ignore

    return imageio_ffmpeg.get_ffmpeg_exe()


def _load_hand_font(size: int, expressive_accent: bool = False) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Loads bundled OFL handwriting font (`PatrickHand` for crisp legibility, `Caveat` for handwritten accents)."""
    candidates: list[Path] = []
    if expressive_accent:
        candidates.extend([CAVEAT_TTF, PATRICK_HAND_TTF])
    else:
        candidates.extend([PATRICK_HAND_TTF, CAVEAT_TTF])
    candidates.extend([Path(FONT_CONDENSED_BLACK_PATH), Path(FONT_PRIMARY_PATH)])
    for fp in candidates:
        if fp.is_file():
            try:
                font = ImageFont.truetype(str(fp), size=max(10, int(size)))
                if fp.name == "Caveat-Variable.ttf":
                    try:
                        font.set_variation_by_axes([700])
                    except Exception:
                        pass
                return font
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _ease_out_cubic(x: float) -> float:
    t = max(0.0, min(1.0, float(x)))
    return 1.0 - (1.0 - t) ** 3


def _ease_in_out_cubic(x: float) -> float:
    t = max(0.0, min(1.0, float(x)))
    return 4.0 * t * t * t if t < 0.5 else 1.0 - ((-2.0 * t + 2.0) ** 3) / 2.0


def _format_num(val: float, is_int: bool, decimals: int | None = None) -> str:
    if decimals is not None:
        if decimals <= 0:
            return f"{int(round(val))}"
        return f"{val:.{decimals}f}"
    if is_int:
        return f"{int(round(val))}"
    if abs(val * 10.0 - round(val * 10.0)) >= 0.05:
        return f"{val:.2f}"
    return f"{val:.1f}"


_ONES_WORDS: dict[int, str] = {
    0: "zero",
    1: "one",
    2: "two",
    3: "three",
    4: "four",
    5: "five",
    6: "six",
    7: "seven",
    8: "eight",
    9: "nine",
    10: "ten",
    11: "eleven",
    12: "twelve",
    13: "thirteen",
    14: "fourteen",
    15: "fifteen",
    16: "sixteen",
    17: "seventeen",
    18: "eighteen",
    19: "nineteen",
}
_TENS_WORDS: dict[int, str] = {
    20: "twenty",
    30: "thirty",
    40: "forty",
    50: "fifty",
    60: "sixty",
    70: "seventy",
    80: "eighty",
    90: "ninety",
}


def _spelled_int_variants(iv: int) -> tuple[str, ...]:
    out: list[str] = list(_NUMBER_WORDS.get(iv, ()))
    if iv in _ONES_WORDS:
        out.append(_ONES_WORDS[iv])
    elif iv in _TENS_WORDS:
        out.append(_TENS_WORDS[iv])
    elif 21 <= iv <= 99:
        tens = (iv // 10) * 10
        ones = iv % 10
        tw, ow = _TENS_WORDS[tens], _ONES_WORDS[ones]
        out.extend([f"{tw}-{ow}", f"{tw} {ow}"])
    elif iv == 100:
        out.extend(["hundred", "one hundred", "a hundred"])
    return tuple(dict.fromkeys(out))


def _sentence_mentions_number(sentence: str, val: float) -> bool:
    low = re.sub(r"(?<=\d),(?=\d{3}\b)", "", str(sentence or "").lower())
    if abs(val - round(val)) < 1e-6:
        iv = int(round(val))
        if re.search(rf"\b{iv}\b", low):
            return True
        for w in _spelled_int_variants(iv):
            if re.search(rf"\b{re.escape(w)}\b", low):
                return True
    else:
        s_val = f"{val:g}"
        if s_val in low:
            return True
        # Also check rounded 1-decimal or integer spoken form (e.g., 3.5 -> "3.5", 0.79 -> "79%" or ".79")
        if f"{val:.1f}" in low or f"{val:.2f}" in low:
            return True
        # Check spelled-out decimal forms (e.g., 9.5 -> "nine point five", 2.1 -> "two point one")
        abs_v = abs(val)
        whole_part = int(abs_v)
        dec_str = f"{abs_v:.2f}".split(".")[1].rstrip("0")
        if dec_str and len(dec_str) <= 2:
            dec_words = " ".join(_ONES_WORDS[int(ch)] for ch in dec_str if ch.isdigit())
            for ww in _spelled_int_variants(whole_part):
                phrase = f"{ww} point {dec_words}"
                if re.search(rf"\b{re.escape(phrase)}\b", low):
                    return True
            if whole_part == 0 and re.search(rf"\bpoint {re.escape(dec_words)}\b", low):
                return True
        pct_eq = int(round(abs(val) * 100))
        if 0 < abs(val) < 1.0:
            if re.search(rf"\b{pct_eq}\b", low):
                return True
            for w in _spelled_int_variants(pct_eq):
                if re.search(rf"\b{re.escape(w)}\b", low):
                    return True
    return False


def _extract_panel_candidate_numbers(panel_raw: dict[str, Any]) -> list[float]:
    nums: list[float] = []
    for k in ("bars", "groups"):
        items = panel_raw.get(k)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    for vk in ("value", "mean", "median", "min", "max", "q1", "q3", "sd"):
                        if isinstance(it.get(vk), (int, float)):
                            nums.append(float(it[vk]))
    for k in ("percent", "value", "highlighted_k", "total_n", "r"):
        if isinstance(panel_raw.get(k), (int, float)):
            nums.append(float(panel_raw[k]))
    params = panel_raw.get("params")
    if isinstance(params, dict):
        for k in ("k", "n", "r", "mean", "sd", "percent"):
            if isinstance(params.get(k), (int, float)):
                nums.append(float(params[k]))
    series = panel_raw.get("series")
    if isinstance(series, list):
        for s in series:
            if isinstance(s, dict) and isinstance(s.get("values"), list):
                for v in s["values"]:
                    if isinstance(v, (int, float)):
                        nums.append(float(v))
    return nums


def _extract_primary_data_numbers(panel_raw: dict[str, Any]) -> list[float]:
    """Extracts primary chart values (bars, groups, percent, dot_array k/n, series values) excluding synthetic SDs."""
    nums: list[float] = []
    for k in ("bars", "groups"):
        items = panel_raw.get(k)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    for vk in ("value", "mean"):
                        if isinstance(it.get(vk), (int, float)):
                            nums.append(float(it[vk]))
                            break
    for k in ("percent", "value", "highlighted_k", "total_n"):
        if isinstance(panel_raw.get(k), (int, float)):
            nums.append(float(panel_raw[k]))
    series = panel_raw.get("series")
    if isinstance(series, list):
        for s in series:
            if isinstance(s, dict) and isinstance(s.get("values"), list):
                for v in s["values"]:
                    if isinstance(v, (int, float)):
                        nums.append(float(v))
    return nums


def validate_r70_m9_stat_integrity(
    panel_raw: dict[str, Any],
    reference_text: str = "",
    *,
    p_tag: str = "stamp",
) -> list[str]:
    """
    R70-M9 Zero-Hallucination & Intuitive Diet Gate:
      1. Forbids `2x1` multi-panel layouts (`DATA_STAMP_MAX_PANELS == 1`) and non-intuitive presets (`DATA_STAMP_BANNED_PRESETS`).
      2. Forbids `mode == 'derived'` and fabricated/academic `sd` / `error` / `ci_low` / `ci_high` / `q1` / `q3` fields.
      3. Forbids mechanical placeholder titles and labels (`Group 1/2`, `Baseline /`, `Quantitative Study Comparison`, etc.).
      4. Blocks `1800..2100` publication years and `180..209` truncated-year numbers (`1970` -> `197.0`) from chart values.
      5. Requires every primary `mode='study'` value to appear in the non-year `reference_text` when provided.
    """
    errs: list[str] = []
    if not isinstance(panel_raw, dict):
        return [f"[data_stamp] {p_tag} must be a dict (R70-M9)"]

    if str(panel_raw.get("layout") or "1x1").strip().lower() != "1x1" or (
        isinstance(panel_raw.get("panels"), list) and len(panel_raw["panels"]) > 1
    ):
        errs.append(f"[data_stamp] {p_tag} 2x1 multi-panel layout is forbidden under R70-M Intuitive Diet (R70-M9)")

    preset = str(
        panel_raw.get("preset")
        or panel_raw.get("chart")
        or route_chart_for_stat(panel_raw.get("format"))
        or "bar_compare"
    ).strip().lower()
    if preset in DATA_STAMP_BANNED_PRESETS:
        errs.append(f"[data_stamp] {p_tag} banned non-intuitive preset={preset!r} (R70-M9)")

    mode = str(panel_raw.get("mode") or "study").strip().lower()
    if mode not in DATA_STAMP_MODES:
        errs.append(f"[data_stamp] {p_tag} forbidden mode={mode!r} (allowed: {DATA_STAMP_MODES}) (R70-M9)")

    # Check mechanical placeholder titles & labels
    text_fields: list[str] = []
    if panel_raw.get("title"):
        text_fields.append(str(panel_raw["title"]))
    for k in ("bars", "groups", "series"):
        items = panel_raw.get(k)
        if isinstance(items, list):
            for it in items:
                if isinstance(it, dict):
                    if it.get("label"):
                        text_fields.append(str(it["label"]))
                    if it.get("start_label"):
                        text_fields.append(str(it["start_label"]))
                    for bad_stat_k in ("sd", "error", "ci_low", "ci_high", "q1", "q3", "iqr"):
                        if it.get(bad_stat_k) is not None:
                            errs.append(
                                f"[data_stamp] {p_tag} contains banned academic dispersion field {bad_stat_k!r} (R70-M9)"
                            )
    for tf in text_fields:
        tf_clean = tf.strip()
        tf_low = tf_clean.lower()
        for pat in DATA_STAMP_BANNED_PLACEHOLDER_PATTERNS:
            if pat in tf_low:
                errs.append(f"[data_stamp] {p_tag} uses banned placeholder title/label {tf!r} (R70-M9)")
                break
        if tf_clean.count("(") != tf_clean.count(")"):
            errs.append(f"[data_stamp] {p_tag} has unbalanced parentheses in title/label {tf!r} (R70-M9)")
        if tf_clean.endswith(("-", ":", "/", ",", "(")) or "- -" in tf_clean:
            errs.append(f"[data_stamp] {p_tag} has truncated punctuation in title/label {tf!r} (R70-M9)")
        if re.search(
            r"\b(a|an|the|of|and|or|to|in|on|by|for|with|from|at|as|into|la|lifel|mechanica|then|each)\s*$",
            tf_low,
        ):
            errs.append(f"[data_stamp] {p_tag} ends with dangling/truncated word in title/label {tf!r} (R70-M9)")

    if mode == "study":
        primary_vals = _extract_primary_data_numbers(panel_raw)
        ref_str = str(reference_text or "")
        year_tokens = [int(y) for y in re.findall(r"\b(18\d\d|19\d\d|20[0-2]\d)\b", ref_str)]
        year_prefixes = {int(str(y)[:3]) for y in year_tokens}
        # Strip 4-digit years from reference text before checking value grounding
        non_year_text = re.sub(r"\b(18\d\d|19\d\d|20[0-2]\d)\b", " ", ref_str)

        for v in primary_vals:
            iv = int(round(v))
            is_int = abs(v - iv) < 1e-6
            if is_int and 1800 <= iv <= 2100 and (not ref_str or iv in year_tokens):
                if not _sentence_mentions_number(non_year_text, v):
                    errs.append(f"[data_stamp] {p_tag} value {v} is a publication year artifact (R70-M9)")
                    continue
            if is_int and 180 <= iv <= 209 and (iv in year_prefixes or not _sentence_mentions_number(non_year_text, v)):
                errs.append(
                    f"[data_stamp] {p_tag} value {v} is a truncated-year artifact (e.g. 1970 -> 197.0) (R70-M9)"
                )
                continue
            if ref_str.strip() and not _sentence_mentions_number(non_year_text, v):
                errs.append(
                    f"[data_stamp] {p_tag} study value {v} is not grounded in source text {ref_str[:75]!r} (R70-M9)"
                )
    return errs



def _load_dossier_grounding_bundle(
    script_doc: dict[str, Any] | None,
    dossier_doc: dict[str, Any] | str | None = None,
) -> tuple[str, bool]:
    """
    Loads verified empirical text + DOI presence from an explicit `dossier_doc` or on-disk
    `BCI_Shorts_Channel/research_dossiers/<slug>/` (`00_topic.json`, `01_sources.json`, `02_core_facts.json`,
    `dossier.json`) so R85 Q2 allows `mode='study'` charts to match verified dossier numbers without audio re-recording.
    """
    import json

    chunks: list[str] = []
    has_doi = False
    if isinstance(script_doc, dict):
        s_doi = str(script_doc.get("doi") or script_doc.get("primary_doi") or "").strip()
        if s_doi and _DOI_RE.match(s_doi):
            has_doi = True
            chunks.append(s_doi)
        for src_it in (script_doc.get("sources") or []):
            txt_s = json.dumps(src_it, ensure_ascii=False) if isinstance(src_it, (dict, list)) else str(src_it)
            if re.search(r"\b10\.\d{4,9}/\S+", txt_s):
                has_doi = True
            chunks.append(txt_s)

    if isinstance(dossier_doc, str) and dossier_doc.strip():
        chunks.append(dossier_doc)
        if re.search(r"\b10\.\d{4,9}/\S+", dossier_doc):
            has_doi = True
    elif isinstance(dossier_doc, dict):
        raw_s = json.dumps(dossier_doc, ensure_ascii=False)
        chunks.append(raw_s)
        if re.search(r"\b10\.\d{4,9}/\S+", raw_s):
            has_doi = True

    slug = ""
    if isinstance(script_doc, dict):
        slug = str(script_doc.get("dossier") or script_doc.get("dossier_slug") or "").strip()
    if slug:
        from pipeline.config import DOSSIERS_DIR

        d_dir = Path(DOSSIERS_DIR) / slug
        if d_dir.is_dir():
            for fn in ("00_topic.json", "01_sources.json", "02_core_facts.json", "dossier.json"):
                fp = d_dir / fn
                if fp.is_file():
                    try:
                        txt_f = fp.read_text(encoding="utf-8")
                        chunks.append(txt_f)
                        if re.search(r"\b10\.\d{4,9}/\S+", txt_f):
                            has_doi = True
                    except Exception:
                        pass
    return " ".join(chunks), has_doi


def _extract_spoken_numbers_for_contradiction(sentence: str) -> list[float]:
    """Extracts explicit numeric quantities spoken in `sentence` (excluding 4-digit calendar years)."""
    clean = re.sub(r"\b(18\d\d|19\d\d|20[0-2]\d)\b", " ", str(sentence or ""))
    clean_low = re.sub(r"(?<=\d),(?=\d{3}\b)", "", clean.lower())
    found: list[float] = []
    for m in re.finditer(r"(?<![a-z0-9])(\d+(?:\.\d+)?)(?![a-z0-9])", clean_low):
        try:
            found.append(float(m.group(1)))
        except ValueError:
            pass
    # Check 21..99 hyphen/space compounds first, then tens/ones
    used_spans: list[tuple[int, int]] = []
    for iv in list(range(100, 20, -1)) + list(range(20, 0, -1)):
        for w in _spelled_int_variants(iv):
            for mw in re.finditer(rf"\b{re.escape(w)}\b", clean_low):
                sp = mw.span()
                if any(not (sp[1] <= a or sp[0] >= b) for a, b in used_spans):
                    continue
                used_spans.append(sp)
                found.append(float(iv))
    return found


def validate_data_stamps(
    script_doc: dict[str, Any] | None,
    sentences: list[str] | None = None,
    *,
    return_warnings: bool = False,
    dossier_doc: dict[str, Any] | str | None = None,
) -> list[str] | tuple[list[str], list[str]]:
    """
    R70-M Validator (`prompt-gate`):
      - Blocking Errors (`R70-M1..M4`):
        * `<= DATA_STAMP_MAX_PER_EPISODE` (3) stamps per episode.
        * Valid `preset` / `layers` / `layout` (`<= 2` panels, `<= 3` layers/panel, `<= 4` groups, `<= 120` scatter pts).
        * `study` / `derived` modes require valid `doi` (`10.xxxx/...`), `source_citation`, and `>= 1` spoken numeric match.
        * `illustrative` (`"Concept"`) mode forbids attaching a study DOI and requires `concept` or `title`.
        * Numeric integrity (`0 <= percent <= 100`, `0 <= k <= n`, `sd >= 0`, `|r| <= 1`, `min <= q1 <= median <= q3 <= max`).
      - Non-Blocking Warnings (`R70-M5..M7`):
        * `< DATA_STAMP_MIN_PER_EPISODE` (2) stamps per episode -> warning only.
        * Sentence gap `< DATA_STAMP_MIN_SENTENCE_GAP` (4) -> warning only (direct overlap `s_a == s_b` is an error).
        * Consecutive identical chart presets -> warning only.
    """
    if not isinstance(script_doc, dict):
        return ([], []) if return_warnings else []
    from pipeline.config import is_r82_dual_speed_pacing_plan

    is_r82_ds = is_r82_dual_speed_pacing_plan(script_doc)
    raw_stamps = script_doc.get("data_stamps")
    warnings: list[str] = []
    if not raw_stamps:
        if is_r82_ds:
            errs_r82 = [
                f"[r82_data_stamps] Rule R82 requires >= {DATA_STAMP_MIN_PER_EPISODE} R70-M data_stamps (got 0) (R82)"
            ]
            return (errs_r82, warnings) if return_warnings else errs_r82
        if isinstance(raw_stamps, list):
            warnings.append(
                f"[data_stamp:warn] 0 data_stamps present (< recommended {DATA_STAMP_MIN_PER_EPISODE} per episode) (R70-M5)"
            )
        return ([], warnings) if return_warnings else []
    if not isinstance(raw_stamps, list):
        errs = ["[data_stamp] script.data_stamps must be a list of stamp objects (R70)"]
        return (errs, warnings) if return_warnings else errs

    issues: list[str] = []
    if len(raw_stamps) > DATA_STAMP_MAX_PER_EPISODE:
        issues.append(
            f"[data_stamp] {len(raw_stamps)} data_stamps > max {DATA_STAMP_MAX_PER_EPISODE} per episode (R70-M1)"
        )
    if len(raw_stamps) < DATA_STAMP_MIN_PER_EPISODE:
        if is_r82_ds:
            issues.append(
                f"[r82_data_stamps] Rule R82 requires >= {DATA_STAMP_MIN_PER_EPISODE} R70-M data_stamps (got {len(raw_stamps)}) (R82)"
            )
        else:
            warnings.append(
                f"[data_stamp:warn] {len(raw_stamps)} data_stamps < recommended {DATA_STAMP_MIN_PER_EPISODE} per episode (R70-M5)"
            )

    sents = list(sentences or [])
    dossier_grounding_txt, dossier_has_doi = _load_dossier_grounding_bundle(script_doc, dossier_doc=dossier_doc)
    any_sibling_doi = any(
        isinstance(x, dict) and bool(_DOI_RE.match(str(x.get("doi") or "").strip()))
        for x in raw_stamps
    )
    seen_sentences: list[tuple[int, int, int, str]] = []
    allowed_presets = set(DATA_STAMP_PRESETS) | set(DATA_STAMP_LAYER_TYPES) | {
        "arc_gauge_ring",
        "slope",
        "line_trajectory",
        "correlation_band",
        "box_quartile",
    }

    for idx, st in enumerate(raw_stamps, start=1):
        if not isinstance(st, dict):
            issues.append(f"[data_stamp] entry #{idx} must be a dict (R70-M1)")
            continue
        raw_panels = st.get("panels")
        if isinstance(raw_panels, list) and len(raw_panels) > DATA_STAMP_MAX_PANELS:
            issues.append(
                f"[data_stamp] entry #{idx} has {len(raw_panels)} panels > max {DATA_STAMP_MAX_PANELS} (R70-M1)"
            )
        try:
            s_idx = int(st.get("sentence_index") or 0)
        except (TypeError, ValueError):
            s_idx = 0
        try:
            e_idx = int(st.get("end_sentence_index") or s_idx)
        except (TypeError, ValueError):
            e_idx = s_idx
        if sents and not (1 <= s_idx <= len(sents)):
            issues.append(
                f"[data_stamp] entry #{idx} sentence_index={s_idx} out of range 1..{len(sents)} (R70-M1)"
            )

        panel_dicts = (
            [p for p in raw_panels if isinstance(p, dict)]
            if (isinstance(raw_panels, list) and raw_panels)
            else [st]
        )
        primary_preset = str(
            panel_dicts[0].get("preset") or panel_dicts[0].get("chart") or st.get("preset") or st.get("chart") or "bar_compare"
        ).strip().lower()

        for p_k, p_raw in enumerate(panel_dicts[:DATA_STAMP_MAX_PANELS], start=1):
            p_tag = f"entry #{idx}" if len(panel_dicts) == 1 else f"entry #{idx} panel #{p_k}"
            s_hi_ref = min(len(sents), max(s_idx, e_idx)) if (sents and 1 <= s_idx <= len(sents)) else 0
            spoken_ref_txt = " ".join(sents[s_idx - 1 : s_hi_ref]) if s_hi_ref > 0 else ""
            ref_txt_for_m9 = f"{spoken_ref_txt} {dossier_grounding_txt}".strip() if dossier_grounding_txt else spoken_ref_txt
            m9_errs = validate_r70_m9_stat_integrity({**st, **p_raw}, ref_txt_for_m9, p_tag=p_tag)
            issues.extend(m9_errs)
            mode = str(p_raw.get("mode") if "mode" in p_raw else (st.get("mode") or "study")).strip().lower()
            if mode not in DATA_STAMP_MODES:
                issues.append(f"[data_stamp] {p_tag} unsupported mode={mode!r} (allowed: {DATA_STAMP_MODES}) (R70-M1)")
                continue

            style = str(p_raw.get("style") or st.get("style") or DATA_STAMP_DEFAULT_STYLE).strip().lower()
            if style not in ("crayon", "ink_pen", "marker", "chalk"):
                issues.append(
                    f"[data_stamp] {p_tag} unsupported style={style!r} (allowed: crayon, ink_pen, marker, chalk) (R70-M1)"
                )

            preset = str(
                p_raw.get("preset") or p_raw.get("chart") or st.get("preset") or st.get("chart") or "bar_compare"
            ).strip().lower()
            exp_layers = p_raw.get("layers")
            if isinstance(exp_layers, list):
                if len(exp_layers) > DATA_STAMP_MAX_LAYERS_PER_PANEL:
                    issues.append(
                        f"[data_stamp] {p_tag} has {len(exp_layers)} layers > max {DATA_STAMP_MAX_LAYERS_PER_PANEL} (R70-M1)"
                    )
                for l_obj in exp_layers:
                    l_t = str((l_obj or {}).get("type") or "").strip().lower()
                    if l_t not in DATA_STAMP_LAYER_TYPES:
                        issues.append(f"[data_stamp] {p_tag} unknown layer type={l_t!r} (R70-M1)")
            elif preset not in allowed_presets:
                issues.append(f"[data_stamp] {p_tag} unsupported preset/chart={preset!r} (R70-M1)")

            # Group & scatter point limits (R70-M1) and numeric integrity (R70-M4)
            grp_list = p_raw.get("groups") if isinstance(p_raw.get("groups"), list) else p_raw.get("bars")
            if isinstance(grp_list, list):
                if len(grp_list) > DATA_STAMP_MAX_GROUPS:
                    issues.append(
                        f"[data_stamp] {p_tag} has {len(grp_list)} groups/bars > max {DATA_STAMP_MAX_GROUPS} (R70-M1)"
                    )
                for g_i, g_it in enumerate(grp_list, start=1):
                    if not isinstance(g_it, dict) or not str(g_it.get("label") or "").strip():
                        issues.append(f"[data_stamp] {p_tag} group/bar #{g_i} missing 'label' (R70-M1)")
                        continue
                    has_num = any(isinstance(g_it.get(k), (int, float)) for k in ("value", "mean", "median", "q1", "min"))
                    if not has_num and not isinstance(g_it.get("samples"), list):
                        issues.append(f"[data_stamp] {p_tag} group/bar #{g_i} missing numeric value/mean/median (R70-M1)")
                    if isinstance(g_it.get("sd"), (int, float)) and float(g_it["sd"]) < 0.0:
                        issues.append(f"[data_stamp] {p_tag} group #{g_i} has negative sd={g_it['sd']} (R70-M4)")
                    if all(isinstance(g_it.get(k), (int, float)) for k in ("min", "q1", "median", "q3", "max")):
                        q_seq = [float(g_it[k]) for k in ("min", "q1", "median", "q3", "max")]
                        if q_seq != sorted(q_seq):
                            issues.append(
                                f"[data_stamp] {p_tag} group #{g_i} quartiles out of order {q_seq} (R70-M4)"
                            )
            elif preset == "bar_compare" and not isinstance(exp_layers, list):
                issues.append(f"[data_stamp] {p_tag} requires 'bars' list with >= 2 items (R70-M1)")
            elif isinstance(grp_list, list) and preset == "bar_compare" and len(grp_list) < 2:
                issues.append(f"[data_stamp] {p_tag} requires 'bars' list with >= 2 items (R70-M1)")

            pts_list = p_raw.get("points") or p_raw.get("scatter_points")
            if isinstance(pts_list, list) and len(pts_list) > DATA_STAMP_MAX_SCATTER_POINTS:
                issues.append(
                    f"[data_stamp] {p_tag} scatter points={len(pts_list)} > max {DATA_STAMP_MAX_SCATTER_POINTS} (R70-M1)"
                )

            if isinstance(p_raw.get("percent"), (int, float)):
                pct_v = float(p_raw["percent"])
                if not (0.0 <= pct_v <= 100.0):
                    issues.append(f"[data_stamp] {p_tag} percent={pct_v} outside 0..100 (R70-M4)")

            if isinstance(p_raw.get("highlighted_k"), (int, float)) and isinstance(p_raw.get("total_n"), (int, float)):
                hk, tn = float(p_raw["highlighted_k"]), float(p_raw["total_n"])
                if hk < 0 or tn <= 0 or hk > tn or tn > 100:
                    issues.append(
                        f"[data_stamp] {p_tag} invalid dot_array k={hk}, n={tn} (require 0 <= k <= n <= 100) (R70-M4)"
                    )

            r_val = p_raw.get("r") if p_raw.get("r") is not None else (p_raw.get("params") or {}).get("r")
            if isinstance(r_val, (int, float)) and abs(float(r_val)) > 1.0:
                issues.append(f"[data_stamp] {p_tag} correlation r={r_val} outside [-1, 1] (R70-M4)")

            doi = str(p_raw.get("doi") if "doi" in p_raw else (st.get("doi") or "")).strip()
            src = str(
                p_raw.get("source_citation") if "source_citation" in p_raw else (st.get("source_citation") or "")
            ).strip()

            if mode in ("study", "derived"):
                if not doi or not _DOI_RE.match(doi):
                    issues.append(f"[data_stamp] {p_tag} ({mode}) missing valid DOI ('10.xxxx/...') — got {doi!r} (R70-M2)")
                if not src:
                    issues.append(f"[data_stamp] {p_tag} ({mode}) missing 'source_citation' (R70-M2)")
                if mode == "derived":
                    has_model = bool(
                        p_raw.get("model")
                        or st.get("model")
                        or p_raw.get("params")
                        or any(isinstance(g, dict) and ("sd" in g or "q1" in g) for g in (grp_list or []))
                        or r_val is not None
                    )
                    if not has_model:
                        issues.append(
                            f"[data_stamp] {p_tag} (derived) requires 'model' or summary parameters (sd/quartiles/r) (R70-M2)"
                        )
                if sents and 1 <= s_idx <= len(sents):
                    s_hi = min(len(sents), max(s_idx, e_idx))
                    target_text = " ".join(sents[s_idx - 1 : s_hi])
                    combined_grounding = f"{target_text} {dossier_grounding_txt}".strip()
                    primary_nums = _extract_primary_data_numbers({**st, **p_raw})
                    cand_nums = primary_nums or _extract_panel_candidate_numbers({**st, **p_raw})
                    if primary_nums:
                        unmatched_vals = [
                            v for v in primary_nums if not _sentence_mentions_number(combined_grounding, v)
                        ]
                        if unmatched_vals:
                            issues.append(
                                f"[data_stamp] {p_tag} study values {unmatched_vals} do not exactly match spoken S{s_idx} "
                                f"or verified dossier numbers ('{target_text[:70]}') (R70-M2/R85)"
                            )
                        # R85 anti-rounding/mismatch lock (blocks 29% != 30% when S{s_idx} speaks 30%!)
                        spoken_nums = _extract_spoken_numbers_for_contradiction(target_text)
                        for pv in primary_nums:
                            if not _sentence_mentions_number(target_text, pv):
                                near_spoken = [
                                    sv for sv in spoken_nums if 0.05 < abs(pv - sv) <= 3.0
                                ]
                                if near_spoken:
                                    issues.append(
                                        f"[data_stamp] {p_tag} chart value {pv} contradicts spoken number {near_spoken[0]} "
                                        f"in S{s_idx} ('{target_text[:70]}') — exact match required (R85)"
                                    )
                    elif cand_nums and not any(_sentence_mentions_number(combined_grounding, v) for v in cand_nums):
                        issues.append(
                            f"[data_stamp] {p_tag} values {cand_nums} do not match any spoken/dossier number in S{s_idx} "
                            f"('{target_text[:70]}') (R70-M2)"
                        )
            elif mode == "illustrative":
                if doi:
                    issues.append(
                        f"[data_stamp] {p_tag} illustrative ('Concept') mode must not attach a study DOI ({doi!r}) (R70-M3)"
                    )
                prim_ill_nums = _extract_primary_data_numbers({**st, **p_raw})
                if dossier_has_doi or (prim_ill_nums and any_sibling_doi):
                    issues.append(
                        f"[data_stamp] {p_tag} illustrative ('Concept') mode is forbidden when empirical study DOI exists; "
                        "use mode='study' with verified DOI and exact paper numbers (R85)"
                    )
                if not (p_raw.get("concept") or st.get("concept") or p_raw.get("title") or st.get("title")):
                    issues.append(f"[data_stamp] {p_tag} illustrative mode requires 'concept' or 'title' (R70-M3)")

        for prev_i, prev_s, prev_e, prev_preset in seen_sentences:
            if s_idx > 0 and prev_s > 0:
                if max(s_idx, prev_s) <= min(max(s_idx, e_idx), max(prev_s, prev_e)):
                    issues.append(
                        f"[data_stamp] stamps #{prev_i} and #{idx} overlap on sentence S{s_idx} (R70-M6)"
                    )
                elif abs(s_idx - prev_s) < DATA_STAMP_MIN_SENTENCE_GAP:
                    warnings.append(
                        f"[data_stamp:warn] stamps #{prev_i} (S{prev_s}) and #{idx} (S{s_idx}) are only "
                        f"{abs(s_idx - prev_s)} sentences apart (< recommended {DATA_STAMP_MIN_SENTENCE_GAP}) (R70-M6)"
                    )
            if prev_i == idx - 1 and prev_preset == primary_preset:
                warnings.append(
                    f"[data_stamp:warn] consecutive stamps #{prev_i} and #{idx} repeat preset {primary_preset!r} (R70-M7)"
                )
        seen_sentences.append((idx, s_idx, e_idx, primary_preset))

    return (issues, warnings) if return_warnings else issues


@lru_cache(maxsize=8)
def _paper_tooth_grain(width: int, height: int, seed: int = 1337) -> np.ndarray:
    """Deterministic 2D paper-tooth texture in `[0.42, 1.0]` so crayon wax grain stays locked across frames."""
    rng = np.random.default_rng(seed)
    coarse_h = max(8, height // 3)
    coarse_w = max(8, width // 3)
    coarse = rng.uniform(0.35, 1.0, size=(coarse_h, coarse_w)).astype(np.float32)
    coarse_img = Image.fromarray((coarse * 255.0).astype(np.uint8), mode="L").resize((width, height), Image.Resampling.BILINEAR)
    fine = rng.uniform(0.55, 1.0, size=(height, width)).astype(np.float32)
    grain = (0.58 * (np.asarray(coarse_img, dtype=np.float32) / 255.0) + 0.42 * fine).astype(np.float32)
    return np.clip(grain, 0.32, 1.0)


def draw_tapered_hand_stroke(
    canvas: Image.Image,
    points: np.ndarray,
    widths: np.ndarray,
    rgb: tuple[int, int, int],
    *,
    alpha: int = 248,
    progress: float = 1.0,
    style: str = "crayon",
    seed: int = 101,
) -> None:
    """
    Renders a progressive (`0..1`) pressure-tapered hand-drawn stroke onto `canvas` (`RGBA`).
    For `style='crayon'` / `'chalk'`, modulates stroke alpha with a fixed 2D paper-tooth wax mask and organic edge jitter.
    """
    prog = max(0.0, min(1.0, float(progress)))
    if prog <= 0.005 or len(points) < 2 or alpha <= 2:
        return

    n_pts = len(points)
    end_idx = max(2, int(round(prog * n_pts)))
    pts_sub = points[:end_idx]
    w_sub = widths[:end_idx]

    w_canv, h_canv = canvas.size
    mask_img = Image.new("L", (w_canv, h_canv), 0)
    mdraw = ImageDraw.Draw(mask_img)

    rng = np.random.default_rng(seed)
    is_crayon = str(style or "").lower() in ("crayon", "chalk")

    for i in range(len(pts_sub) - 1):
        x0, y0 = float(pts_sub[i, 0]), float(pts_sub[i, 1])
        x1, y1 = float(pts_sub[i + 1, 0]), float(pts_sub[i + 1, 1])
        rad = max(1.0, 0.5 * float(w_sub[i]))
        seg_len = math.hypot(x1 - x0, y1 - y0)
        steps = max(1, int(math.ceil(seg_len / max(1.2, rad * 0.38))))
        for s_k in range(steps + 1):
            u = s_k / float(steps)
            cx = x0 + (x1 - x0) * u
            cy = y0 + (y1 - y0) * u
            if is_crayon:
                # Multi-bristle wax edge roughness (deterministic per step)
                jx = float(rng.normal(0.0, rad * 0.14))
                jy = float(rng.normal(0.0, rad * 0.16))
                r_eff = rad * float(rng.uniform(0.86, 1.12))
                mdraw.ellipse([cx + jx - r_eff, cy + jy - r_eff, cx + jx + r_eff, cy + jy + r_eff], fill=255)
                if rad >= 8.0:
                    jx2 = float(rng.normal(0.0, rad * 0.24))
                    jy2 = float(rng.normal(0.0, rad * 0.24))
                    r2 = rad * 0.62
                    mdraw.ellipse([cx + jx2 - r2, cy + jy2 - r2, cx + jx2 + r2, cy + jy2 + r2], fill=215)
            else:
                mdraw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=255)

    mask_arr = np.asarray(mask_img, dtype=np.float32) / 255.0
    if not np.any(mask_arr > 0.01):
        return

    if is_crayon:
        grain = _paper_tooth_grain(w_canv, h_canv, seed=seed % 997 + 17)
        # Keep core legible while showing authentic wax tooth along edges and interior grain
        textured = np.clip(mask_arr * (0.38 + 0.72 * (grain ** 1.35)), 0.0, 1.0)
        mask_arr = np.where(mask_arr > 0.05, textured, 0.0)
    elif str(style or "").lower() == "marker":
        mask_arr = np.clip(mask_arr * 0.94, 0.0, 1.0)

    layer = np.zeros((h_canv, w_canv, 4), dtype=np.uint8)
    layer[..., 0] = int(rgb[0])
    layer[..., 1] = int(rgb[1])
    layer[..., 2] = int(rgb[2])
    layer[..., 3] = np.clip(mask_arr * float(alpha), 0.0, 255.0).astype(np.uint8)
    canvas.alpha_composite(Image.fromarray(layer, mode="RGBA"))


def compute_natural_arrow_geometry(
    start_xy: tuple[float, float],
    target_xy: tuple[float, float],
    *,
    base_width: float = 8.5,
    scale: float = 1.0,
    seed: int = 404,
    n_samples: int = 96,
) -> dict[str, Any]:
    """
    Builds a human-drawn asymmetric cubic-Bezier arrow from `start_xy` toward `target_xy`:
      - Stops slightly shy (`12 * scale` px) of `target_xy` so it never looks CAD-snapped.
      - Asymmetric control points (`C1` steeper wrist lift, `C2` sweeping approach) -> non-circular arc.
      - Fixed-seed low-frequency normal hand tremor (`±1.5px` scaled).
      - Pressure-tapered widths (`thin -> thick -> slightly thin`).
      - Two asymmetric arrowhead strokes (`left_wing` ~ `29px @ 31°`, `right_wing` ~ `19.5px @ 43°` -> `32%` diff).
    """
    x0, y0 = float(start_xy[0]), float(start_xy[1])
    xt, yt = float(target_xy[0]), float(target_xy[1])

    dx_raw = xt - x0
    dy_raw = yt - y0
    dist = max(24.0, math.hypot(dx_raw, dy_raw))
    ux_dir = dx_raw / dist
    uy_dir = dy_raw / dist

    # Stop slightly shy of exact target endpoint (human hand margin)
    shy_px = 13.0 * scale
    x3 = xt - ux_dir * shy_px
    y3 = yt - uy_dir * shy_px - 6.0 * scale

    # Asymmetric wrist-arc control points (steep initial lift, long sweeping descent — never a circular arc)
    arc_lift = max(58.0 * scale, min(145.0 * scale, 0.34 * dist))
    c1x = x0 + 0.21 * (x3 - x0) - 18.0 * scale
    c1y = min(y0, y3) - arc_lift * 1.18
    c2x = x0 + 0.83 * (x3 - x0) + 12.0 * scale
    c2y = min(y0, y3) - arc_lift * 0.26

    u = np.linspace(0.0, 1.0, max(24, int(n_samples)), dtype=np.float64)
    om = 1.0 - u
    bx = (om ** 3) * x0 + 3.0 * (om ** 2) * u * c1x + 3.0 * om * (u ** 2) * c2x + (u ** 3) * x3
    by = (om ** 3) * y0 + 3.0 * (om ** 2) * u * c1y + 3.0 * om * (u ** 2) * c2y + (u ** 3) * y3

    # Tangent & unit normal for deterministic low-frequency hand tremor (±1.5px)
    tx = np.gradient(bx)
    ty = np.gradient(by)
    t_norm = np.maximum(1e-6, np.hypot(tx, ty))
    nx = -ty / t_norm
    ny = tx / t_norm

    rng = np.random.default_rng(seed)
    ph1 = float(rng.uniform(0.0, 2.0 * math.pi))
    ph2 = float(rng.uniform(0.0, 2.0 * math.pi))
    envelope_ends = np.sin(np.pi * u) ** 0.75
    jitter = (
        1.15 * scale * np.sin(2.0 * np.pi * 1.6 * u + ph1)
        + 0.55 * scale * np.sin(2.0 * np.pi * 3.7 * u + ph2)
    ) * envelope_ends
    pts = np.column_stack([bx + nx * jitter, by + ny * jitter]).astype(np.float32)

    # Pressure tapering: thin touch-down -> fuller mid-stroke -> slightly tapered release
    taper = 0.40 + 0.68 * (np.sin(np.pi * np.clip(u * 0.94 + 0.02, 0.0, 1.0)) ** 0.65)
    micro_pressure = 1.0 + 0.07 * np.sin(2.0 * np.pi * 2.3 * u + ph1 * 0.5)
    widths = (float(base_width) * scale * taper * micro_pressure).astype(np.float32)

    # End tangent direction at tip for asymmetric two-stroke arrowhead
    tip = pts[-1]
    lookback = max(2, len(pts) // 12)
    end_vec = pts[-1] - pts[-1 - lookback]
    end_ang = math.atan2(float(end_vec[1]), float(end_vec[0]))

    left_len = 31.0 * scale
    right_len = 20.5 * scale  # ~33.9% shorter than left_len (>= 15% asymmetry!)
    left_ang = end_ang + math.pi - math.radians(30.5)
    right_ang = end_ang + math.pi + math.radians(42.5)

    def _wing_stroke(length_px: float, ang_rad: float, wing_seed: int) -> tuple[np.ndarray, np.ndarray]:
        wu = np.linspace(0.0, 1.0, 18, dtype=np.float32)
        wx1 = float(tip[0]) + length_px * math.cos(ang_rad)
        wy1 = float(tip[1]) + length_px * math.sin(ang_rad)
        # Slight wrist curve on each wing stroke
        perp_x = -math.sin(ang_rad) * (2.2 * scale)
        perp_y = math.cos(ang_rad) * (2.2 * scale)
        wx = (1.0 - wu) * float(tip[0]) + wu * wx1 + perp_x * np.sin(np.pi * wu)
        wy = (1.0 - wu) * float(tip[1]) + wu * wy1 + perp_y * np.sin(np.pi * wu)
        ww = float(base_width) * scale * (0.92 - 0.50 * wu)
        _ = wing_seed
        return np.column_stack([wx, wy]).astype(np.float32), ww.astype(np.float32)

    wing_l_pts, wing_l_w = _wing_stroke(left_len, left_ang, seed + 1)
    wing_r_pts, wing_r_w = _wing_stroke(right_len, right_ang, seed + 2)

    return {
        "shaft_points": pts,
        "shaft_widths": widths,
        "left_wing_points": wing_l_pts,
        "left_wing_widths": wing_l_w,
        "right_wing_points": wing_r_pts,
        "right_wing_widths": wing_r_w,
        "left_wing_length": float(left_len),
        "right_wing_length": float(right_len),
        "arc_peak_xy": (float(pts[int(len(pts) * 0.42), 0]), float(np.min(pts[:, 1]))),
    }


def compute_open_ellipse_loop(
    center_xy: tuple[float, float],
    rx: float,
    ry: float,
    *,
    turns: float = 1.32,
    tilt_deg: float = -6.5,
    base_width: float = 7.0,
    scale: float = 1.0,
    seed: int = 808,
    n_samples: int = 90,
) -> tuple[np.ndarray, np.ndarray]:
    """
    Computes a slightly squashed, tilted `1.32`-turn hand-sketched ellipse around `center_xy`
    whose start and end radii drift apart so the loop stays naturally open rather than CAD-closed.
    """
    cx, cy = float(center_xy[0]), float(center_xy[1])
    u = np.linspace(0.0, 1.0, max(30, int(n_samples)), dtype=np.float64)
    theta0 = -0.62 * math.pi
    theta = theta0 + (2.0 * math.pi * float(turns)) * u

    # Spiral radial drift + asymmetric squash so turn 2 sits outside turn 1 with open start/end tips
    r_spiral = 0.92 + 0.16 * u + 0.04 * np.sin(3.0 * theta + 0.7)
    ex = float(rx) * r_spiral * np.cos(theta)
    ey = float(ry) * (0.94 + 0.13 * (1.0 - u)) * np.sin(theta)

    ang = math.radians(float(tilt_deg))
    ca, sa = math.cos(ang), math.sin(ang)
    px = cx + ex * ca - ey * sa
    py = cy + ex * sa + ey * ca

    taper = 0.42 + 0.64 * (np.sin(np.pi * u) ** 0.62)
    _ = seed
    widths = (float(base_width) * scale * taper).astype(np.float32)
    return np.column_stack([px, py]).astype(np.float32), widths


def _draw_text_with_soft_halo(
    canvas: Image.Image,
    xy: tuple[int, int],
    text: str,
    font: ImageFont.FreeTypeFont | ImageFont.ImageFont,
    fill_rgba: tuple[int, int, int, int],
    *,
    halo_alpha: int = 155,
    halo_blur_px: float = 4.0,
) -> tuple[int, int, int, int]:
    """Draws crisp handwritten text with a soft dark ink-legibility halo (zero rectangular box!)."""
    w, h = canvas.size
    halo = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    hdraw = ImageDraw.Draw(halo, "RGBA")
    bbox = hdraw.textbbox(xy, text, font=font)
    if halo_alpha > 0:
        for ox, oy in ((-2, 0), (2, 0), (0, -2), (0, 2), (0, 3)):
            hdraw.text((xy[0] + ox, xy[1] + oy), text, font=font, fill=(8, 11, 16, halo_alpha))
        if halo_blur_px > 0.5:
            halo = halo.filter(ImageFilter.GaussianBlur(radius=halo_blur_px))
        canvas.alpha_composite(halo)
    tdraw = ImageDraw.Draw(canvas, "RGBA")
    tdraw.text(xy, text, font=font, fill=fill_rgba)
    return bbox


def resolve_multiplier_badge_placement(
    *,
    arrow_geo: dict[str, Any],
    val_boxes: list[tuple[float, float, float, float]],
    bar_boxes: list[tuple[float, float, float, float]],
    bar_tip_coords: list[tuple[float, float]],
    bar_val_right_x: list[float],
    mw_est: float,
    mh_est: float,
    est_rx: float,
    est_ry: float,
    bar_start_x: float,
    x_left: float,
    x_right: float,
    ul_y: float,
    y_bot: float,
    scale_x: float,
    scale_y: float,
    scale: float,
) -> tuple[int, int]:
    """
    Finds `(tx, ty)` for the hand-lettered multiplier label and its red open-ellipse loop
    with `>= 20px` scaled clearance from arrow strokes, bar value bboxes, and bars.
    """
    all_arrow_pts = np.vstack([
        np.asarray(arrow_geo["shaft_points"], dtype=np.float64),
        np.asarray(arrow_geo["left_wing_points"], dtype=np.float64),
        np.asarray(arrow_geo["right_wing_points"], dtype=np.float64),
    ])
    apex_x, apex_y = arrow_geo["arc_peak_xy"]
    arr_max_x = float(np.max(all_arrow_pts[:, 0]))
    arr_min_y = float(np.min(all_arrow_pts[:, 1]))

    loop_rx_real = max(48.0 * scale_x, est_rx) + 4.0 * scale
    loop_ry_real = max(34.0 * scale_y, est_ry) + 4.0 * scale
    rx_clr = loop_rx_real + 20.0 * scale
    ry_clr = loop_ry_real + 20.0 * scale

    min_tx = int(round(max(x_left + loop_rx_real - 0.5 * mw_est + 6.0 * scale_x, bar_start_x + 12.0 * scale_x)))
    max_tx = int(round(max(min_tx, x_right - 0.5 * mw_est - loop_rx_real - 6.0 * scale_x)))
    min_ty = int(round(ul_y + loop_ry_real - 0.5 * mh_est + 10.0 * scale_y))
    max_ty = int(round(max(min_ty, y_bot - loop_ry_real - 0.5 * mh_est - 12.0 * scale_y)))

    def _box_collides(lcx: float, lcy: float, boxes: list[tuple[float, float, float, float]], pad: float) -> bool:
        for bx0, by0, bx1, by1 in boxes:
            if not (lcx + rx_clr < bx0 - pad or lcx - rx_clr > bx1 + pad or lcy + ry_clr < by0 - pad or lcy - ry_clr > by1 + pad):
                return True
        return False

    def _is_clear(tx: int, ty: int) -> tuple[bool, float]:
        lcx = tx + 0.5 * mw_est
        lcy = ty + 0.5 * mh_est + 4.0 * scale_y
        if tx < min_tx or tx > max_tx or ty < min_ty or ty > max_ty:
            return False, -1.0
        if _box_collides(lcx, lcy, val_boxes, 14.0 * scale):
            return False, -0.5
        if _box_collides(lcx, lcy, bar_boxes, 12.0 * scale):
            return False, -0.25
        d2 = ((all_arrow_pts[:, 0] - lcx) / rx_clr) ** 2 + ((all_arrow_pts[:, 1] - lcy) / ry_clr) ** 2
        min_d2 = float(np.min(d2)) if len(d2) else 9.0
        return min_d2 >= 1.0, min_d2

    short_idx = int(np.argmin([bt[0] for bt in bar_tip_coords]))
    short_right = float(bar_val_right_x[short_idx]) if short_idx < len(bar_val_right_x) else float(bar_tip_coords[short_idx][0])
    right_of_arrow_tx = min(max_tx, max(min_tx, int(round(arr_max_x + 22.0 * scale + loop_rx_real - 0.5 * mw_est))))
    above_arrow_ty = max(min_ty, int(round(arr_min_y - 22.0 * scale - loop_ry_real - 0.5 * mh_est - 4.0 * scale_y)))
    cand_y0 = max(min_ty, min(max_ty, int(round(bar_tip_coords[0][1] - 0.5 * mh_est))))
    cand_ymid = max(min_ty, min(max_ty, int(round(0.5 * (bar_tip_coords[0][1] + bar_tip_coords[-1][1]) - 0.5 * mh_est))))

    candidates: list[tuple[int, int]] = [
        (right_of_arrow_tx, cand_y0),
        (right_of_arrow_tx, cand_ymid),
        (right_of_arrow_tx, min_ty),
        (max_tx, cand_y0),
        (max_tx, cand_ymid),
        (max_tx, min_ty),
        (min(max_tx, max(min_tx, int(round(apex_x - 0.5 * mw_est)))), above_arrow_ty),
        (max_tx, above_arrow_ty),
        (min(max_tx, max(min_tx, int(round(short_right + loop_rx_real + 24.0 * scale_x - 0.5 * mw_est)))), int(round(bar_tip_coords[short_idx][1] - 0.5 * mh_est))),
        (min(max_tx, max(min_tx, int(round(max(bar_val_right_x) + loop_rx_real + 20.0 * scale_x - 0.5 * mw_est)))), cand_y0),
    ]
    if val_boxes:
        candidates.extend([
            (max(min_tx, min(max_tx, int(round(apex_x - 0.5 * mw_est)))), max(min_ty, int(round(min(v[1] for v in val_boxes) - 1.3 * ry_clr - mh_est)))),
            (max(min_tx, min(max_tx, int(round(apex_x - 0.5 * mw_est)))), min(max_ty, int(round(max(v[3] for v in val_boxes) + 0.5 * ry_clr)))),
        ])

    for tx, ty in candidates:
        ok, _ = _is_clear(tx, ty)
        if ok:
            return tx, ty

    best_xy = candidates[0]
    best_score = -999.0
    for gx in np.linspace(min_tx, max_tx, 9):
        for gy in np.linspace(min_ty, max_ty, 7):
            tx, ty = int(round(gx)), int(round(gy))
            ok, sc = _is_clear(tx, ty)
            if ok:
                return tx, ty
            if sc > best_score:
                best_score = sc
                best_xy = (tx, ty)
    return best_xy


def render_data_stamp_rgba_frame(
    stamp: dict[str, Any],
    t_rel: float,
    total_dur: float,
    *,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
    max_y_frac: float | None = None,
) -> Image.Image:
    """
    Renders a single `width x height` RGBA frame of the R70-M Hand-Drawn HERO Graph (`Y = 12%..62%`, or compacted
    above `max_y_frac` when overlaying a Canonical I02 dark-void lower-brain backdrop).
    Zero rectangular background card (`alpha == 0` outside hand-drawn strokes and handwritten labels).
    Dispatches all non-legacy presets/layers/panels/modes to `pipeline.charts.render_chart_spec_rgba_frame`
    while keeping classic 2-3 bar `bar_compare` 100% pixel-identical when `max_y_frac is None`.
    """
    if not is_legacy_bar_compare_only(stamp):
        ctx = {
            "draw_stroke_fn": draw_tapered_hand_stroke,
            "draw_text_fn": _draw_text_with_soft_halo,
            "load_font_fn": _load_hand_font,
            "arrow_fn": compute_natural_arrow_geometry,
            "loop_fn": compute_open_ellipse_loop,
        }
        return render_chart_spec_rgba_frame(
            stamp,
            t_rel,
            total_dur,
            width=width,
            height=height,
            ctx=ctx,
            max_y_frac=max_y_frac,
        )

    scale_x = width / 1080.0
    scale_y = height / 1920.0
    scale = min(scale_x, scale_y)
    y_lo_frac, y_hi_frac = DATA_STAMP_Y_FRAC_RANGE
    eff_hi_frac = min(y_hi_frac, max(y_lo_frac + 0.18, float(max_y_frac))) if max_y_frac is not None else y_hi_frac
    compact_dark_void = max_y_frac is not None and eff_hi_frac < 0.48

    fade_in = min(1.0, max(0.0, t_rel / 0.22))
    fade_out = min(1.0, max(0.0, (total_dur - t_rel) / 0.28))
    master_alpha = min(fade_in, fade_out)

    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    if master_alpha <= 0.01:
        return canvas

    bars = [b for b in (stamp.get("bars") or []) if isinstance(b, dict)][:3]
    if len(bars) < 2:
        return canvas

    style = str(stamp.get("style") or ("crayon" if "marshmallow" in str(stamp.get("title") or "").lower() else DATA_STAMP_DEFAULT_STYLE)).strip().lower()
    if style not in ("crayon", "ink_pen", "marker", "chalk"):
        style = "crayon"

    def _a(alpha_base: int) -> int:
        return max(0, min(255, int(round(alpha_base * master_alpha))))

    # 3-platform HERO safe viewport geometry: Y = 12% .. 62% (or compacted above lower I02 brain), X <= UNIVERSAL_SAFE_X_RIGHT_PX
    x_left = int(round(56 * scale_x))
    x_right = int(round(UNIVERSAL_SAFE_X_RIGHT_PX * scale_x))
    y_top = int(math.ceil(height * y_lo_frac))
    y_bot = int(round(height * eff_hi_frac))

    f_title = _load_hand_font(int(round(56 * scale_y)), expressive_accent=False)
    f_label = _load_hand_font(int(round(50 * scale_y)), expressive_accent=False)
    f_val = _load_hand_font(int(round(66 * scale_y)), expressive_accent=False)
    f_mult = _load_hand_font(int(round(92 * scale_y)), expressive_accent=True)
    f_cite = _load_hand_font(int(round(32 * scale_y)), expressive_accent=False)

    # Timeline phases scaled gracefully to total_dur (works for both 4.2s and 6.0s spans)
    draw_window = max(1.8, min(4.2, total_dur - 0.55))
    norm_p = max(0.0, min(1.0, t_rel / draw_window))

    p_axis = _ease_out_cubic(norm_p / 0.12)
    p_bar0 = _ease_out_cubic((norm_p - 0.08) / 0.22)
    p_bar1 = _ease_out_cubic((norm_p - 0.28) / 0.36)
    p_arrow_shaft = _ease_in_out_cubic((norm_p - 0.62) / 0.18)
    arrow_shaft_done_t = 0.80 * draw_window
    p_arrow_wings = _ease_out_cubic((t_rel - (arrow_shaft_done_t + 0.08)) / 0.12)
    p_loop = _ease_in_out_cubic((norm_p - 0.80) / 0.18)

    # 1. Hand-written title + warm cream chalk/crayon underline stroke
    header_txt = str(stamp.get("title") or "Study Comparison").strip()
    if header_txt.isupper():
        header_txt = header_txt.title()
    title_y = y_top + int(round((4 if compact_dark_void else 18) * scale_y))
    tbbox = _draw_text_with_soft_halo(
        canvas,
        (x_left + int(round(8 * scale_x)), title_y),
        header_txt,
        f_title,
        (255, 248, 232, _a(252)),
        halo_alpha=_a(175),
    )
    ul_y = tbbox[3] + int(round((8 if compact_dark_void else 12) * scale_y))
    ul_u = np.linspace(0.0, 1.0, 48, dtype=np.float32)
    ul_pts = np.column_stack([
        x_left + (min(x_right - int(round(40 * scale_x)), tbbox[2] + int(round(18 * scale_x))) - x_left) * ul_u,
        ul_y + (2.5 * scale_y) * np.sin(2.0 * np.pi * 1.2 * ul_u + 0.3),
    ]).astype(np.float32)
    ul_w = (5.5 * scale * (0.45 + 0.55 * np.sin(np.pi * ul_u))).astype(np.float32)
    draw_tapered_hand_stroke(
        canvas,
        ul_pts,
        ul_w,
        (255, 214, 112),
        alpha=_a(225),
        progress=p_axis,
        style=style,
        seed=11,
    )

    # 2. Hand-drawn vertical baseline axis on the left of the bars
    axis_x = x_left + int(round(28 * scale_x))
    if compact_dark_void:
        row0_label_y = ul_y + int(round(26 * scale_y))
        row0_bar_y = row0_label_y + int(round(56 * scale_y))
        row_gap = int(round(166 * scale_y)) if len(bars) == 2 else int(round(122 * scale_y))
        last_bar_y = row0_bar_y + (len(bars) - 1) * row_gap + int(round(68 * scale_y))
    else:
        row0_label_y = ul_y + int(round(62 * scale_y))
        row0_bar_y = row0_label_y + int(round(78 * scale_y))
        row_gap = int(round(235 * scale_y)) if len(bars) == 2 else int(round(175 * scale_y))
        last_bar_y = row0_bar_y + (len(bars) - 1) * row_gap + int(round(92 * scale_y))
    ax_u = np.linspace(0.0, 1.0, 56, dtype=np.float32)
    ax_end_y = min(y_bot - int(round((54 if compact_dark_void else 95) * scale_y)), last_bar_y)
    ax_pts = np.column_stack([
        axis_x + (2.0 * scale_x) * np.sin(2.0 * np.pi * 1.4 * ax_u + 0.8),
        (row0_label_y + int(round(12 * scale_y))) * (1.0 - ax_u) + ax_end_y * ax_u,
    ]).astype(np.float32)
    ax_w = (6.8 * scale * (0.50 + 0.50 * np.sin(np.pi * ax_u))).astype(np.float32)
    draw_tapered_hand_stroke(
        canvas,
        ax_pts,
        ax_w,
        (242, 238, 226),
        alpha=_a(235),
        progress=p_axis,
        style="ink_pen" if style == "ink_pen" else style,
        seed=23,
    )

    # 3. Progressive Crayon / Pen Comparison Stroke Bars (HERO thick multi-pass bars!)
    probe_lbl_d = ImageDraw.Draw(canvas)
    max_lbl_px = 0
    for b_s in bars:
        tv = float(b_s.get("value") or 0.0)
        u_s = _display_unit(b_s.get("unit") or "")
        is_i = abs(tv - round(tv)) < 1e-6
        b_dec = 0 if is_i else (2 if abs(tv * 10.0 - round(tv * 10.0)) >= 0.005 else 1)
        s_txt = f"{_format_num(tv, is_i, b_dec)} {u_s}".strip()
        bb = probe_lbl_d.textbbox((0, 0), s_txt, font=f_val)
        max_lbl_px = max(max_lbl_px, int(max(0, bb[2] - bb[0])))
    right_pad_px = max(int(round(240 * scale_x)), max_lbl_px + int(round(36 * scale_x)))
    bar_start_x = axis_x + int(round(26 * scale_x))
    bar_max_len = max(120.0 * scale_x, float((x_right - right_pad_px) - bar_start_x))
    max_val = max(max(0.01, float(b.get("value") or 0.0)) for b in bars)
    base_val = float(bars[0].get("value") or 0.0)

    palette = [
        (238, 114, 104),  # Warm coral-red crayon stub (Broken Promise)
        (68, 228, 162),   # Bright mint-emerald crayon/marker (Kept Promise)
        (92, 206, 255),   # Sky-cyan third group if 3 bars
    ]

    bar_tip_coords: list[tuple[float, float]] = []
    bar_val_right_x: list[float] = []
    bar_val_full_bboxes: list[tuple[float, float, float, float]] = []
    bar_stroke_bboxes: list[tuple[float, float, float, float]] = []
    for r_i, b_spec in enumerate(bars):
        lbl_y = row0_label_y + r_i * row_gap
        by_center = row0_bar_y + r_i * row_gap + int(round(32 * scale_y))
        lbl = str(b_spec.get("label") or f"Group {r_i + 1}").strip()
        target_v = float(b_spec.get("value") or 0.0)
        unit = _display_unit(b_spec.get("unit") or "")
        is_int = abs(target_v - round(target_v)) < 1e-6
        val_decimals = 0 if is_int else (2 if abs(target_v * 10.0 - round(target_v * 10.0)) >= 0.005 else 1)
        prog_r = p_bar0 if r_i == 0 else p_bar1
        rgb_bar = palette[min(r_i, len(palette) - 1)]

        if prog_r > 0.02:
            _draw_text_with_soft_halo(
                canvas,
                (bar_start_x, lbl_y),
                lbl,
                f_label,
                (248, 245, 236, _a(int(round(248 * min(1.0, prog_r * 2.2))))),
                halo_alpha=_a(165),
            )

        full_bar_len = max(52.0 * scale_x, bar_max_len * (max(0.0, target_v) / max_val))
        bar_end_x = bar_start_x + full_bar_len
        bar_tip_coords.append((bar_end_x, float(by_center)))
        bar_stroke_bboxes.append((float(bar_start_x), float(by_center - 20.0 * scale_y), float(bar_end_x), float(by_center + 20.0 * scale_y)))

        if prog_r > 0.01:
            bu = np.linspace(0.0, 1.0, 72, dtype=np.float32)
            # Two layered overlapping thick hand-colored crayon passes for rich hand-drawn body
            for pass_k, (y_off, w_mult, al_base) in enumerate(((-7.0, 34.0, 244), (7.5, 31.0, 232))):
                b_pts = np.column_stack([
                    bar_start_x + full_bar_len * bu,
                    by_center + y_off * scale_y + (2.4 * scale_y) * np.sin(2.0 * np.pi * (1.5 + 0.4 * pass_k) * bu + r_i),
                ]).astype(np.float32)
                b_w = (w_mult * scale * (0.72 + 0.28 * np.sin(np.pi * np.clip(bu * 0.92 + 0.04, 0.0, 1.0)))).astype(np.float32)
                draw_tapered_hand_stroke(
                    canvas,
                    b_pts,
                    b_w,
                    rgb_bar,
                    alpha=_a(al_base),
                    progress=prog_r,
                    style=style,
                    seed=100 + r_i * 17 + pass_k,
                )

            cur_v = (
                target_v * prog_r
                if r_i == 0
                else (min(base_val, target_v) + (target_v - min(base_val, target_v)) * prog_r)
            )
            cur_x = bar_start_x + full_bar_len * prog_r
            val_str = f"{_format_num(cur_v, is_int, val_decimals)} {unit}".strip()
            vbbox = _draw_text_with_soft_halo(
                canvas,
                (int(round(cur_x + 22 * scale_x)), int(round(by_center - 38 * scale_y))),
                val_str,
                f_val,
                (255, 252, 240, _a(255)),
                halo_alpha=_a(180),
            )
            full_val_str = f"{_format_num(target_v, is_int, val_decimals)} {unit}".strip()
            fvb_raw = ImageDraw.Draw(canvas).textbbox((0, 0), full_val_str, font=f_val)
            full_val_w = max(0, fvb_raw[2] - fvb_raw[0])
            full_val_h = max(0, fvb_raw[3] - fvb_raw[1])
            fvx0 = int(round(bar_start_x + full_bar_len + 22 * scale_x))
            fvy0 = int(round(by_center - 38 * scale_y))
            bar_val_right_x.append(float(fvx0 + full_val_w))
            bar_val_full_bboxes.append((float(fvx0 + fvb_raw[0]), float(fvy0 + fvb_raw[1]), float(fvx0 + fvb_raw[0] + full_val_w), float(fvy0 + fvb_raw[1] + full_val_h)))
            _ = vbbox

    # 4. Natural Hand-Drawn Curved Comparison Arrow (bar 0 tip -> bar[-1] tip) + Hand-Circled `4×`
    badge_raw = str(stamp.get("multiplier_badge") or "").strip()
    if len(bar_tip_coords) >= 2 and (badge_raw or max_val > max(0.01, base_val) * 1.25):
        m_match = re.search(r"(\d+(?:\.\d+)?)\s*[x×]|[x×]\s*(\d+(?:\.\d+)?)", badge_raw, flags=re.IGNORECASE)
        if m_match:
            num_tok = m_match.group(1) or m_match.group(2)
            mult_label = f"{num_tok}×"
        elif badge_raw:
            mult_label = badge_raw.split()[0]
        else:
            ratio_v = max_val / max(0.01, base_val)
            mult_label = f"{int(round(ratio_v))}×" if abs(ratio_v - round(ratio_v)) < 0.12 else f"{ratio_v:.1f}×"

        start_x_clean = (
            bar_val_right_x[0] + 18.0 * scale_x
            if bar_val_right_x
            else bar_tip_coords[0][0] + 18.0 * scale_x
        )
        p_start = (start_x_clean, bar_tip_coords[0][1] - 4.0 * scale_y)
        p_target = (bar_tip_coords[-1][0] - 6.0 * scale_x, bar_tip_coords[-1][1] - 28.0 * scale_y)
        arrow_geo = compute_natural_arrow_geometry(
            p_start,
            p_target,
            base_width=8.8,
            scale=scale,
            seed=404,
        )
        arrow_rgb = (255, 214, 92)
        if p_arrow_shaft > 0.01:
            draw_tapered_hand_stroke(
                canvas,
                arrow_geo["shaft_points"],
                arrow_geo["shaft_widths"],
                arrow_rgb,
                alpha=_a(250),
                progress=p_arrow_shaft,
                style=style,
                seed=405,
            )
        if p_arrow_wings > 0.01:
            draw_tapered_hand_stroke(
                canvas,
                arrow_geo["left_wing_points"],
                arrow_geo["left_wing_widths"],
                arrow_rgb,
                alpha=_a(252),
                progress=p_arrow_wings,
                style=style,
                seed=406,
            )
            draw_tapered_hand_stroke(
                canvas,
                arrow_geo["right_wing_points"],
                arrow_geo["right_wing_widths"],
                arrow_rgb,
                alpha=_a(252),
                progress=min(1.0, max(0.0, (p_arrow_wings - 0.18) / 0.82)),
                style=style,
                seed=407,
            )

        if p_arrow_shaft > 0.55:
            txt_prog = min(1.0, (p_arrow_shaft - 0.55) / 0.35)
            # R85: Place hand-lettered multiplier + highlight loop strictly clear of arrow, bars, and value bboxes!
            probe_m = ImageDraw.Draw(canvas)
            m_tb = probe_m.textbbox((0, 0), mult_label, font=f_mult)
            mw_est = max(24.0, float(m_tb[2] - m_tb[0]))
            mh_est = max(24.0, float(m_tb[3] - m_tb[1]))
            est_rx = max(48.0 * scale_x, 0.66 * mw_est + 18.0 * scale_x)
            est_ry = max(34.0 * scale_y, 0.62 * mh_est + 12.0 * scale_y)
            tx_ink, ty_ink = resolve_multiplier_badge_placement(
                arrow_geo=arrow_geo,
                val_boxes=bar_val_full_bboxes,
                bar_boxes=bar_stroke_bboxes,
                bar_tip_coords=bar_tip_coords,
                bar_val_right_x=bar_val_right_x,
                mw_est=mw_est,
                mh_est=mh_est,
                est_rx=est_rx,
                est_ry=est_ry,
                bar_start_x=float(bar_start_x),
                x_left=float(x_left),
                x_right=float(x_right),
                ul_y=float(ul_y),
                y_bot=float(y_bot),
                scale_x=scale_x,
                scale_y=scale_y,
                scale=scale,
            )
            cx_m = tx_ink - int(round(m_tb[0]))
            cy_m = ty_ink - int(round(m_tb[1]))
            mbbox = _draw_text_with_soft_halo(
                canvas,
                (cx_m, cy_m),
                mult_label,
                f_mult,
                (255, 232, 118, _a(int(round(255 * txt_prog)))),
                halo_alpha=_a(int(round(185 * txt_prog))),
                halo_blur_px=5.0,
            )
            if p_loop > 0.01:
                loop_cx = 0.5 * (mbbox[0] + mbbox[2])
                loop_cy = 0.5 * (mbbox[1] + mbbox[3]) + 4.0 * scale_y
                loop_rx = max(48.0 * scale_x, 0.66 * (mbbox[2] - mbbox[0]) + 18.0 * scale_x)
                loop_ry = max(34.0 * scale_y, 0.62 * (mbbox[3] - mbbox[1]) + 12.0 * scale_y)
                l_pts, l_w = compute_open_ellipse_loop(
                    (loop_cx, loop_cy),
                    rx=loop_rx,
                    ry=loop_ry,
                    turns=1.32,
                    tilt_deg=-6.5,
                    base_width=6.8,
                    scale=scale,
                    seed=808,
                )
                draw_tapered_hand_stroke(
                    canvas,
                    l_pts,
                    l_w,
                    (255, 136, 96),
                    alpha=_a(244),
                    progress=p_loop,
                    style=style,
                    seed=809,
                )

    # 5. Subtle fine-ink source citation footer at bottom of HERO zone (well above Y=68% subtitles)
    cite = str(stamp.get("source_citation") or "").strip()
    if cite and norm_p >= 0.18:
        cite_alpha = _a(int(round(215 * min(1.0, (norm_p - 0.18) / 0.25))))
        footer_y = min(
            y_bot - int(round((38 if compact_dark_void else 48) * scale_y)),
            last_bar_y + int(round((14 if compact_dark_void else 22) * scale_y)),
        )
        disp_cite = f"Study: {cite}"[:68]
        max_cw = max(int(round(160 * scale_x)), x_right - int(round(14 * scale_x)) - axis_x)
        probe_c = ImageDraw.Draw(canvas)
        while len(disp_cite) > 12:
            cb = probe_c.textbbox((0, 0), disp_cite, font=f_cite)
            if (cb[2] - cb[0]) <= max_cw:
                break
            if " " in disp_cite:
                disp_cite = disp_cite.rsplit(" ", 1)[0].rstrip(" ·,;:-")
            else:
                disp_cite = disp_cite[:-2]
        _draw_text_with_soft_halo(
            canvas,
            (axis_x, footer_y),
            disp_cite,
            f_cite,
            (226, 224, 214, cite_alpha),
            halo_alpha=int(cite_alpha * 0.72),
            halo_blur_px=3.0,
        )

    top_y0 = int(math.ceil(height * float(y_lo_frac)))
    sub_y0 = int(round(height * 0.68))
    safe_x_end = min(width, int(round(UNIVERSAL_SAFE_X_RIGHT_PX * scale_x)) + 1)
    arr = np.asarray(canvas, dtype=np.uint8)
    if (
        np.any(arr[:top_y0, :, 3] > 0)
        or np.any(arr[sub_y0:, :, 3] > 0)
        or (safe_x_end < width and np.any(arr[:, safe_x_end:, 3] > 0))
    ):
        arr = arr.copy()
        arr[:top_y0, :, :] = 0
        arr[sub_y0:, :, :] = 0
        if safe_x_end < width:
            arr[:, safe_x_end:, :] = 0
        canvas = Image.fromarray(arr, mode="RGBA")
    return canvas


def resolve_data_stamp_windows(
    script_doc: dict[str, Any] | None,
    sentence_spans: list[dict[str, Any]],
    total_duration_sec: float,
) -> list[dict[str, Any]]:
    """
    Maps `script_doc['data_stamps']` to `[start_sec, end_sec]` windows covering the target sentence(s)
    plus complexity-aware hold time (`4.2s..7.5s` via `compute_stamp_complexity_and_hold_sec`).
    """
    if not isinstance(script_doc, dict):
        return []
    raw_stamps = script_doc.get("data_stamps")
    if not isinstance(raw_stamps, list) or not raw_stamps:
        return []
    span_by_s = {int(sp["sentence_index"]): sp for sp in sentence_spans if isinstance(sp, dict) and "sentence_index" in sp}
    resolved: list[dict[str, Any]] = []
    for st in raw_stamps[:DATA_STAMP_MAX_PER_EPISODE]:
        if not isinstance(st, dict):
            continue
        s_idx = int(st.get("sentence_index") or 0)
        e_idx = int(st.get("end_sentence_index") or s_idx)
        sp = span_by_s.get(s_idx)
        if not sp:
            continue
        sp_end = span_by_s.get(max(s_idx, e_idx), sp)
        t0 = max(0.05, float(sp["start_sec"]) + float(st.get("offset_sec") or 0.04))
        complexity, rec_hold = compute_stamp_complexity_and_hold_sec(st)
        full_sent_plus_hold = (float(sp_end["end_sec"]) - t0) + float(DATA_STAMP_MIN_HOLD_SEC)
        raw_dur = float(st.get("duration_sec") or max(rec_hold, full_sent_plus_hold))
        next_sp = span_by_s.get(max(s_idx, e_idx) + 1)
        hard_end_cap = (
            min(total_duration_sec - 0.15, float(next_sp["start_sec"]) - 0.08)
            if next_sp and st.get("duration_sec") is None and full_sent_plus_hold >= rec_hold
            else (total_duration_sec - 0.15)
        )
        t1 = min(max(t0 + 1.4, hard_end_cap), t0 + raw_dur)
        if resolved and t0 < resolved[-1]["end_sec"] + 0.15:
            t0 = round(resolved[-1]["end_sec"] + 0.15, 3)
            t1 = max(t0 + 1.4, t1)
        if t1 - t0 >= 1.0:
            resolved.append(
                {
                    **st,
                    "start_sec": round(t0, 3),
                    "end_sec": round(t1, 3),
                    "duration_sec": round(t1 - t0, 3),
                    "complexity": complexity,
                }
            )
    return resolved


def _measure_stamp_zone_mean_luma(video_in: Path, t_sample: float, width: int, height: int) -> float:
    """Measures mean grayscale luminance across the upper chart zone (`y = 0.08..0.60`, `x = 0.06..0.88`)."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_in))
        if not cap.isOpened():
            return 0.0
        try:
            v_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fi = max(0, min(max(0, tot - 1), int(round(max(0.0, t_sample) * v_fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                return 0.0
            if bgr.shape[1] != width or bgr.shape[0] != height:
                bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA)
            y0, y1 = int(round(0.08 * height)), int(round(0.60 * height))
            x0, x1 = int(round(0.06 * width)), int(round(0.88 * width))
            gray = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            return float(np.mean(gray)) if gray.size > 0 else 0.0
        finally:
            cap.release()
    except Exception:
        return 0.0


def _measure_upper_chart_headroom_luma(
    video_path: Path,
    t_sec: float,
    width: int,
    height: int,
) -> float:
    """Measures mean luminance in the upper Study-chart headroom (`Y=8%..42%`, `X=6%..88%`) to detect pure dark studio voids (e.g. Canonical I02 brain backdrops)."""
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return 255.0
        try:
            v_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            fi = max(0, min(max(0, tot - 1), int(round(max(0.0, float(t_sec)) * v_fps))))
            cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
            ok, bgr = cap.read()
            if not ok or bgr is None:
                return 255.0
            if bgr.shape[1] != width or bgr.shape[0] != height:
                bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA)
            y0, y1 = int(round(0.08 * height)), int(round(0.42 * height))
            x0, x1 = int(round(0.06 * width)), int(round(0.88 * width))
            gray = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
            return float(np.mean(gray)) if gray.size > 0 else 255.0
        finally:
            cap.release()
    except Exception:
        return 255.0


def _detect_dark_void_lower_subject_top_y(
    video_path: Path,
    sample_times: list[float],
    width: int,
    height: int,
) -> int | None:
    """
    On a dark-void lower-subject backdrop (e.g. Canonical I02 lower-44% 3D brain over `#040711`),
    returns the highest (minimum Y) top-edge pixel row of the lower subject across `sample_times`
    within `Y = 30%..66%` so the Study chart can compact strictly above the brain with zero overlap.
    """
    try:
        import cv2

        cap = cv2.VideoCapture(str(video_path))
        if not cap.isOpened():
            return None
        try:
            v_fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)
            tot = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
            y0, y1 = int(round(0.30 * height)), int(round(0.66 * height))
            x0, x1 = int(round(0.08 * width)), int(round(0.92 * width))
            top_hits: list[int] = []
            for t_s in sample_times:
                fi = max(0, min(max(0, tot - 1), int(round(max(0.0, float(t_s)) * v_fps))))
                cap.set(cv2.CAP_PROP_POS_FRAMES, fi)
                ok, bgr = cap.read()
                if not ok or bgr is None:
                    continue
                if bgr.shape[1] != width or bgr.shape[0] != height:
                    bgr = cv2.resize(bgr, (width, height), interpolation=cv2.INTER_AREA)
                band = cv2.cvtColor(bgr[y0:y1, x0:x1], cv2.COLOR_BGR2GRAY)
                if band.size == 0:
                    continue
                row_p95 = np.percentile(band, 95, axis=1)
                active = row_p95 >= 40.0
                for k in range(0, max(0, len(active) - 3)):
                    if bool(active[k]) and bool(active[k + 1]) and bool(active[k + 2]) and bool(active[k + 3]):
                        top_hits.append(y0 + k)
                        break
            return min(top_hits) if top_hits else None
        finally:
            cap.release()
    except Exception:
        return None


def _build_bright_wall_contrast_card_rgba(
    chart_bbox: tuple[int, int, int, int],
    *,
    width: int,
    height: int,
    fade_alpha: float = 1.0,
) -> Image.Image:
    """
    Renders a sleek rounded matte dark-slate backdrop card (`rgba(10, 14, 24, 218)` = 85.5% opacity)
    when the underlying wall is bright (`mean_luma >= 110`), guaranteeing WCAG contrast >= 10.0 (>= 7.0 hard gate)
    for white/amber/cyan/coral `R70-M` study chart typography and bars.
    """
    scale_x = width / 1080.0
    scale_y = height / 1920.0
    pad_x = int(round(32 * scale_x))
    pad_y = int(round(26 * scale_y))
    x0 = max(int(round(42 * scale_x)), chart_bbox[0] - pad_x)
    y0 = max(int(round(86 * scale_y)), chart_bbox[1] - pad_y)
    x1 = min(int(round((UNIVERSAL_SAFE_X_RIGHT_PX + 16) * scale_x)), chart_bbox[2] + pad_x)
    y1 = min(int(round(0.645 * height)), chart_bbox[3] + pad_y)
    if x1 <= x0 + 40 or y1 <= y0 + 40:
        return Image.new("RGBA", (width, height), (0, 0, 0, 0))

    card = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(card)
    rad = max(12, int(round(28 * min(scale_x, scale_y))))
    fill_a = max(0, min(255, int(round(218 * max(0.0, min(1.0, fade_alpha))))))
    rim_a = max(0, min(255, int(round(46 * max(0.0, min(1.0, fade_alpha))))))
    draw.rounded_rectangle(
        (x0, y0, x1, y1),
        radius=rad,
        fill=(10, 14, 24, fill_a),
        outline=(255, 255, 255, rim_a),
        width=max(1, int(round(2 * min(scale_x, scale_y)))),
    )
    return card


def composite_data_stamps_on_video(
    video_in: Path,
    video_out: Path,
    resolved_stamps: list[dict[str, Any]],
    *,
    fps: int = 30,
    width: int = VIDEO_WIDTH,
    height: int = VIDEO_HEIGHT,
) -> list[tuple[float, float]]:
    """
    Renders RGBA PNG sequences for each resolved HERO `data_stamp`, applies an upper-viewport cinema focus-pull
    (`gblur=sigma=DATA_STAMP_BG_BLUR_SIGMA` + `DATA_STAMP_BG_DIM` darkening across `Y = 0..65%` so burned-in
    `Y = 73%` subtitles remain 100% razor-sharp), and composites the hand-drawn sketch onto `video_in` -> `video_out`.
    """
    if not resolved_stamps:
        return []
    ff = _ffmpeg_exe()
    applied: list[tuple[float, float]] = []
    blur_h = int(round(height * 0.66))
    blur_h -= blur_h % 2
    sigma = max(4, int(DATA_STAMP_BG_BLUR_SIGMA))
    keep_mul = round(max(0.35, min(0.85, 1.0 - float(DATA_STAMP_BG_DIM) * 1.25)), 3)

    from pipeline.media_cache import atomic_commit_from_scratch, ram_tempdir

    with ram_tempdir(prefix="aab_datastamp_v2_") as td:
        td_p = Path(td)
        mask_path = td_p / "focus_mask.png"
        if DATA_STAMP_HERO_MODE:
            y_idx = np.arange(blur_h, dtype=np.float32)
            feather_y0 = float(int(round(height * 0.55)))
            u_f = np.clip((y_idx - feather_y0) / max(1.0, float(blur_h) - feather_y0), 0.0, 1.0)
            alpha_col = np.round(255.0 * 0.5 * (1.0 + np.cos(np.pi * u_f))).astype(np.uint8)
            mask_arr = np.repeat(alpha_col[:, None], width, axis=1)
            Image.fromarray(mask_arr, mode="L").save(mask_path, format="PNG", compress_level=1)

        cmd: list[str] = [ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y", "-i", str(video_in)]
        filter_parts: list[str] = []
        prev_lbl = "0:v"
        next_in_idx = 1

        for idx, st in enumerate(resolved_stamps):
            t0 = float(st["start_sec"])
            t1 = float(st["end_sec"])
            dur = max(1.0, t1 - t0)
            n_frames = max(12, int(math.ceil(dur * fps)))
            seq_dir = td_p / f"stamp_{idx}"
            seq_dir.mkdir(parents=True, exist_ok=True)
            bg_luma = _measure_stamp_zone_mean_luma(Path(video_in), 0.5 * (t0 + t1), width, height)
            upper_headroom_luma = _measure_upper_chart_headroom_luma(Path(video_in), 0.5 * (t0 + t1), width, height)
            use_dark_card = bg_luma >= 110.0
            # When the upper chart headroom (Y=8%..42%) is already a clean dark studio void (e.g. Canonical I02
            # lower-44% brain backdrop, upper_headroom_luma < 24.0), skip the redundant Y=0..66% blur+dim scrim so
            # the lower 3D brain stays razor-sharp and full brightness without a sudden pop when the chart ends.
            apply_hero_blur_dim = bool(DATA_STAMP_HERO_MODE) and (upper_headroom_luma >= 24.0)
            compact_max_y_frac: float | None = None
            if upper_headroom_luma < 24.0:
                subj_top_y = _detect_dark_void_lower_subject_top_y(
                    Path(video_in),
                    [t0 + 0.15 * dur, t0 + 0.50 * dur, t0 + 0.85 * dur],
                    width,
                    height,
                )
                if subj_top_y is not None:
                    pad_px = 46.0 * (height / 1920.0)
                    compact_max_y_frac = min(
                        float(DATA_STAMP_Y_FRAC_RANGE[1]),
                        max(0.365, (float(subj_top_y) - pad_px) / float(height)),
                    )
            card_bbox: tuple[int, int, int, int] | None = None
            if use_dark_card:
                im_probe = render_data_stamp_rgba_frame(
                    st,
                    t_rel=dur * 0.82,
                    total_dur=dur,
                    width=width,
                    height=height,
                    max_y_frac=compact_max_y_frac,
                )
                card_bbox = im_probe.getbbox()
            fade_d_card = min(0.22, dur * 0.14)
            for f_i in range(n_frames):
                t_rel = f_i / float(fps)
                im = render_data_stamp_rgba_frame(
                    st,
                    t_rel=t_rel,
                    total_dur=dur,
                    width=width,
                    height=height,
                    max_y_frac=compact_max_y_frac,
                )
                if use_dark_card and card_bbox is not None:
                    f_in = min(1.0, max(0.0, t_rel / max(0.05, fade_d_card)))
                    f_out = min(1.0, max(0.0, (dur - t_rel) / max(0.05, fade_d_card)))
                    card_rgba = _build_bright_wall_contrast_card_rgba(
                        card_bbox, width=width, height=height, fade_alpha=min(f_in, f_out)
                    )
                    im = Image.alpha_composite(card_rgba, im)
                im.save(seq_dir / f"f_{f_i:04d}.png", format="PNG", compress_level=1)
            cmd.extend(["-framerate", str(fps), "-i", str(seq_dir / "f_%04d.png")])
            in_idx = next_in_idx
            next_in_idx += 1

            if apply_hero_blur_dim:
                cmd.extend(["-ss", f"{t0:.4f}", "-t", f"{dur:.4f}", "-i", str(video_in)])
                blur_src_idx = next_in_idx
                next_in_idx += 1
                cmd.extend(["-loop", "1", "-framerate", str(fps), "-t", f"{dur + 0.5:.3f}", "-i", str(mask_path)])
                mask_idx = next_in_idx
                next_in_idx += 1
                blurred_top = f"ds_blur_{idx}"
                feathered_top = f"ds_feath_{idx}"
                dim_merged = f"ds_dim_{idx}"
                fade_d = min(0.24, dur * 0.15)
                fade_out_rel = max(0.0, dur - fade_d)
                filter_parts.append(
                    f"[{blur_src_idx}:v]setpts=PTS-STARTPTS,"
                    f"crop={width}:{blur_h}:0:0,"
                    f"gblur=sigma={sigma},"
                    f"format=rgba,"
                    f"lutrgb=r='val*{keep_mul}':g='val*{keep_mul}':b='val*{min(1.0, keep_mul + 0.03):.3f}'[{blurred_top}]"
                )
                filter_parts.append(
                    f"[{blurred_top}][{mask_idx}:v]alphamerge,"
                    f"fade=t=in:st=0:d={fade_d:.4f}:alpha=1,"
                    f"fade=t=out:st={fade_out_rel:.4f}:d={fade_d:.4f}:alpha=1,"
                    f"setpts=PTS-STARTPTS+{t0:.4f}/TB[{feathered_top}]"
                )
                filter_parts.append(
                    f"[{prev_lbl}][{feathered_top}]overlay=0:0:format=auto:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[{dim_merged}]"
                )
                prev_lbl = dim_merged

            ov_lbl = f"st_pts_{idx}"
            out_lbl = f"v_out_{idx}"
            filter_parts.append(f"[{in_idx}:v]setpts=PTS-STARTPTS+{t0:.4f}/TB[{ov_lbl}]")
            filter_parts.append(
                f"[{prev_lbl}][{ov_lbl}]overlay=0:0:eof_action=pass:enable='between(t,{t0:.4f},{t1:.4f})'[{out_lbl}]"
            )
            prev_lbl = out_lbl
            applied.append((round(t0, 3), round(t1, 3)))

        tmp_out = td_p / "datastamp_out.mp4"
        cmd.extend(
            [
                "-threads",
                "2",
                "-filter_complex",
                ";".join(filter_parts),
                "-map",
                f"[{prev_lbl}]",
                "-c:v",
                "libx264",
                "-preset",
                "veryfast",
                "-crf",
                "17",
                "-pix_fmt",
                "yuv420p",
                str(tmp_out),
            ]
        )
        res = subprocess.run(cmd, capture_output=True, text=True, check=False, timeout=600, stdin=subprocess.DEVNULL)
        if res.returncode != 0 or not tmp_out.is_file():
            tmp_out.unlink(missing_ok=True)
            raise RuntimeError(f"DataStamp v2 ffmpeg overlay failed (rc={res.returncode}): {(res.stderr or '')[:350]}")
        atomic_commit_from_scratch(tmp_out, video_out)
    return applied


def seed_data_stamps_from_dossier(
    dossier: dict[str, Any] | None,
    sentences: list[str],
    *,
    max_stamps: int = DATA_STAMP_MAX_PER_EPISODE,
) -> list[dict[str, Any]]:
    """
    R70-M multi-chart seeder:
      1. First matches `core_facts[].stats` entries from `dossier` against `sentences` (spacing by `>= 4` sentences
         and rotating presets where possible).
      2. Falls back to extracting up to `max_stamps` numeric comparisons / percentages / counts across `sentences`.
    """
    if not isinstance(dossier, dict) or not sentences:
        return []
    if isinstance(dossier.get("dossier.json"), dict):
        dossier = dossier["dossier.json"]
    default_doi = str(
        dossier.get("doi")
        or dossier.get("primary_doi")
        or (dossier.get("primary_study") or {}).get("doi")
        or (dossier.get("layer_1_case") or {}).get("doi")
        or (dossier.get("three_layer_formula") or {}).get("layer_1_case", {}).get("doi")
        or ""
    ).strip()
    default_cite = str(
        dossier.get("citation_short")
        or (dossier.get("primary_study") or {}).get("citation")
        or (dossier.get("three_layer_formula") or {}).get("layer_1_case", {}).get("citation")
        or dossier.get("journal")
        or "Peer-reviewed study"
    ).strip()

    stamps: list[dict[str, Any]] = []
    used_sents: list[int] = []
    used_presets: list[str] = []

    def _can_place(s_i: int) -> bool:
        return all(abs(s_i - prev) >= DATA_STAMP_MIN_SENTENCE_GAP for prev in used_sents)

    core_facts = dossier.get("core_facts")
    if isinstance(core_facts, list):
        for cf in core_facts:
            if len(stamps) >= max_stamps:
                break
            if not isinstance(cf, dict) or not isinstance(cf.get("stats"), dict):
                continue
            st_meta = cf["stats"]
            preset = str(st_meta.get("preset") or route_chart_for_stat(st_meta.get("format"))).strip().lower()
            if used_presets and preset == used_presets[-1] and st_meta.get("alt_preset"):
                preset = str(st_meta["alt_preset"]).strip().lower()
            f_doi = str(st_meta.get("doi") or cf.get("doi") or default_doi).strip()
            f_cite = str(st_meta.get("source_citation") or cf.get("source_citation") or default_cite).strip()
            mode = str(st_meta.get("mode") or "study").strip().lower()
            if mode in ("study", "derived") and (not f_doi or not _DOI_RE.match(f_doi)):
                continue

            cand_nums = _extract_panel_candidate_numbers(st_meta)
            matched_s = 0
            for s_idx, sent in enumerate(sentences, start=1):
                if not _can_place(s_idx):
                    continue
                if cand_nums and any(_sentence_mentions_number(sent, v) for v in cand_nums):
                    matched_s = s_idx
                    break
            if matched_s == 0:
                continue

            entry: dict[str, Any] = {
                "sentence_index": matched_s,
                "mode": mode,
                "preset": preset,
                "chart": preset,
                "style": str(st_meta.get("style") or DATA_STAMP_DEFAULT_STYLE),
                "title": str(st_meta.get("title") or cf.get("label") or "Verified Study Data")[:48],
                "source_citation": f_cite,
                "doi": "" if mode == "illustrative" else f_doi,
            }
            for copy_k in ("bars", "groups", "series", "params", "unit", "percent", "highlighted_k", "total_n", "multiplier_badge", "concept", "fn"):
                if copy_k in st_meta:
                    entry[copy_k] = st_meta[copy_k]
            stamps.append(entry)
            used_sents.append(matched_s)
            used_presets.append(preset)

    return stamps


def seed_default_data_stamps_from_dossier(dossier: dict[str, Any] | None, sentences: list[str]) -> list[dict[str, Any]]:
    """Backward-compatible alias for `seed_data_stamps_from_dossier`."""
    return seed_data_stamps_from_dossier(dossier, sentences)
