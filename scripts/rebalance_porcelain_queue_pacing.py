"""
Idempotent audit & balanced documentary-pacing normalizer for all 65 queued `porcelain_cinematic_v7`
episodes in `BCI_Shorts_Channel/porcelain_rebalanced_queue.json` (Rule R66.4).

Targets the approved sweet-spot pacing across full-length ~147-165s Porcelain v7 episodes:
  - 47..49 clips (~46..48 cuts, ~3.0-3.2s average speech cut duration)
  - 0 holds spanning >= 3 sentences (<= PORCELAIN_V7_MAX_HOLD_SENTENCES = 2)
  - <= PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS (2) literal analogy cutaways, 0 chronometer/scale filler props
  - Same-scene multi-angle coverage (room wide <-> neck-down porcelain hands / instrument close-up,
    and whole-brain 3D circuit <-> anatomical cutaway zoom) preserving `scene_state` & `DQ3` anatomy locks.

Usage:
    python -X utf8 scripts/rebalance_porcelain_queue_pacing.py [--check-only]
"""

from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from pathlib import Path
from typing import Any

WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from pipeline import cli, config
from pipeline.config import (
    DIORAMA_CLIP_COUNT_DEFAULT,
    DIORAMA_V7_CAMERA_MOVES,
    DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO,
    DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO,
    PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS,
    PORCELAIN_V7_MAX_HOLD_SENTENCES,
    PORCELAIN_V7_STYLE_PROFILE,
    PORCELAIN_V7_TARGET_CLIP_MAX,
    PORCELAIN_V7_TARGET_CLIP_MIN,
)
from pipeline.depiction_rules import (
    normalize_porcelain_v7_brain_mode,
    normalize_porcelain_v7_grammar,
)
from pipeline.dynamic_episode_qa import (
    LITERAL_ANALOGY_SPECS,
    verify_pre_flow_contract,
)
from pipeline.flow_prompt_builder import build_flow_prompts, count_words
from pipeline.plain_language import find_anatomy_terms
from pipeline.prompt_quality_v5 import (
    _CHRONOMETER_PROP_RE,
    _LOW_IMPACT_SCALE_FILLER_RE,
    validate_production_diorama_v6,
)
from pipeline.publish import validate_diorama_paradox_title
from scripts.migrate_dossiers_porcelain_v7 import (
    _clean_porcelain_scene_text,
    _enrich_porcelain_cast_clip,
)

_TEXT_FIELDS: tuple[str, ...] = (
    "scene",
    "subject_action",
    "environment_backdrop",
    "environment",
    "action",
    "kinetic_action",
    "attire_and_hands",
    "prop_action",
    "consequence",
    "structure",
    "internal_mechanism",
    "analogy_world",
    "analogy_scene",
    "analogy_object",
    "comparison_action",
    "comparison_motion",
    "brain_scene",
    "maquette_scene",
)


def _is_brain_or_outro(clip: dict[str, Any]) -> bool:
    g_name = str(clip.get("grammar") or "")
    c_role = str(clip.get("cut_role") or "").strip().lower()
    return (
        g_name
        in (
            "porcelain_living_brain",
            "porcelain_data_sculpture",
            "lowpoly_living_brain",
            "lowpoly_matte_brain",
            "lowpoly_data_sculpture",
            "arch_brain_maquette",
            "frosted_crystal_specimen",
        )
        or bool(clip.get("brain_mode"))
        or c_role == "outro"
    )


_WIDE_VIEW_PREFIX_RE = re.compile(
    r"\b(?:over|across)\s+(?:an?\s+)?(?:(?:elevated|reverse|three-quarter|high-angle|locked|orthographic|architectural|full-bleed|wide|sunlit)\s+)*(?:wide\s+)?(?:view|shot|angle|frame)\s+(?:of|inside|across)\s+",
    flags=re.IGNORECASE,
)


def _strip_wide_camera_prefix_for_closeup(text: str) -> str:
    """Rewrites 'over an elevated wide view of a bright ...' -> 'inside a bright ...' on neck-down hands close-ups."""
    out = _WIDE_VIEW_PREFIX_RE.sub("inside ", str(text or ""))
    out = re.sub(
        r"^(?:an?\s+)?(?:(?:elevated|reverse|three-quarter|high-angle|locked|orthographic|architectural|full-bleed|wide)\s+)*(?:view|shot|angle|frame)\s+(?:of|inside|across)\s+",
        "",
        out,
        flags=re.IGNORECASE,
    )
    return re.sub(r"\s{2,}", " ", out).strip()


def _sanitize_filler_tokens(text: str, allow_chrono: bool) -> str:
    out = str(text or "")
    out = out.replace("(Low-Poly Pastel v7)", "").replace("pastel_analogy_court", "sunlit_studio_bench")
    if not allow_chrono:
        out = re.sub(
            r"\b(?:eight|ten|fifteen|five|two|three|sixty|thirty)-minute\s+sandglass(?:\s+timers?)?\b",
            "brushed-silver marker cylinder",
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(r"\bsandglass(?:es)?(?:\s+timers?)?\b", "brushed-silver marker cylinder", out, flags=re.IGNORECASE)
        out = re.sub(
            r"\b(?:mechanical\s+acoustic\s+)?interval\s+chimes?\b",
            "brushed-brass acoustic chime bar",
            out,
            flags=re.IGNORECASE,
        )
        out = re.sub(r"\btimer\s+bells?\b", "acoustic chime bar", out, flags=re.IGNORECASE)
        out = re.sub(r"\bcrosswalk\s+timers?\b", "crosswalk signal beacon", out, flags=re.IGNORECASE)
        out = re.sub(r"\btimers\b", "tally counters", out, flags=re.IGNORECASE)
        out = re.sub(r"\btimer\b", "tally counter", out, flags=re.IGNORECASE)
        out = _CHRONOMETER_PROP_RE.sub("polished brass counter", out)
    out = re.sub(r"\bwooden\s+neighborhood\s+dioramas\b", "architectural housing layout boards", out, flags=re.IGNORECASE)
    out = re.sub(r"\bdioramas\b", "architectural layout boards", out, flags=re.IGNORECASE)
    out = re.sub(r"\bdiorama\b", "architectural layout board", out, flags=re.IGNORECASE)
    out = re.sub(r"\bminiature\s+tea\s+set\b", "child-sized ceramic tea set", out, flags=re.IGNORECASE)
    out = re.sub(r"\bminiature\s+neighborhoods\b", "contrasting housing layout boards", out, flags=re.IGNORECASE)
    out = re.sub(r"\bminiature\s+stations\b", "compact rail platform markers", out, flags=re.IGNORECASE)
    out = re.sub(r"\bminiatures\b", "compact sculpted tokens", out, flags=re.IGNORECASE)
    out = re.sub(r"\bminiature\b", "compact", out, flags=re.IGNORECASE)
    out = _LOW_IMPACT_SCALE_FILLER_RE.sub("calibrated oak bench", out)
    out = re.sub(
        r"\bpastel-(?:mint|blue|pink|yellow|coral|peach|lilac|sage|green|cream|grey|gray)\b",
        "brushed-matte",
        out,
        flags=re.IGNORECASE,
    )
    out = re.sub(r"\bpastel\s+", "sunlit ", out, flags=re.IGNORECASE)
    out = re.sub(r"\bsunlit\s+sunlit\b", "sunlit", out, flags=re.IGNORECASE)
    # Also neutralize plaque/text triggers that could arise from raw lowpoly fields
    out = re.sub(r"\bwall\s+dial\b", "circular acoustic damper", out, flags=re.IGNORECASE)
    out = re.sub(r"\bconfetti\b", "paper slips", out, flags=re.IGNORECASE)
    out = re.sub(r"\b(?:zero|no|without)\s+face(?:\s+features?)?\b", "smooth featureless white heads", out, flags=re.IGNORECASE)
    return re.sub(r"\s{2,}", " ", out).strip()


def _sentence_has_literal_analogy_lock(sent: str) -> bool:
    return any(spec["spoken_re"].search(sent) for spec in LITERAL_ANALOGY_SPECS)


def _upgrade_lowpoly_candidate(
    raw_lp: dict[str, Any],
    *,
    allow_chrono: bool,
) -> dict[str, Any] | None:
    """Upgrades a non-analogy clip spec from sibling diorama_v7_lowpoly/visual_plan.json if clean."""
    g_norm = normalize_porcelain_v7_grammar(str(raw_lp.get("grammar") or "porcelain_fullbleed_world"))
    if g_norm == "porcelain_literal_analogy":
        return None
    c = copy.deepcopy(raw_lp)
    c.pop("scene", None)
    c.pop("beat_index", None)
    c.pop("beat_weight", None)
    c.pop("hold_sentences", None)
    c.pop("end_sentence_index", None)
    if "lowpoly" in str(c.get("reference_image") or "").lower():
        c.pop("reference_image", None)
    c["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
    c["grammar"] = g_norm
    if c.get("brain_mode") or g_norm == "porcelain_living_brain":
        c["brain_mode"] = normalize_porcelain_v7_brain_mode(str(c.get("brain_mode") or "sagittal_coronal_cutaway"))
        bs = _clean_porcelain_scene_text(str(c.get("brain_scene") or ""))
        bs = _sanitize_filler_tokens(bs, allow_chrono=allow_chrono).rstrip(".")
        if "cyan-blue" not in bs.lower() and "amber-gold" not in bs.lower():
            bs = (
                f"{bs}; enclosed clear cyan-blue cortical hubs, contained deep crimson-red focal zones, "
                "warm amber-gold fiber pathways, and smooth pearl-aqua fluid channels"
                if bs
                else "enclosed clear cyan-blue cortical hubs, contained deep crimson-red focal zones, warm amber-gold fiber pathways, and smooth pearl-aqua fluid channels"
            )
        c["brain_scene"] = bs
    for k in _TEXT_FIELDS:
        if isinstance(c.get(k), str) and c[k]:
            c[k] = _sanitize_filler_tokens(_clean_porcelain_scene_text(c[k]), allow_chrono=allow_chrono)
    if g_norm in ("porcelain_hands_closeup", "porcelain_pov_hands") and isinstance(c.get("attire_and_hands"), str):
        c["attire_and_hands"] = _strip_wide_camera_prefix_for_closeup(c["attire_and_hands"])
    c = _enrich_porcelain_cast_clip(c)
    return c


def _synthesize_multi_angle_clip(
    host: dict[str, Any],
    target_sent: int,
    sent_text: str,
    lowpoly_by_sent: dict[int, list[dict[str, Any]]],
    *,
    allow_chrono: bool,
) -> dict[str, Any]:
    """Builds a topic-grounded same-scene multi-angle coverage clip for `target_sent`."""
    anat_terms = find_anatomy_terms(sent_text)
    host_g = str(host.get("grammar") or "porcelain_fullbleed_world")
    act_no = int(host.get("act") or 1)
    loc_id = str(host.get("location_id") or "primary_studio_room").strip()

    # 1. If spoken sentence names a brain region OR host is a 3D brain hold, use complementary 3D brain angle
    if anat_terms or host_g == "porcelain_living_brain" or host.get("brain_mode"):
        for lp in lowpoly_by_sent.get(target_sent, []):
            cand = _upgrade_lowpoly_candidate(lp, allow_chrono=allow_chrono)
            if cand and str(cand.get("grammar")) == "porcelain_living_brain":
                cand["sentence_index"] = target_sent
                cand["end_sentence_index"] = target_sent
                cand["act"] = act_no
                return cand

        host_bm = normalize_porcelain_v7_brain_mode(str(host.get("brain_mode") or "cortical_vascular_whole"))
        comp_bm = (
            "sagittal_coronal_cutaway"
            if host_bm in ("cortical_vascular_whole", "frosted_glass_subcortical_xray")
            else "bounded_micro_channel"
        )
        b_reg = str(anat_terms[0] if anat_terms else (host.get("brain_region") or "prefrontal cortex"))
        comp_cam = "gentle_push_in" if str(host.get("camera") or "") == "locked_tripod" else "locked_tripod"
        out_b: dict[str, Any] = {
            "sentence_index": target_sent,
            "end_sentence_index": target_sent,
            "act": act_no,
            "location_id": "bright_brain_studio",
            "grammar": "porcelain_living_brain",
            "brain_mode": comp_bm,
            "brain_region": b_reg,
            "camera": comp_cam,
            "brain_scene": (
                f"inside the precision 3D anatomical cutaway of the {b_reg}, enclosed clear cyan-blue relay hubs "
                "connect with warm amber-gold axon tracts while contained deep crimson-red activity zones shift cleanly "
                "alongside smooth luminous pearl-aqua perivascular channels"
            ),
            "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        }
        if host.get("anatomy_label") and not anat_terms:
            out_b["anatomy_label"] = host["anatomy_label"]
        return out_b

    # 2. Check sibling lowpoly draft for a topic-specific non-analogy room/hands/cutaway clip on `target_sent`
    for lp in lowpoly_by_sent.get(target_sent, []):
        cand = _upgrade_lowpoly_candidate(lp, allow_chrono=allow_chrono)
        if cand is not None:
            cand["sentence_index"] = target_sent
            cand["end_sentence_index"] = target_sent
            cand["act"] = act_no
            if not cand.get("location_id"):
                cand["location_id"] = loc_id
            return cand

    # 3. Synthesize complementary same-scene multi-angle coverage in the exact same room & scene_state
    host_cam = str(host.get("camera") or "locked_tripod")
    st_copy = copy.deepcopy(host.get("scene_state")) if isinstance(host.get("scene_state"), dict) else None
    if st_copy is not None:
        # Second half of a split hold starts in the post-entrance/post-exit steady state of the first half
        end_cast = list(st_copy.get("present_cast_end") or st_copy.get("present_cast_start") or ["subject"])
        st_copy["present_cast_start"] = end_cast
        st_copy["entering_cast"] = []
        st_copy["exiting_cast"] = []
        st_copy["present_cast_end"] = end_cast

    if host_g == "porcelain_fullbleed_world":
        comp_cam = "pan_right" if host_cam == "locked_tripod" else "locked_tripod"
        env_hint = _strip_wide_camera_prefix_for_closeup(
            _sanitize_filler_tokens(
                str(host.get("environment") or "the sunlit laboratory workbench"),
                allow_chrono=allow_chrono,
            )
        )
        new_c: dict[str, Any] = {
            "sentence_index": target_sent,
            "end_sentence_index": target_sent,
            "act": act_no,
            "location_id": loc_id,
            "grammar": "porcelain_hands_closeup",
            "camera": comp_cam,
            "attire_and_hands": (
                f"tailored woven blazer cuffs and smooth articulated matte-white porcelain hands inside {env_hint}"
            ),
            "prop_action": (
                "both smooth matte-white porcelain hands reach forward across the bench, align the primary test instrument, "
                "and press the brass control latch cleanly into place"
            ),
            "consequence": "the calibrated indicator shifts smoothly into steady alignment under bright studio daylight",
            "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        }
    else:
        comp_cam = "locked_tripod" if host_cam != "locked_tripod" else "pan_left"
        new_c = {
            "sentence_index": target_sent,
            "end_sentence_index": target_sent,
            "act": act_no,
            "location_id": loc_id,
            "grammar": "porcelain_fullbleed_world",
            "camera": comp_cam,
            "environment": (
                f"a reverse three-quarter wide angle inside the bright high-key {loc_id.replace('_', ' ')} "
                "with warm birch workbenches, brushed-metal research apparatus, and tall daylight windows"
            ),
            "action": (
                "viewed from a clean three-quarter angle, a clothed matte-white porcelain figure with a smooth featureless "
                "white oval head in tailored linen sleeves leans forward, adjusts the tabletop apparatus, and slides the marker cleanly"
            ),
            "style_profile": PORCELAIN_V7_STYLE_PROFILE,
        }
    if st_copy is not None:
        new_c["scene_state"] = st_copy
    return _enrich_porcelain_cast_clip(new_c)


def _rebalance_camera_ratios(clips: list[dict[str, Any]]) -> bool:
    """Ensures camera moves across clips satisfy R63/R66 tripod >= 35%, zoom <= 30%, pan_left >= 1, pan_right >= 1."""
    changed = False
    n_tot = max(1, len(clips))
    for c in clips:
        cm = str(c.get("camera") or c.get("camera_move") or "").strip()
        if cm not in DIORAMA_V7_CAMERA_MOVES:
            c["camera"] = "tilt_up" if str(c.get("cut_role") or "").lower() == "outro" else "locked_tripod"
            changed = True

    def _counts() -> dict[str, int]:
        d = {m: 0 for m in DIORAMA_V7_CAMERA_MOVES}
        for c in clips:
            cm = str(c.get("camera") or c.get("camera_move") or "locked_tripod")
            if cm in d:
                d[cm] += 1
        return d

    cnts = _counts()
    # 1. Cap zoom ratio <= 0.27 (comfortably under 0.30)
    max_zoom = int(n_tot * (DIORAMA_V7_ZOOM_CAMERA_MAX_RATIO - 0.03))
    for c in reversed(clips):
        if cnts["gentle_push_in"] + cnts["clean_pullback_reveal"] <= max_zoom:
            break
        if str(c.get("cut_role") or "").lower() == "outro":
            continue
        cm = str(c.get("camera") or c.get("camera_move") or "")
        if cm in ("gentle_push_in", "clean_pullback_reveal"):
            c["camera"] = "locked_tripod"
            c.pop("camera_move", None)
            cnts[cm] -= 1
            cnts["locked_tripod"] += 1
            changed = True

    # 2. Ensure pan_left >= 2 and pan_right >= 2
    for needed_pan in ("pan_left", "pan_right"):
        for c in clips:
            if cnts[needed_pan] >= 2:
                break
            role = str(c.get("cut_role") or "").lower()
            cm = str(c.get("camera") or c.get("camera_move") or "")
            if role in ("outro", "split_right", "split_bottom"):
                continue
            if cm in ("tilt_down", "tilt_up") or (cm == "locked_tripod" and cnts["locked_tripod"] > int(n_tot * 0.44)):
                c["camera"] = needed_pan
                c.pop("camera_move", None)
                cnts[cm] -= 1
                cnts[needed_pan] += 1
                changed = True

    # 3. Ensure locked_tripod >= ceil(0.37 * n_tot)
    min_locked = int(n_tot * (DIORAMA_V7_LOCKED_CAMERA_MIN_RATIO + 0.03)) + 1
    for c in clips:
        if cnts["locked_tripod"] >= min_locked:
            break
        role = str(c.get("cut_role") or "").lower()
        cm = str(c.get("camera") or c.get("camera_move") or "")
        if role == "outro" or cm == "locked_tripod":
            continue
        if cm in ("pan_left", "pan_right") and cnts[cm] <= 2:
            continue
        c["camera"] = "locked_tripod"
        c.pop("camera_move", None)
        cnts[cm] -= 1
        cnts["locked_tripod"] += 1
        changed = True

    return changed


def _expand_holds_to_sweet_spot(
    plan: dict[str, Any],
    clips: list[dict[str, Any]],
    narrations: list[str],
    lowpoly_by_sent: dict[int, list[dict[str, Any]]],
    *,
    allow_chrono: bool,
) -> tuple[list[dict[str, Any]], bool]:
    """Expands compact 34-36 clip plans to ~48 clips (46-48 cuts) with zero 3-sentence holds."""
    n_sents = len(narrations)
    target_clips = min(
        PORCELAIN_V7_TARGET_CLIP_MAX - 2,
        max(PORCELAIN_V7_TARGET_CLIP_MIN + 2, DIORAMA_CLIP_COUNT_DEFAULT, n_sents - 3),
    )
    target_clips = max(PORCELAIN_V7_TARGET_CLIP_MIN, min(PORCELAIN_V7_TARGET_CLIP_MAX - 2, target_clips))

    # Check if already balanced AND split_comparisons indices match actual split_right/split_bottom clips
    has_overhold = any(
        str(c.get("cut_role") or "").lower() not in ("outro", "split_right", "split_bottom")
        and isinstance(c.get("sentence_index"), int)
        and (max(int(c["sentence_index"]), int(c.get("end_sentence_index") or c["sentence_index"])) - int(c["sentence_index"]) + 1)
        > PORCELAIN_V7_MAX_HOLD_SENTENCES
        for c in clips
    )
    split_roles_1based = {
        idx_s
        for idx_s, c_s in enumerate(clips, start=1)
        if isinstance(c_s, dict) and str(c_s.get("cut_role") or "").strip().lower() in ("split_right", "split_bottom")
    }
    has_stale_split_idx = any(
        isinstance(sc, dict)
        and int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0) not in split_roles_1based
        for sc in (plan.get("split_comparisons") or [])
    )
    if (
        PORCELAIN_V7_TARGET_CLIP_MIN <= len(clips) <= PORCELAIN_V7_TARGET_CLIP_MAX
        and not has_overhold
        and not has_stale_split_idx
    ):
        return clips, False

    split_sents = {
        int(sc.get("sentence_index") or 0)
        for sc in (plan.get("split_comparisons") or [])
        if isinstance(sc, dict) and int(sc.get("sentence_index") or 0) >= 1
    }

    work = [copy.deepcopy(c) for c in clips]
    changed = False

    def _hold_bounds(c_obj: dict[str, Any]) -> tuple[int, int]:
        s0 = int(c_obj.get("sentence_index") or 0)
        h_exp = int(c_obj.get("hold_sentences") or 1)
        s1 = max(s0, int(c_obj.get("end_sentence_index") or (s0 + h_exp - 1)))
        return s0, s1

    def _split_one_at(idx_pos: int) -> None:
        nonlocal changed
        host = work[idx_pos]
        s0, s1 = _hold_bounds(host)
        # Peel off final sentence `s1` into its own multi-angle coverage clip right after `host`
        new_end = s1 - 1
        # However, if `s1` is a split_hstack sentence or literal-analogy lock on host, peel `s0` instead if needed
        peel_first = (
            s1 in split_sents
            or (
                str(host.get("grammar") or "") == "porcelain_literal_analogy"
                and _sentence_has_literal_analogy_lock(narrations[s1 - 1] if 1 <= s1 <= n_sents else "")
                and not _sentence_has_literal_analogy_lock(narrations[s0 - 1] if 1 <= s0 <= n_sents else "")
            )
        )
        if peel_first:
            # New clip takes `s0`, host keeps `s0+1..s1`
            host["sentence_index"] = s0 + 1
            host["end_sentence_index"] = s1
            host.pop("hold_sentences", None)
            if s0 + 1 == s1:
                host.pop("end_sentence_index", None)
            new_clip = _synthesize_multi_angle_clip(
                host,
                s0,
                narrations[s0 - 1] if 1 <= s0 <= n_sents else "",
                lowpoly_by_sent,
                allow_chrono=allow_chrono,
            )
            work.insert(idx_pos, new_clip)
        else:
            host["sentence_index"] = s0
            if new_end > s0:
                host["end_sentence_index"] = new_end
            else:
                host.pop("end_sentence_index", None)
            host.pop("hold_sentences", None)
            # If host was entrance/exit, keep entrance on host (`s0..new_end`) and steady post-state on `s1`
            new_clip = _synthesize_multi_angle_clip(
                host,
                s1,
                narrations[s1 - 1] if 1 <= s1 <= n_sents else "",
                lowpoly_by_sent,
                allow_chrono=allow_chrono,
            )
            work.insert(idx_pos + 1, new_clip)
        changed = True

    # Pass 1: Eliminate 100% of 3+ sentence holds
    while True:
        over_idx = -1
        for idx_c, c_item in enumerate(work):
            if str(c_item.get("cut_role") or "").lower() in ("outro", "split_right", "split_bottom"):
                continue
            if not isinstance(c_item.get("sentence_index"), int):
                continue
            s0, s1 = _hold_bounds(c_item)
            if s1 - s0 + 1 > PORCELAIN_V7_MAX_HOLD_SENTENCES:
                over_idx = idx_c
                break
        if over_idx < 0:
            break
        _split_one_at(over_idx)

    # Pass 2: Split longest 2-sentence holds (by spoken word count) until len(work) == target_clips
    while len(work) < target_clips:
        best_idx = -1
        best_score = -1
        for idx_c, c_item in enumerate(work):
            if str(c_item.get("cut_role") or "").lower() in ("outro", "split_right", "split_bottom"):
                continue
            if not isinstance(c_item.get("sentence_index"), int):
                continue
            s0, s1 = _hold_bounds(c_item)
            if s1 <= s0:
                continue
            w_span = sum(count_words(narrations[s_k - 1]) for s_k in range(s0, s1 + 1) if 1 <= s_k <= n_sents)
            # Slightly prioritize splitting brain holds >4s and heavy multi-clause holds
            bonus = 4 if str(c_item.get("grammar") or "") == "porcelain_living_brain" else 0
            if w_span + bonus > best_score:
                best_score = w_span + bonus
                best_idx = idx_c
        if best_idx < 0:
            break
        _split_one_at(best_idx)

    # Pass 3: Merge adjacent compatible 1-sentence clips when len(work) > PORCELAIN_V7_TARGET_CLIP_MAX - 2
    max_sweet_clips = PORCELAIN_V7_TARGET_CLIP_MAX - 2
    while len(work) > max_sweet_clips:
        merge_idx = -1
        best_merge_words = 10**9
        for idx_c in range(len(work) - 1):
            c_cur = work[idx_c]
            c_nxt = work[idx_c + 1]
            r_cur = str(c_cur.get("cut_role") or "").lower()
            r_nxt = str(c_nxt.get("cut_role") or "").lower()
            if r_cur in ("outro", "split_left", "split_right", "split_top", "split_bottom"):
                continue
            if r_nxt in ("outro", "split_left", "split_right", "split_top", "split_bottom"):
                continue
            if not isinstance(c_cur.get("sentence_index"), int) or not isinstance(c_nxt.get("sentence_index"), int):
                continue
            s0, s1 = _hold_bounds(c_cur)
            n0, n1 = _hold_bounds(c_nxt)
            if s0 < 4 or s1 != s0 or n0 != s0 + 1 or n1 != n0:
                continue
            if s0 in split_sents or n0 in split_sents:
                continue
            g_cur = str(c_cur.get("grammar") or "")
            g_nxt = str(c_nxt.get("grammar") or "")
            if g_cur == "porcelain_literal_analogy" or g_nxt == "porcelain_literal_analogy":
                continue
            cur_brain = _is_brain_or_outro(c_cur)
            nxt_brain = _is_brain_or_outro(c_nxt)
            if cur_brain != nxt_brain:
                continue
            if not cur_brain:
                # Avoid merging if second sentence names anatomy that requires a 3D brain clip (DQ3)
                if 1 <= n0 <= n_sents and find_anatomy_terms(narrations[n0 - 1]):
                    continue
                loc_cur = str((c_cur.get("scene_state") or {}).get("location_id") or c_cur.get("location_id") or "primary_room")
                loc_nxt = str((c_nxt.get("scene_state") or {}).get("location_id") or c_nxt.get("location_id") or "primary_room")
                if loc_cur != loc_nxt:
                    continue
            w_pair = sum(count_words(narrations[k - 1]) for k in (s0, n0) if 1 <= k <= n_sents)
            if w_pair < best_merge_words:
                best_merge_words = w_pair
                merge_idx = idx_c
        if merge_idx < 0:
            break
        c_keep = work[merge_idx]
        c_drop = work.pop(merge_idx + 1)
        c_keep["end_sentence_index"] = int(c_drop["sentence_index"])
        c_keep.pop("hold_sentences", None)
        changed = True

    # Re-index clip_number 1..N and re-bind split_comparisons left_clip_index / right_clip_index
    for i_new, c_item in enumerate(work, start=1):
        if c_item.get("clip_number") != i_new:
            c_item["clip_number"] = i_new
            changed = True

    if isinstance(plan.get("split_comparisons"), list):
        for sc in plan["split_comparisons"]:
            if not isinstance(sc, dict):
                continue
            s_idx = int(sc.get("sentence_index") or 0)
            if s_idx < 1:
                continue
            matched_sec = False
            for i_new, c_item in enumerate(work, start=1):
                role = str(c_item.get("cut_role") or "").strip().lower()
                s0 = int(c_item.get("sentence_index") or 0)
                s1 = max(s0, int(c_item.get("end_sentence_index") or s0))
                if role in ("split_right", "split_bottom") and s0 == s_idx:
                    if "bottom_clip_index" in sc and "right_clip_index" not in sc:
                        if sc.get("bottom_clip_index") != i_new:
                            sc["bottom_clip_index"] = i_new
                            changed = True
                    else:
                        if sc.get("right_clip_index") != i_new:
                            sc["right_clip_index"] = i_new
                            changed = True
                    matched_sec = True
                elif role not in ("outro", "split_right", "split_bottom") and s0 <= s_idx <= s1:
                    if "top_clip_index" in sc and "left_clip_index" not in sc:
                        if sc.get("top_clip_index") != i_new:
                            sc["top_clip_index"] = i_new
                            changed = True
                    else:
                        if sc.get("left_clip_index") != i_new:
                            sc["left_clip_index"] = i_new
                            changed = True
            if not matched_sec:
                for i_new, c_item in enumerate(work, start=1):
                    role = str(c_item.get("cut_role") or "").strip().lower()
                    if role in ("split_right", "split_bottom"):
                        if c_item.get("sentence_index") != s_idx:
                            c_item["sentence_index"] = s_idx
                            changed = True
                        if "bottom_clip_index" in sc and "right_clip_index" not in sc:
                            if sc.get("bottom_clip_index") != i_new:
                                sc["bottom_clip_index"] = i_new
                                changed = True
                        else:
                            if sc.get("right_clip_index") != i_new:
                                sc["right_clip_index"] = i_new
                                changed = True
                        break

    return work, changed


_CHRONOMETER_APPARATUS_SLUGS: frozenset[str] = frozenset(
    {
        "schachter_external_eating_cues",  # Science 1968 (10.1126/science.161.3843.751): rigged 2x wall clock & confiscated wristwatches
    }
)


def _sync_unproduced_project_dir(draft_dir: Path, project_id: str, *, write: bool) -> tuple[bool, list[str]]:
    """Syncs rebalanced porcelain draft into `projects/<project_id>` if and only if the project is unproduced."""
    if not project_id:
        return False, []
    proj_dir = Path(config.PROJECTS_DIR) / project_id
    if not proj_dir.exists():
        return False, []
    if (proj_dir / "06_publish" / "upload_receipt.json").exists():
        return False, []
    if (proj_dir / "05_assembly" / "final_shorts_1080x1920.mp4").exists():
        return False, []
    native_dir = proj_dir / "03_visuals" / "flow_native_clips"
    if native_dir.exists() and any(native_dir.glob("clip_*.mp4")):
        return False, []

    src_vp = draft_dir / "visual_plan.json"
    dst_vis = proj_dir / "03_visuals"
    dst_vp = dst_vis / "visual_plan.json"
    src_prompts = draft_dir / "flow_all_in_one_prompts.json"
    dst_prompts = dst_vis / "flow_all_in_one_prompts.json"
    src_specs = draft_dir / "reference_image_specs.json"
    dst_specs = dst_vis / "reference_image_specs.json"
    src_script = draft_dir / "script.json"
    dst_script = proj_dir / "02_script" / "script.json"

    sync_issues: list[str] = []
    src_vp_bytes = src_vp.read_bytes()
    needs_vp = (not dst_vp.exists()) or (dst_vp.read_bytes() != src_vp_bytes)
    needs_prompts = src_prompts.exists() and ((not dst_prompts.exists()) or (dst_prompts.read_bytes() != src_prompts.read_bytes()))
    needs_specs = src_specs.exists() and ((not dst_specs.exists()) or (dst_specs.read_bytes() != src_specs.read_bytes()))
    needs_script = src_script.exists() and ((not dst_script.exists()) or (dst_script.read_bytes() != src_script.read_bytes()))
    if not (needs_vp or needs_prompts or needs_specs or needs_script):
        return False, []

    if not write:
        sync_issues.append(f"unproduced project {project_id} is out of sync with {draft_dir.name}/visual_plan.json")
        return False, sync_issues

    import shutil

    dst_vis.mkdir(parents=True, exist_ok=True)
    shutil.copy2(src_vp, dst_vp)
    if src_prompts.exists():
        shutil.copy2(src_prompts, dst_prompts)
    if src_specs.exists():
        shutil.copy2(src_specs, dst_specs)
    if src_script.exists():
        dst_script.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src_script, dst_script)
    return True, []


def normalize_draft_dir(pdir: Path, *, write: bool = True) -> dict[str, Any]:
    vp_path = pdir / "visual_plan.json"
    plan = json.loads(vp_path.read_text(encoding="utf-8"))
    _, narrations, _ = cli._load_gate_inputs(pdir)
    clips: list[dict[str, Any]] = list(plan.get("clips") or [])
    slug_guess = str(plan.get("dossier") or plan.get("dossier_slug") or pdir.parent.name).strip()
    if slug_guess in _CHRONOMETER_APPARATUS_SLUGS and not plan.get("allow_chronometer_apparatus"):
        plan["allow_chronometer_apparatus"] = True
        changed = True
    else:
        changed = False
    allow_chrono = bool(plan.get("allow_chronometer_apparatus"))

    if not plan.get("require_scene_state_ledger"):
        plan["require_scene_state_ledger"] = True
        changed = True
    if isinstance(plan.get("target_clip_count"), int) and plan.get("target_clip_count") != DIORAMA_CLIP_COUNT_DEFAULT:
        plan["target_clip_count"] = DIORAMA_CLIP_COUNT_DEFAULT
        changed = True

    for pk in ("title", "topic", "real_environment", "default_location_id"):
        if isinstance(plan.get(pk), str) and plan[pk]:
            cleaned_pk = _sanitize_filler_tokens(plan[pk], allow_chrono=allow_chrono)
            if cleaned_pk != plan[pk]:
                plan[pk] = cleaned_pk
                changed = True
    if isinstance(plan.get("environment_props"), list):
        new_props = [
            _sanitize_filler_tokens(str(pr), allow_chrono=allow_chrono) if isinstance(pr, str) else pr
            for pr in plan["environment_props"]
        ]
        if new_props != plan["environment_props"]:
            plan["environment_props"] = new_props
            changed = True

    # Pre-normalize classic migrated drafts: trailing outro role, <=2 literal analogy cap, and R65 thumbnail block
    default_loc = str(plan.get("default_location_id") or "primary_studio_room").strip() or "primary_studio_room"
    default_env = _sanitize_filler_tokens(
        str(plan.get("real_environment") or "a bright high-key architectural research room with warm birch benches"),
        allow_chrono=allow_chrono,
    )
    prop_list = [str(x).strip() for x in (plan.get("environment_props") or []) if str(x).strip()]
    primary_prop = _sanitize_filler_tokens(
        prop_list[0] if prop_list else "the calibrated tabletop test apparatus",
        allow_chrono=allow_chrono,
    )
    if clips and narrations:
        last_c = clips[-1]
        if isinstance(last_c, dict):
            s_last = last_c.get("sentence_index")
            r_last = str(last_c.get("cut_role") or "").strip().lower()
            if r_last == "outro" or s_last is None or (isinstance(s_last, int) and s_last > len(narrations)):
                if last_c.get("cut_role") != "outro":
                    last_c["cut_role"] = "outro"
                    changed = True
                if last_c.get("sentence_index") != len(narrations):
                    last_c["sentence_index"] = len(narrations)
                    changed = True
                last_c.pop("end_sentence_index", None)
                last_c.pop("scene_state", None)
                last_c.pop("scene", None)
                last_c["act"] = 6
                last_c["location_id"] = str(last_c.get("location_id") or default_loc)
                last_c["grammar"] = "porcelain_fullbleed_world"
                last_c["camera"] = "tilt_up"
                last_c["style_profile"] = PORCELAIN_V7_STYLE_PROFILE
                if not str(last_c.get("environment") or "").strip():
                    last_c["environment"] = (
                        f"a serene wide architectural view across {default_env} with tall daylight windows opening to pale sky"
                    )
                    changed = True
                if not str(last_c.get("action") or "").strip():
                    last_c["action"] = (
                        f"viewed strictly from behind, a clothed matte-white porcelain researcher stands quietly beside {primary_prop} as the camera tilts gently upward"
                    )
                    changed = True

    analogy_indices: list[tuple[int, int]] = []
    for idx_a, c_a in enumerate(clips):
        if not isinstance(c_a, dict):
            continue
        if str(c_a.get("cut_role") or "").strip().lower() in ("outro", "split_right", "split_bottom"):
            continue
        if str(c_a.get("grammar") or "") == "porcelain_literal_analogy":
            s_a0 = int(c_a.get("sentence_index") or 0)
            s_a1 = max(s_a0, int(c_a.get("end_sentence_index") or s_a0))
            has_lock = any(
                _sentence_has_literal_analogy_lock(narrations[sk - 1])
                for sk in range(s_a0, s_a1 + 1)
                if 1 <= sk <= len(narrations)
            )
            analogy_indices.append((0 if has_lock else 1, idx_a))
    if len(analogy_indices) > PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS:
        analogy_indices.sort()
        keep_analogy = {idx_a for _, idx_a in analogy_indices[:PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS]}
        for _, idx_a in analogy_indices[PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS:]:
            c_conv = clips[idx_a]
            s_a0 = int(c_conv.get("sentence_index") or 1)
            s_a1 = max(s_a0, int(c_conv.get("end_sentence_index") or s_a0))
            act_a = int(c_conv.get("act") or min(6, max(1, (s_a0 - 1) // 8 + 1)))
            prop_i = _sanitize_filler_tokens(
                prop_list[idx_a % len(prop_list)] if prop_list else primary_prop,
                allow_chrono=allow_chrono,
            )
            prop_short = " ".join(prop_i.split()[:8]).rstrip(",.;:")
            env_short = " ".join(_strip_wide_camera_prefix_for_closeup(default_env).split()[:12]).rstrip(",.;:")
            c_conv.clear()
            c_conv.update(
                {
                    "clip_number": idx_a + 1,
                    "sentence_index": s_a0,
                    **({"end_sentence_index": s_a1} if s_a1 > s_a0 else {}),
                    "act": act_a,
                    "location_id": default_loc,
                    "grammar": "porcelain_hands_closeup",
                    "camera": "locked_tripod",
                    "attire_and_hands": (
                        f"tailored woven blazer cuffs and smooth matte-white porcelain hands beside {prop_short} inside {env_short}"
                    ),
                    "prop_action": (
                        f"both smooth matte-white porcelain hands reach forward, align {prop_short}, and set the marker cleanly"
                    ),
                    "consequence": "the physical apparatus settles into crisp alignment under bright daylight",
                    "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                }
            )
            changed = True

    thumb_blk = plan.get("thumbnail")
    if not isinstance(thumb_blk, dict) or not str(thumb_blk.get("hook_text") or "").strip():
        hook_cand = ""
        for callout_key in ("chapter_headlines", "top_callouts"):
            for item_co in (plan.get(callout_key) or []):
                if isinstance(item_co, dict):
                    txt_co = re.sub(r"[^A-Z0-9 ?!'-]", "", str(item_co.get("text") or "").upper()).strip()
                    if 4 <= len(txt_co) <= 18 and int(item_co.get("sentence_index") or 0) in (2, 3, 1):
                        hook_cand = txt_co
                        if int(item_co.get("sentence_index") or 0) == 3:
                            break
            if hook_cand:
                break
        if not hook_cand:
            words_slug = [w.upper() for w in slug_guess.split("_") if w and len(w) >= 3][:2]
            hook_cand = " ".join(words_slug)[:18].strip() or "BRAIN MYSTERY"
        plan["thumbnail"] = {
            "hook_text": hook_cand,
            "cover_sentence_index": 3,
            "cover_brief": f"centered {primary_prop} inside {default_env}",
        }
        changed = True
    if isinstance(plan.get("thumbnail"), dict):
        cov_s = int(plan["thumbnail"].get("cover_sentence_index") or 3)
        cov_txt = str(plan["thumbnail"].get("hook_text") or "").strip()
        if cov_txt:
            for callout_key in ("chapter_headlines", "top_callouts"):
                arr = [x for x in (plan.get(callout_key) or []) if isinstance(x, dict)]
                if not any(int(x.get("sentence_index") or 0) == cov_s and str(x.get("text") or "").strip().upper() == cov_txt.upper() for x in arr):
                    arr = [x for x in arr if int(x.get("sentence_index") or 0) != cov_s]
                    arr.append({"sentence_index": cov_s, "text": cov_txt})
                    arr.sort(key=lambda d: int(d.get("sentence_index") or 0))
                    plan[callout_key] = arr
                    changed = True

    # Load sibling lowpoly visual_plan as topic-specific shot bank if expansion is needed
    lowpoly_by_sent: dict[int, list[dict[str, Any]]] = {}
    lp_vp_path = pdir.parent / "diorama_v7_lowpoly" / "visual_plan.json"
    if lp_vp_path.exists():
        try:
            lp_doc = json.loads(lp_vp_path.read_text(encoding="utf-8"))
            for lpc in lp_doc.get("clips") or []:
                if not isinstance(lpc, dict):
                    continue
                if str(lpc.get("cut_role") or "").lower() in ("outro", "split_right", "split_bottom"):
                    continue
                s_lp = lpc.get("sentence_index")
                if isinstance(s_lp, int) and s_lp >= 1:
                    lowpoly_by_sent.setdefault(s_lp, []).append(lpc)
        except Exception:
            lowpoly_by_sent = {}

    clips, exp_changed = _expand_holds_to_sweet_spot(
        plan,
        clips,
        narrations,
        lowpoly_by_sent,
        allow_chrono=allow_chrono,
    )
    if exp_changed:
        plan["clips"] = clips
        changed = True

    loc_state: dict[str, dict[str, Any]] = {}
    for idx, c in enumerate(clips, start=1):
        if not isinstance(c, dict):
            continue
        if c.get("clip_number") != idx:
            c["clip_number"] = idx
            changed = True
        if str(c.get("location_id") or "") == "pastel_analogy_court":
            c["location_id"] = "sunlit_studio_bench"
            changed = True
        if isinstance(c.get("scene_state"), dict) and str(c["scene_state"].get("location_id") or "") == "pastel_analogy_court":
            c["scene_state"]["location_id"] = "sunlit_studio_bench"
            changed = True
        for k in _TEXT_FIELDS:
            if isinstance(c.get(k), str) and c[k]:
                cleaned = _sanitize_filler_tokens(c[k], allow_chrono=allow_chrono)
                if cleaned != c[k]:
                    c[k] = cleaned
                    changed = True
        if str(c.get("grammar") or "") in ("porcelain_hands_closeup", "porcelain_pov_hands") and isinstance(
            c.get("attire_and_hands"), str
        ):
            stripped_ah = _strip_wide_camera_prefix_for_closeup(c["attire_and_hands"])
            if len(stripped_ah.split()) > 22:
                stripped_ah = " ".join(stripped_ah.split()[:20]).rstrip(",.;:")
            if stripped_ah != c["attire_and_hands"]:
                c["attire_and_hands"] = stripped_ah
                changed = True
            if isinstance(c.get("prop_action"), str) and len(c["prop_action"].split()) > 22:
                c["prop_action"] = " ".join(c["prop_action"].split()[:20]).rstrip(",.;:")
                changed = True

        # Ensure DQ3 anatomy lock compliance on primary clips
        c_role = str(c.get("cut_role") or "").strip().lower()
        g_name = str(c.get("grammar") or "")
        if c_role not in ("outro", "split_right", "split_bottom") and g_name != "porcelain_living_brain":
            s0 = int(c.get("sentence_index") or 0)
            s1 = max(s0, int(c.get("end_sentence_index") or s0))
            anat_hit: list[str] = []
            for s_k in range(s0, s1 + 1):
                if 1 <= s_k <= len(narrations):
                    anat_hit.extend(find_anatomy_terms(narrations[s_k - 1]))
            if anat_hit:
                b_reg = anat_hit[0]
                c.clear()
                c.update(
                    {
                        "clip_number": idx,
                        "sentence_index": s0,
                        **({"end_sentence_index": s1} if s1 > s0 else {}),
                        "act": min(6, max(1, (s0 - 1) // 8 + 1)),
                        "location_id": "bright_brain_studio",
                        "grammar": "porcelain_living_brain",
                        "brain_mode": "sagittal_coronal_cutaway" if idx % 2 == 0 else "cortical_vascular_whole",
                        "brain_region": b_reg,
                        "camera": "locked_tripod",
                        "brain_scene": (
                            f"inside the precision 3D anatomical model of the {b_reg}, enclosed clear cyan-blue cortical "
                            "hubs connect with warm amber-gold fiber pathways alongside contained deep crimson-red focal zones "
                            "and smooth luminous pearl-aqua perivascular fluid channels"
                        ),
                        "style_profile": PORCELAIN_V7_STYLE_PROFILE,
                    }
                )
                g_name = "porcelain_living_brain"
                changed = True

        if _is_brain_or_outro(c) or g_name == "porcelain_literal_analogy":
            continue
        if c_role in ("split_right", "split_bottom"):
            enriched_sp = _enrich_porcelain_cast_clip(c)
            if enriched_sp != c:
                c.clear()
                c.update(enriched_sp)
                changed = True
            sp_loc = str((c.get("scene_state") or {}).get("location_id") or c.get("location_id") or default_loc).strip()
            c["location_id"] = sp_loc
            if not isinstance(c.get("scene_state"), dict):
                c["scene_state"] = {
                    "location_id": sp_loc,
                    "present_cast_start": ["researcher"],
                    "entering_cast": [],
                    "exiting_cast": [],
                    "present_cast_end": ["researcher"],
                }
                changed = True
            continue

        enriched = _enrich_porcelain_cast_clip(c)
        if enriched != c:
            c.clear()
            c.update(enriched)
            changed = True

        loc_id = str((c.get("scene_state") or {}).get("location_id") or c.get("location_id") or "primary_room").strip()
        if c.get("location_id") != loc_id:
            c["location_id"] = loc_id
            changed = True
        st = dict(c.get("scene_state") or {})
        st["location_id"] = loc_id
        p_start = [str(x).strip() for x in (st.get("present_cast_start") or ["subject"]) if str(x).strip()]
        entering = [str(x).strip() for x in (st.get("entering_cast") or []) if str(x).strip()]
        exiting = [str(x).strip() for x in (st.get("exiting_cast") or []) if str(x).strip()]
        entering = [x for x in entering if x not in p_start]
        exiting = [x for x in exiting if x in (set(p_start) | set(entering))]
        p_end = sorted((set(p_start) | set(entering)) - set(exiting))

        prev = loc_state.get(loc_id)
        if prev is not None and not (st.get("scene_reset") or st.get("protocol_phase_jump")):
            if (set(p_start) & prev["departed"]) or (set(entering) & prev["present_end"]):
                st["protocol_phase_jump"] = True
                changed = True

        st["present_cast_start"] = p_start
        st["entering_cast"] = entering
        st["exiting_cast"] = exiting
        st["present_cast_end"] = p_end
        if c.get("scene_state") != st:
            c["scene_state"] = st
            changed = True

        departed = (
            set(exiting)
            if (prev is None or st.get("scene_reset"))
            else ((prev["departed"] - set(entering)) | set(exiting))
        )
        loc_state[loc_id] = {"present_end": set(p_end), "departed": departed}

    if _rebalance_camera_ratios(clips):
        changed = True

    plan["clips"] = clips
    from pipeline.porcelain_anchor_pack import populate_porcelain_reference_contract
    from pipeline.reference_image_qa import build_reference_image_specs

    before_contract = json.dumps(plan, sort_keys=True, ensure_ascii=False)
    populate_porcelain_reference_contract(plan, dossier_dir=pdir.parent)
    if json.dumps(plan, sort_keys=True, ensure_ascii=False) != before_contract:
        changed = True
    clips = list(plan.get("clips") or [])

    if changed and write:
        vp_path.write_text(json.dumps(plan, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    plan_chk = plan if not write else json.loads(vp_path.read_text(encoding="utf-8"))
    _, narrations_chk, script_doc = cli._load_gate_inputs(pdir)
    built = build_flow_prompts(plan_chk, narrations_chk)
    prompts_json_path = pdir / "flow_all_in_one_prompts.json"
    specs_json_path = pdir / "reference_image_specs.json"
    if write and (changed or not prompts_json_path.exists()):
        from pipeline.flow_prompt_builder import write_flow_prompts_json

        write_flow_prompts_json(pdir, built)
    if write and (changed or not specs_json_path.exists()):
        specs_payload = build_reference_image_specs(plan_chk, narrations_chk)
        specs_json_path.write_text(
            json.dumps(specs_payload, indent=2, ensure_ascii=False) + "\n",
            encoding="utf-8",
        )
    stale_nested = pdir / "03_visuals"
    if write and stale_nested.is_dir():
        import shutil

        shutil.rmtree(stale_nested, ignore_errors=True)
    issues = list(validate_production_diorama_v6(plan_chk, narrations_chk, built, script_doc=script_doc))
    issues.extend(verify_pre_flow_contract(plan_chk, narrations_chk, built, script_doc=script_doc))
    raw_title = str(script_doc.get("title") or plan_chk.get("title") or "").strip()
    if raw_title:
        issues.extend(validate_diorama_paradox_title(raw_title))

    lit_cnt = sum(1 for c in clips if str(c.get("grammar") or "") == "porcelain_literal_analogy")
    split_right_cnt = sum(1 for c in clips if str(c.get("cut_role") or "").lower() in ("split_right", "split_bottom"))
    est_cuts = len(clips) - split_right_cnt
    return {
        "dir": str(pdir),
        "clip_count": len(clips),
        "estimated_cuts": est_cuts,
        "literal_analogy_clips": lit_cnt,
        "changed": changed,
        "issues": issues,
    }


def main() -> int:
    ap = argparse.ArgumentParser(description="Audit/rebalance 65 porcelain_cinematic_v7 queued drafts to 46-48 cuts.")
    ap.add_argument("--check-only", action="store_true", help="Validate without modifying files.")
    args = ap.parse_args()

    q_path = Path(config.CHANNEL_ROOT) / "porcelain_rebalanced_queue.json"
    q_doc = json.loads(q_path.read_text(encoding="utf-8"))
    queue = q_doc.get("queue") or []
    failed = []
    modified = 0
    synced_projects = 0
    clip_counts: list[int] = []
    cut_counts: list[int] = []

    for item in queue:
        draft_path = Path(item["porcelain_dir"])
        res = normalize_draft_dir(draft_path, write=not args.check_only)
        did_sync, sync_issues = _sync_unproduced_project_dir(
            draft_path,
            str(item.get("project_id") or ""),
            write=not args.check_only,
        )
        if did_sync:
            synced_projects += 1
        if sync_issues:
            res["issues"].extend(sync_issues)
        clip_counts.append(res["clip_count"])
        cut_counts.append(res["estimated_cuts"])
        if item.get("target_clips") != res["clip_count"] or item.get("target_cuts") != res["estimated_cuts"]:
            item["target_clips"] = res["clip_count"]
            item["target_cuts"] = res["estimated_cuts"]
        if res["changed"]:
            modified += 1
        if (
            res["issues"]
            or not (PORCELAIN_V7_TARGET_CLIP_MIN <= res["clip_count"] <= PORCELAIN_V7_TARGET_CLIP_MAX)
            or res["literal_analogy_clips"] > PORCELAIN_V7_LITERAL_ANALOGY_MAX_CLIPS
        ):
            failed.append((item["slug"], res["clip_count"], res["issues"]))

    if not args.check_only:
        q_doc["pacing_profile"] = {
            "target_clips_range": [PORCELAIN_V7_TARGET_CLIP_MIN, PORCELAIN_V7_TARGET_CLIP_MAX],
            "default_clips": DIORAMA_CLIP_COUNT_DEFAULT,
            "min_cut_sec": config.PORCELAIN_V7_MIN_CUT_SEC,
            "mid_act_max_cut_sec": config.PORCELAIN_V7_MID_ACT_MAX_CUT_SEC,
            "long_take_max_sec": config.PORCELAIN_V7_LONG_TAKE_MAX_SEC,
            "avg_cut_target_sec": [config.PORCELAIN_V7_AVG_CUT_MIN_SEC, config.PORCELAIN_V7_AVG_CUT_MAX_SEC],
            "measured_queue_clips_min_max": [min(clip_counts, default=0), max(clip_counts, default=0)],
            "measured_queue_cuts_min_max": [min(cut_counts, default=0), max(cut_counts, default=0)],
        }
        for p6 in q_doc.get("pilot_top_6") or []:
            match = next((it for it in queue if it.get("slug") == p6.get("slug")), None)
            if match:
                p6["target_clips"] = match["target_clips"]
                p6["target_cuts"] = match["target_cuts"]
        q_path.write_text(json.dumps(q_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")

    print(
        f"Audited {len(queue)} porcelain drafts (modified={modified}, synced_projects={synced_projects}, failed={len(failed)}, "
        f"clips={min(clip_counts, default=0)}..{max(clip_counts, default=0)}, "
        f"cuts={min(cut_counts, default=0)}..{max(cut_counts, default=0)}, "
        f"window={PORCELAIN_V7_TARGET_CLIP_MIN}..{PORCELAIN_V7_TARGET_CLIP_MAX})."
    )
    if failed:
        for slug, cc, iss in failed[:15]:
            print(f"  FAIL {slug} (clips={cc}): {iss[:4]}")
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
