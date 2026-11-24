"""
Canonical Asset Library Loader, SHA-256 Lock Enforcer & Per-Episode Provenance (`canonical_assets/v1` + `v1_1`).

Unified 85-Slot SHA-256 Locked Library (`v1`: 42 slots + `v1_1`: 43 slots = 85 approved anchors):
  1. Only slots and candidate files marked `"status": "approved"` with `"sha256_locked": true` in
     `v1/manifest.json` or `v1_1/manifest.json` may be resolved or staged into episode projects.
  2. Live file SHA-256 is verified against `approved_sha256` (or `approved_start_sha256` / `approved_end_sha256`
     for Category F `Start+End` transition pairs) on every resolution/staging call.
  3. Retired derivative anchors (`xray_brain75_master`, `ref_r78m_*`, `cand_01..05_*_xray_9x16`,
     `ep31_mode2_silver_cyan_style_master`), all 23 `[EXCL]` excluded outliers in `v1_1`, and all unapproved
     backup candidate files (`cand_01..04.png`, `cand_02_start/end.png`) are hard-blocked.
  4. Every episode records `03_visuals/reference_images/canonical_assets_provenance.json` (plus
     `00_project_manifest.json` `canonical_assets_lock`) binding the exact library version(s), slot IDs,
     frames, and verified SHA-256 digests used.
"""
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from pipeline.config import (
    CANONICAL_ASSETS_DEFAULT_VERSION,
    CANONICAL_ASSETS_VERSIONS,
    CANONICAL_PROVENANCE_FILENAME,
    CANONICAL_REF_IMAGE_SOURCES,
    CHANNEL_ROOT,
    R85_RETIRED_DERIVATIVE_BRAIN_ANCHORS,
    R88_RETIRED_CARTOON_CAST_SLOTS,
    REF_IMAGE_SOURCE_CANONICAL_V1,
    REF_IMAGE_SOURCE_CANONICAL_V1_1,
    REF_IMAGE_SOURCE_CANONICAL_V1_2,
    REF_IMAGES_DIRNAME,
    is_r88_faceless_cast_plan,
)


def _matches_retired_r88_slot_ref(val: Any) -> str | None:
    """Returns matching R88 retired cartoon slot ID if `val` references `B01-B15`, else None."""
    raw = str(val or "").strip()
    if not raw:
        return None
    low = raw.lower()
    for b_slot in R88_RETIRED_CARTOON_CAST_SLOTS:
        b_low = b_slot.lower()
        if b_low in low:
            return b_slot
    if re.search(r"(?:^|[_/\\])b(?:0[1-9]|1[0-5])_[a-z0-9_]+", low):
        m = re.search(r"(b(?:0[1-9]|1[0-5])_[a-z0-9_]+)", low)
        return m.group(1) if m else raw
    return None


class CanonicalAssetError(ValueError):
    """Raised when a requested canonical anchor is unapproved, missing, tampered, excluded, or retired."""


RETIRED_ANCHOR_PREFIXES: tuple[str, ...] = (
    "ref_r78m_",
    "xray_brain75_master",
    "ep31_mode2_silver_cyan_style_master",
    "cand_01_3q_subcortical_limbic_xray_9x16",
    "cand_02_side_profile_pfc_accumbens_xray_9x16",
    "cand_03_anterior_3q_dual_hub_xray_9x16",
    "cand_04_neutral_master_translucent_glass_9x16",
    "cand_05_elevated_3q_frontal_cyan_brainstem_red_9x16",
)

R88_PRE_R88_DOTTED_EYE_STAGED_ENV_SLOTS: dict[str, str] = {
    "E06_laboratory_staged": "E01_laboratory_empty",
    "E07_mri_suite_staged": "E02_mri_suite_empty",
    "E08_home_doorway_staged": "E03_home_doorway_empty",
    "E09_lecture_room_staged": "E04_lecture_room_empty",
    "E10_kitchen_staged": "E05_kitchen_empty",
    "E14_night_bedroom_staged": "E11_night_bedroom_empty",
    "E15_clinic_consult_office_staged": "E12_clinic_consult_office_empty",
    "E16_urban_street_sidewalk_staged": "E13_urban_street_sidewalk_empty",
}


def guard_r88_autobound_slot(slot_id: str, *, r88_faceless: bool = True) -> str:
    """Rejects pre-R88 cartoon-dot-eye E*_staged slots from being auto-bound under R88 faceless cast mode."""
    sid = str(slot_id or "").strip()
    if r88_faceless and sid in R88_PRE_R88_DOTTED_EYE_STAGED_ENV_SLOTS:
        clean_alt = R88_PRE_R88_DOTTED_EYE_STAGED_ENV_SLOTS[sid]
        raise CanonicalAssetError(
            f"Pre-R88 dotted-eye staged slot '{sid}' cannot be auto-bound under R88 faceless cast mode; "
            f"use clean faceless '{clean_alt}' instead."
        )
    return sid


def _normalize_version_key(version: str | None) -> str:
    raw = str(version or CANONICAL_ASSETS_DEFAULT_VERSION).strip().lower()
    if raw in ("v1.0", "1.0", "1.0.0"):
        return "v1"
    if raw in ("v1.1", "1.1", "1.1.0"):
        return "v1_1"
    if raw in ("v1.2", "1.2", "1.2.0"):
        return "v1_2"
    return raw


def _source_tag_for_version(version_key: str) -> str:
    vk = _normalize_version_key(version_key)
    if vk == "v1_2":
        return REF_IMAGE_SOURCE_CANONICAL_V1_2
    if vk == "v1_1":
        return REF_IMAGE_SOURCE_CANONICAL_V1_1
    return REF_IMAGE_SOURCE_CANONICAL_V1


def get_canonical_root(version: str = CANONICAL_ASSETS_DEFAULT_VERSION, custom_root: str | Path | None = None) -> Path:
    if custom_root is not None:
        return Path(custom_root)
    ver_norm = _normalize_version_key(version)
    env_override = os.environ.get("AAB_CANONICAL_ASSETS_DIR", "").strip()
    if env_override and ver_norm == CANONICAL_ASSETS_DEFAULT_VERSION:
        return Path(env_override)
    return Path(CHANNEL_ROOT) / "canonical_assets" / ver_norm


def compute_file_sha256(path: str | Path) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def load_canonical_manifest(
    version: str = CANONICAL_ASSETS_DEFAULT_VERSION,
    *,
    custom_root: str | Path | None = None,
    require_approved: bool = True,
) -> dict[str, Any]:
    ver_norm = _normalize_version_key(version)
    root = get_canonical_root(version=ver_norm, custom_root=custom_root)
    manifest_p = root / "manifest.json"
    if not manifest_p.is_file():
        raise CanonicalAssetError(f"Canonical Asset Library manifest missing: {manifest_p}")
    doc = json.loads(manifest_p.read_text(encoding="utf-8"))
    if require_approved and str(doc.get("status") or "") not in ("approved", "locked"):
        raise CanonicalAssetError(
            f"Canonical Asset Library {manifest_p} has status='{doc.get('status')}' (must be 'approved' or 'locked')"
        )
    return doc


def _approved_rel_paths_for_version(version_key: str) -> set[str]:
    approved_rels: set[str] = set()
    try:
        doc = load_canonical_manifest(version=version_key, require_approved=False)
    except Exception:
        return approved_rels
    for s in doc.get("slots") or []:
        if not isinstance(s, dict) or str(s.get("status") or "") not in ("approved", "retired_r88_cartoon_face"):
            continue
        for k in ("approved_rel_path", "approved_start_rel_path", "approved_end_rel_path"):
            val = str(s.get(k) or "").replace("\\", "/").strip().lower()
            if val:
                approved_rels.add(f"{version_key}/{val}")
                approved_rels.add(val)
    return approved_rels


def is_retired_derivative_anchor(name_or_path: str | Path | None) -> bool:
    if not name_or_path:
        return False
    raw = str(name_or_path).strip()
    if not raw:
        return False
    norm = raw.replace("\\", "/")
    base = Path(norm).name.lower()
    stem = Path(norm).stem.lower()
    retired_exact = {x.lower() for x in R85_RETIRED_DERIVATIVE_BRAIN_ANCHORS}
    if base in retired_exact or stem in retired_exact:
        return True
    if any(base.startswith(pfx) or stem.startswith(pfx) for pfx in RETIRED_ANCHOR_PREFIXES):
        return True
    # Block direct binding of any unapproved or [EXCL] candidate file inside canonical_assets/<ver>/
    low_norm = norm.lower()
    if "canonical_assets/" in low_norm and re.search(r"/cand_\d+(?:_(?:start|end))?\.png$", low_norm):
        target_vers: tuple[str, ...]
        if "/v1_2/" in low_norm:
            target_vers = ("v1_2",)
        elif "/v1_1/" in low_norm:
            target_vers = ("v1_1",)
        elif "/v1/" in low_norm:
            target_vers = ("v1",)
        else:
            target_vers = CANONICAL_ASSETS_VERSIONS
        approved_rels: set[str] = set()
        for vk in target_vers:
            approved_rels.update(_approved_rel_paths_for_version(vk))
        if not approved_rels:
            return True
        if not any(low_norm.endswith("/" + ar) or low_norm == ar for ar in approved_rels if ar):
            return True
    return False


def _locate_slot_version(
    slot_id: str,
    version: str = "auto",
    custom_root: str | Path | None = None,
) -> tuple[str, Path, dict[str, Any], dict[str, Any]]:
    ver_req = str(version or "auto").strip().lower()
    if custom_root is not None:
        vk = _normalize_version_key("v1" if ver_req == "auto" else ver_req)
        doc = load_canonical_manifest(version=vk, custom_root=custom_root, require_approved=True)
        slot_map = {str(s.get("slot_id")): s for s in (doc.get("slots") or []) if isinstance(s, dict)}
        if slot_id not in slot_map:
            raise CanonicalAssetError(f"Unknown canonical slot_id '{slot_id}' in {custom_root}")
        return vk, Path(custom_root), doc, slot_map[slot_id]

    if ver_req in ("auto", "all", "unified"):
        search_order = CANONICAL_ASSETS_VERSIONS
    else:
        primary = _normalize_version_key(ver_req)
        # Keep explicit version first; fall back to remaining locked versions if caller used default 'v1' with a v1_1 slot ID
        search_order = (primary,) + tuple(v for v in CANONICAL_ASSETS_VERSIONS if v != primary) if primary == CANONICAL_ASSETS_DEFAULT_VERSION else (primary,)

    last_err: str | None = None
    for vk in search_order:
        root = get_canonical_root(version=vk)
        if not (root / "manifest.json").is_file():
            continue
        try:
            doc = load_canonical_manifest(version=vk, custom_root=root, require_approved=True)
        except CanonicalAssetError as exc:
            last_err = str(exc)
            continue
        slot_map = {str(s.get("slot_id")): s for s in (doc.get("slots") or []) if isinstance(s, dict)}
        if slot_id in slot_map:
            return vk, root, doc, slot_map[slot_id]
    if last_err:
        raise CanonicalAssetError(last_err)
    raise CanonicalAssetError(f"Unknown canonical slot_id '{slot_id}' in canonical_assets/{version}")


def resolve_canonical_approved_slot(
    slot_id: str,
    *,
    version: str = "auto",
    frame: str = "single",
    custom_root: str | Path | None = None,
    verify_sha256: bool = True,
    allow_retired_r88: bool = False,
) -> dict[str, Any]:
    if is_retired_derivative_anchor(slot_id):
        raise CanonicalAssetError(f"Retired derivative anchor '{slot_id}' is permanently blocked; use canonical_assets v1/v1_1.")
    ver_key, root, doc, sl = _locate_slot_version(slot_id, version=version, custom_root=custom_root)
    slot_status = str(sl.get("status") or "")
    if slot_status == "retired_r88_cartoon_face":
        if not allow_retired_r88:
            raise CanonicalAssetError(
                f"Canonical slot '{slot_id}' is permanently retired under R88 ({slot_status}); "
                "use active faceless A/D/E/I/J/K slots instead."
            )
    elif slot_status != "approved":
        raise CanonicalAssetError(f"Canonical slot '{slot_id}' is not approved (status='{slot_status}')")

    approved_cands = [
        c
        for c in (sl.get("candidates") or [])
        if isinstance(c, dict)
        and str(c.get("status") or "") == "approved"
        and bool(c.get("sha256_locked"))
        and str(c.get("screening_tag") or "") != "excluded_outlier"
    ]
    if len(approved_cands) != 1:
        raise CanonicalAssetError(
            f"Canonical slot '{slot_id}' must have exactly 1 sha256_locked approved candidate (found {len(approved_cands)})"
        )
    cand = approved_cands[0]
    excl_set = set(sl.get("excluded_candidates") or [])

    is_pair = str(sl.get("category") or "") == "F_transitions" or str(sl.get("asset_type") or "") == "start_end_transition_pair"
    frame_norm = str(frame or "single").strip().lower()
    if is_pair and frame_norm in ("start", "end"):
        if frame_norm == "start":
            approved_fn = str(sl.get("approved_start_filename") or cand.get("start_filename") or "cand_01_start.png")
            rel_path = str(sl.get("approved_start_rel_path") or cand.get("start_rel_path") or "")
            expected_sha = str(sl.get("approved_start_sha256") or cand.get("start_sha256") or "").strip().lower()
            staged_fn = f"canonical_{slot_id}_start.png"
        else:
            approved_fn = str(sl.get("approved_end_filename") or cand.get("end_filename") or "cand_01_end.png")
            rel_path = str(sl.get("approved_end_rel_path") or cand.get("end_rel_path") or "")
            expected_sha = str(sl.get("approved_end_sha256") or cand.get("end_sha256") or "").strip().lower()
            staged_fn = f"canonical_{slot_id}_end.png"
    else:
        frame_norm = "single"
        approved_fn = str(sl.get("approved_filename") or cand.get("filename") or "cand_01.png")
        rel_path = str(sl.get("approved_rel_path") or cand.get("rel_path") or cand.get("preview_rel_path") or "")
        expected_sha = str(sl.get("approved_sha256") or cand.get("sha256") or cand.get("preview_sha256") or "").strip().lower()
        staged_fn = f"canonical_{slot_id}.png"

    if approved_fn in excl_set:
        raise CanonicalAssetError(f"Canonical candidate '{approved_fn}' on '{slot_id}' is permanently blocked ([EXCL] outlier)")

    abs_path = root / rel_path
    if not abs_path.is_file():
        raise CanonicalAssetError(f"Approved canonical file missing on disk for '{slot_id}' ({frame_norm}): {abs_path}")
    if verify_sha256:
        actual_sha = compute_file_sha256(abs_path).lower()
        if not expected_sha or actual_sha != expected_sha:
            raise CanonicalAssetError(
                f"SHA-256 lock mismatch for canonical slot '{slot_id}' ({abs_path}): "
                f"expected {expected_sha}, got {actual_sha}"
            )
    return {
        "library_version": ver_key,
        "manifest_version": str(doc.get("version") or ver_key),
        "slot_id": slot_id,
        "frame": frame_norm,
        "category": str(sl.get("category") or ""),
        "staged_filename": staged_fn,
        "approved_filename": approved_fn,
        "rel_path": rel_path,
        "abs_path": abs_path,
        "sha256": expected_sha,
        "when_to_use": str(sl.get("when_to_use") or ""),
    }


def resolve_canonical_transition_pair(
    slot_id: str,
    *,
    version: str = "v1_1",
    custom_root: str | Path | None = None,
    verify_sha256: bool = True,
    allow_retired_r88: bool = False,
) -> dict[str, Any]:
    start_res = resolve_canonical_approved_slot(
        slot_id,
        version=version,
        frame="start",
        custom_root=custom_root,
        verify_sha256=verify_sha256,
        allow_retired_r88=allow_retired_r88,
    )
    end_res = resolve_canonical_approved_slot(
        slot_id,
        version=version,
        frame="end",
        custom_root=custom_root,
        verify_sha256=verify_sha256,
        allow_retired_r88=allow_retired_r88,
    )
    return {
        "slot_id": slot_id,
        "library_version": start_res["library_version"],
        "category": start_res["category"],
        "start": start_res,
        "end": end_res,
    }


def list_all_approved_canonical_slots(
    versions: tuple[str, ...] = CANONICAL_ASSETS_VERSIONS,
    *,
    verify_sha256: bool = False,
    skip_unapproved: bool = True,
    include_retired_r88: bool = False,
) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    allowed_statuses = ("approved", "retired_r88_cartoon_face") if include_retired_r88 else ("approved",)
    for vk in versions:
        root = get_canonical_root(version=vk)
        if not (root / "manifest.json").is_file():
            continue
        doc = load_canonical_manifest(version=vk, custom_root=root, require_approved=not skip_unapproved)
        if skip_unapproved and str(doc.get("status") or "") not in ("approved", "locked"):
            continue
        for sl in doc.get("slots") or []:
            if not isinstance(sl, dict) or str(sl.get("status") or "") not in allowed_statuses:
                continue
            sid = str(sl["slot_id"])
            is_pair = str(sl.get("category") or "") == "F_transitions" or str(sl.get("asset_type") or "") == "start_end_transition_pair"
            if is_pair:
                items.append(
                    resolve_canonical_transition_pair(
                        sid,
                        version=vk,
                        verify_sha256=verify_sha256,
                        allow_retired_r88=include_retired_r88,
                    )
                )
            else:
                items.append(
                    resolve_canonical_approved_slot(
                        sid,
                        version=vk,
                        verify_sha256=verify_sha256,
                        allow_retired_r88=include_retired_r88,
                    )
                )
    return items


def select_canonical_brain_slot(
    *,
    brain_region: str = "",
    viewpoint: str = "",
    mode: str = "",
    shot_scale: str = "",
    neural_state: str = "",
    side_by_side: bool = False,
    allow_v1_1: bool = True,
) -> str:
    m_low = str(mode or "").strip().lower()
    sc_low = str(shot_scale or "").strip().lower()
    vp_low = str(viewpoint or "").strip().lower()
    reg_low = str(brain_region or "").strip().lower()
    ns_low = str(neural_state or "").strip().lower()

    if allow_v1_1:
        if any(k in reg_low for k in ("optic", "eye", "retina", "primary visual")):
            return "A16_eyes_optic_nerve_to_v1_pathway"
        if any(k in reg_low for k in ("spinal", "vagus", "descending", "pain gate")):
            return "A17_brain_spinal_body_descending_xray"
        if any(k in reg_low for k in ("synapse", "neurotransmitter", "receptor", "dopamine cleft")):
            return "A14_neuron_synapse_junction_macro"
        if sc_low == "1p_tract_canyon" or "tract_canyon" in vp_low:
            return "A13_1p_white_matter_tract_canyon"
        if any(k in reg_low for k in ("ventric", "csf", "glymphatic", "aqueduct")):
            return "A15_ventricular_csf_aqueduct_cutaway"
        if "anterior cingulate" in reg_low or "cingulate" in reg_low or bool(re.search(r"\bacc\b", reg_low)):
            return "A19_anterior_cingulate_amygdala_limbic_cutaway"
        if "coronal" in vp_low and any(k in reg_low for k in ("hippocamp", "amygdala", "medial temporal")):
            return "A18_coronal_bilateral_hippocampus_ventricles"

    if "mode1" in m_low or sc_low == "xray_head_dive":
        return "A01_mode1_translucent_head_lateral"
    if side_by_side or sc_low == "dual_brain_ab" or "a_vs_b" in vp_low or "dual" in sc_low:
        return "A12_dual_brain_top_bottom_compare"
    if sc_low in ("vessel_csf_macro", "1p_tract_canyon") or "macro" in vp_low or "sulcal" in reg_low:
        return "A05_sulcal_vessel_macro"
    if any(k in reg_low for k in ("hippocamp", "entorhinal", "parahippocamp", "medial temporal")):
        return "A06_hippocampus_cutaway"
    if any(k in reg_low for k in ("insula", "opercul", "sylvian")):
        return "A08_insula_operculum_retracted"
    if "midsagittal" in vp_low or any(
        k in reg_low for k in ("thalam", "brainstem", "pons", "medulla", "midbrain", "callosum", "cingulate", "ventric", "csf", "glymphatic", "locus coeruleus", "raphe")
    ):
        return "A07_thalamus_brainstem_midsagittal"
    if ns_low in ("silenced", "shutdown", "inhibited", "hypoactive"):
        return "A11_region_shutdown_sample"
    if any(k in reg_low for k in ("prefrontal", "dlpfc", "vmpfc", "orbitofrontal", "frontal pole")):
        return "A09_prefrontal_cortex_3q_anterolateral"
    if "dorsal" in vp_low or "top_down" in vp_low or "topdown" in vp_low or "hemisphere" in reg_low:
        return "A03_mode2_whole_brain_dorsal_topdown"
    if "anterior" in vp_low and "three_quarter" not in vp_low and "3q" not in vp_low:
        return "A04_mode2_whole_brain_anterior_frontal"
    if ns_low in ("tract_pulse", "signal_relay", "rerouted", "severed") or "tract" in reg_low or "fasciculus" in reg_low:
        return "A10_signal_segment_sample"
    return "A02_mode2_whole_brain_lateral"


def select_canonical_character_slot(
    *,
    role_hint: str = "",
    expression_hint: str = "",
    wardrobe_hint: str = "",
    r88_faceless: bool = False,
) -> str:
    """Maps character/context hints to active brain/environment slots (empty E*_empty rooms under R88 faceless mode)."""
    hints = f"{wardrobe_hint} {role_hint} {expression_hint}".strip().lower()
    if any(k in hints for k in ("mri", "fmri", "scanner")):
        return "E02_mri_suite_empty" if r88_faceless else "E07_mri_suite_staged"
    if any(
        k in hints
        for k in (
            "scrub",
            "surgeon",
            "operating",
            "lab coat",
            "clinical",
            "clinic",
            "lab",
            "laboratory",
            "scientist",
            "researcher",
            "neurologist",
            "doctor",
            "clinician",
            "hospital",
        )
    ):
        return "E01_laboratory_empty" if r88_faceless else "E06_laboratory_staged"
    if any(k in hints for k in ("kitchen", "dining", "coffee", "breakfast", "snack", "pudding", "yogurt")):
        return "E05_kitchen_empty" if r88_faceless else "E10_kitchen_staged"
    return "A01_mode1_translucent_head_lateral"


def select_canonical_arrow_slot(arrow_mode: str = "", *, prefer_v1_2: bool = False) -> str:
    m = str(arrow_mode or "").strip().lower()
    if prefer_v1_2:
        if any(k in m for k in ("sever", "gap", "doorway", "halt", "block")):
            return "C03b_spatial_doorway_sever_with_prop"
        if any(k in m for k in ("dual", "race", "zigzag", "detour", "side by side", "vs", "versus")):
            return "C02b_spatial_dual_route_prop_legend"
        return "C01b_spatial_corridor_with_anchor_prop"
    if any(k in m for k in ("sever", "gap", "doorway", "halt", "block")):
        return "C03_arrow_doorway_sever_gap"
    if any(k in m for k in ("straight", "corridor", "direct", "linear")):
        return "C01_arrow_straight_corridor"
    return "C02_arrow_adaptive_zigzag"


def select_canonical_hook_slot(hook_visual_mode: str = "", topic_hint: str = "") -> str:
    """Selects a Canonical v1.2 Category J (`J01–J06`) 0.0s–3.0s hook pattern-interrupt anchor."""
    hm = str(hook_visual_mode or "").strip().lower()
    th = str(topic_hint or "").strip().lower()
    if hm == "mode2_instant_brain_shock":
        return "J05_hook_mode2_instant_brain_shock_open"
    if hm == "bizarre_prop_interrupt":
        if any(k in th for k in ("capsule", "pill", "spoon", "tabletop", "hands", "scale", "pudding", "snack")):
            return "J04_hook_paradox_prop_split_tabletop"
        if any(k in th for k in ("shock", "disbelief", "reaction", "portrait")):
            return "J06_hook_extreme_2d_ink_shock_reaction"
        return "J03_hook_bizarre_experiment_prop_closeup"
    if any(k in th for k in ("sleep", "insomnia", "paralysis", "bed", "night", "pillow", "dream", "rem")):
        return "J02_hook_mode1_bedside_sleep_anomaly"
    return "J01_hook_mode1_daily_action_xray_alert"


def select_canonical_nonspatial_contrast_slot(topic_hint: str = "", contrast_hint: str = "") -> str:
    """Selects a Canonical v1.2 Category K (`K01–K06`) non-spatial A vs B physical/brain contrast anchor."""
    txt = f"{topic_hint} {contrast_hint}".strip().lower()
    if any(k in txt for k in ("dual brain", "a12", "brain state", "top vs bottom", "stacked brain", "start+end brain")):
        return "K06_contrast_a12_dual_brain_state_transition_pair"
    if any(k in txt for k in ("scale", "weight", "0 lb", "pound", "unchanged", "dial", "flat")):
        return "K05_contrast_scale_flat_vs_internal_surge_split"
    if any(k in txt for k in ("lock", "receptor", "gaba", "glycine", "paralysis", "brake", "switch", "gate", "inhibit")):
        return "K04_contrast_dual_receptor_chemical_lock_panel"
    if any(k in txt for k in ("sponge", "rinse", "wash basin", "soak", "clean")):
        return "K02_contrast_squeezed_vs_stalled_sponge_basins"
    if any(k in txt for k in ("fluid", "csf", "glymphatic", "tube", "vessel", "blood", "flow", "pipe", "channel")):
        return "K01_contrast_active_vs_blocked_fluid_tubes"
    return "K03_contrast_twin_tabletop_stimulus_ab"


def select_canonical_drone_slot(env_hint: str = "") -> str:
    e = str(env_hint or "").strip().lower()
    if any(k in e for k in ("hospital", "clinic", "medical center", "infirmary", "nih")):
        return "D02_drone_medical_hospital_120ft"
    return "D01_drone_university_campus_120ft"


def select_canonical_environment_slot(
    env_hint: str = "",
    *,
    staged: bool = False,
    allow_v1_1: bool = True,
    r88_faceless: bool = False,
) -> str:
    e = str(env_hint or "").strip().lower()
    eff_staged = False if r88_faceless else bool(staged)
    if allow_v1_1:
        if any(k in e for k in ("bedroom", "insomnia", "nightstand", "bed edge", "pillow")):
            return "E14_night_bedroom_staged" if eff_staged else "E11_night_bedroom_empty"
        if any(k in e for k in ("consult", "clinic office", "doctor office", "physician desk")):
            return "E15_clinic_consult_office_staged" if eff_staged else "E12_clinic_consult_office_empty"
        if any(k in e for k in ("sidewalk", "street walk", "park path", "urban street", "commute walk")):
            return "E16_urban_street_sidewalk_staged" if eff_staged else "E13_urban_street_sidewalk_empty"
    if any(k in e for k in ("mri", "scanner", "fmri", "neuroimaging")):
        return "E07_mri_suite_staged" if eff_staged else "E02_mri_suite_empty"
    if any(k in e for k in ("doorway", "threshold", "hallway", "entry", "living room")):
        return "E08_home_doorway_staged" if eff_staged else "E03_home_doorway_empty"
    if any(k in e for k in ("lecture", "classroom", "seminar", "auditorium", "university room")):
        return "E09_lecture_room_staged" if eff_staged else "E04_lecture_room_empty"
    if any(k in e for k in ("kitchen", "breakfast", "coffee", "mug", "island")):
        return "E10_kitchen_staged" if eff_staged else "E05_kitchen_empty"
    return "E06_laboratory_staged" if eff_staged else "E01_laboratory_empty"


def select_canonical_prop_slot(prop_hint: str = "") -> str:
    p = str(prop_hint or "").strip().lower()
    if any(k in p for k in ("lightbox", "mri film", "dual scan", "brain scan sheet")):
        return "G01_mri_lightbox_dual_brain_scans"
    if any(k in p for k in ("eeg", "electrode", "cap")):
        return "G02_eeg_electrode_cap_vinyl_head"
    if any(k in p for k in ("pill", "bottle", "vial", "capsule", "placebo", "zolpidem")):
        return "G03_unlabeled_amber_pill_bottle_and_capsules"
    if any(k in p for k in ("maze", "labyrinth")):
        return "G04_tabletop_3d_experimental_maze"
    if any(k in p for k in ("map", "street", "route")):
        return "G05_unlabeled_street_map_and_pointer"
    if any(k in p for k in ("stopwatch", "timer", "clock")):
        return "G06_numeral_free_brass_stopwatch"
    if any(k in p for k in ("box", "block", "occlusion", "doorway object")):
        return "G07_white_occlusion_box_and_plain_blocks"
    if any(k in p for k in ("card", "rey", "geometric", "sketchpad")):
        return "G08_geometric_stimulus_cards_and_sketchpads"
    return "G09_graphic_icon_smartphone_and_tablet"


def select_canonical_misconception_slot(hint: str = "") -> str:
    h = str(hint or "").strip().lower()
    if any(k in h for k in ("padlock", "fixed", "locked", "case", "acrylic")):
        return "H01_padlocked_acrylic_plaster_brain_case"
    if any(k in h for k in ("switch", "off", "silent", "bulb", "dormant")):
        return "H02_dormant_off_toggle_switch_panel"
    if any(k in h for k in ("empty", "separate", "disconnect", "sever", "pull apart")):
        return "H03_pulled_apart_empty_clear_capsule"
    return "H04_physical_red_x_over_simple_diagram_card"


def select_canonical_layout_slot(hint: str = "") -> str:
    h = str(hint or "").strip().lower()
    if any(k in h for k in ("dark", "brain", "void")) and any(k in h for k in ("stamp", "chart", "gauge", "bar")):
        return "I02_data_stamp_backdrop_dark_brain_low38"
    if any(k in h for k in ("stamp", "chart", "tabletop", "wall", "headroom")):
        return "I01_data_stamp_backdrop_warm_tabletop_low30"
    if any(k in h for k in ("callout", "safezone", "cutaway")):
        return "I03_callout_safezone_brain_headroom_frame"
    if any(k in h for k in ("thumbnail", "50/50", "split")):
        return "I04_thumbnail_50_50_in_skull_split_frame"
    return "I05_ending_warm_takeaway_resolution_frame"


def select_canonical_transition_slot(hint: str = "") -> str:
    h = str(hint or "").strip().lower()
    if any(k in h for k in ("sponge", "metaphor", "shape bridge", "prop_to_anatomy")):
        return "F04_metaphor_prop_to_anatomy_shape_bridge"
    if any(k in h for k in ("human_profile", "xray_head", "head_enter")):
        return "F01_human_profile_to_mode1_xray_head"
    if any(k in h for k in ("mode1", "cranium", "whole_brain")):
        return "F02_mode1_xray_head_to_mode2_whole_brain"
    if any(k in h for k in ("tract", "canyon", "1p")):
        return "F03b_sulcal_vessel_macro_to_1p_tract_canyon"
    if any(k in h for k in ("sulcal", "vessel_macro")):
        return "F03a_whole_brain_to_sulcal_vessel_macro"
    if any(k in h for k in ("drone", "courtyard", "portico")):
        return "F05a_drone_120ft_to_courtyard_portico"
    if any(k in h for k in ("window", "interior", "lab_portal")):
        return "F05b_window_threshold_to_staged_interior"
    if any(k in h for k in ("corridor", "topdown", "arrow")):
        return "F06_oblique_corridor_to_topdown_r80_arrow"
    if any(k in h for k in ("return", "real_world", "pullout")):
        return "F07_mode2_brain_to_vinyl_character_return"
    if any(k in h for k in ("prop_settle", "tabletop_stamp")):
        return "F08a_prop_settle_for_data_stamp_entry"
    if any(k in h for k in ("brain_settle", "dark_stamp")):
        return "F08b_brain_settle_for_data_stamp_entry"
    return "F09_single_brain_to_dual_top_bottom_compare"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_canprov_", suffix=".json")
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        tmp_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(tmp_p, path)
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)


def stage_canonical_slot_to_project(
    project_dir: str | Path,
    slot_id: str,
    *,
    dest_filename: str | None = None,
    version: str = "auto",
    frame: str = "single",
    custom_root: str | Path | None = None,
    allow_retired_r88: bool = False,
) -> dict[str, Any]:
    """
    Copies the SHA-256-verified approved canonical PNG (`v1` or `v1_1`) into
    `<project_dir>/03_visuals/reference_images/`, registers canonical provenance,
    and updates `canonical_assets_provenance.json` + `00_project_manifest.json` (`canonical_assets_lock`).
    """
    p_dir = Path(project_dir)
    resolved = resolve_canonical_approved_slot(
        slot_id,
        version=version,
        frame=frame,
        custom_root=custom_root,
        verify_sha256=True,
        allow_retired_r88=allow_retired_r88,
    )
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    fname = str(dest_filename or resolved["staged_filename"]).strip()
    if is_retired_derivative_anchor(fname):
        raise CanonicalAssetError(f"Cannot stage canonical slot '{slot_id}' under retired filename '{fname}'")

    dst_p = ref_dir / fname
    need_copy = True
    if dst_p.is_file():
        if compute_file_sha256(dst_p).lower() == resolved["sha256"]:
            need_copy = False
    if need_copy:
        tmp_dst = ref_dir / f".tmp_stage_{os.getpid()}_{fname}"
        shutil.copy2(resolved["abs_path"], tmp_dst)
        os.replace(tmp_dst, dst_p)

    from pipeline.ref_qa import register_reference_image

    register_reference_image(p_dir, fname, _source_tag_for_version(resolved["library_version"]))
    record_project_canonical_slot_usage(
        p_dir,
        staged_filename=fname,
        resolved_slot=resolved,
        custom_root=custom_root,
    )
    return {**resolved, "staged_filename": fname, "staged_path": dst_p}


def stage_canonical_transition_pair_to_project(
    project_dir: str | Path,
    slot_id: str,
    *,
    start_filename: str | None = None,
    end_filename: str | None = None,
    version: str = "v1_1",
    custom_root: str | Path | None = None,
) -> dict[str, Any]:
    st_start = stage_canonical_slot_to_project(
        project_dir,
        slot_id,
        dest_filename=start_filename,
        version=version,
        frame="start",
        custom_root=custom_root,
    )
    st_end = stage_canonical_slot_to_project(
        project_dir,
        slot_id,
        dest_filename=end_filename,
        version=version,
        frame="end",
        custom_root=custom_root,
    )
    return {
        "slot_id": slot_id,
        "library_version": st_start["library_version"],
        "start": st_start,
        "end": st_end,
    }


def record_project_canonical_slot_usage(
    project_dir: str | Path,
    *,
    staged_filename: str,
    resolved_slot: dict[str, Any],
    custom_root: str | Path | None = None,
) -> dict[str, Any]:
    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    ref_dir.mkdir(parents=True, exist_ok=True)
    prov_path = ref_dir / CANONICAL_PROVENANCE_FILENAME

    version = _normalize_version_key(resolved_slot.get("library_version") or CANONICAL_ASSETS_DEFAULT_VERSION)
    root = get_canonical_root(version=version, custom_root=custom_root)
    manifest_sha = compute_file_sha256(root / "manifest.json") if (root / "manifest.json").is_file() else ""

    existing: dict[str, Any] = {}
    if prov_path.is_file():
        try:
            existing = json.loads(prov_path.read_text(encoding="utf-8")) or {}
        except Exception:
            existing = {}

    files_map: dict[str, Any] = dict(existing.get("files") or {})
    files_map[staged_filename] = {
        "slot_id": resolved_slot["slot_id"],
        "frame": str(resolved_slot.get("frame") or "single"),
        "category": resolved_slot["category"],
        "canonical_rel_path": resolved_slot["rel_path"],
        "sha256": resolved_slot["sha256"],
        "library_version": version,
    }

    manifest_shas_by_ver: dict[str, str] = dict(existing.get("canonical_manifest_sha256_by_version") or {})
    if manifest_sha:
        manifest_shas_by_ver[version] = manifest_sha
    libs_used = sorted({_normalize_version_key(v.get("library_version") or "v1") for v in files_map.values()})
    for lv in libs_used:
        if lv not in manifest_shas_by_ver:
            lv_root = get_canonical_root(version=lv, custom_root=custom_root if lv == version else None)
            if (lv_root / "manifest.json").is_file():
                manifest_shas_by_ver[lv] = compute_file_sha256(lv_root / "manifest.json")

    top_lib_ver = "+".join(libs_used) if len(libs_used) > 1 else (libs_used[0] if libs_used else version)
    doc = {
        "schema": "aab_project_canonical_provenance_v1",
        "project_id": p_dir.name,
        "library_version": top_lib_ver,
        "libraries_used": libs_used,
        "canonical_manifest_sha256": manifest_shas_by_ver.get("v1", manifest_sha),
        "canonical_manifest_sha256_by_version": manifest_shas_by_ver,
        "updated_at_utc": datetime.now(timezone.utc).isoformat(),
        "files": dict(sorted(files_map.items())),
    }
    _atomic_write_json(prov_path, doc)

    # Mirror summary into 00_project_manifest.json if present
    proj_manifest_p = p_dir / "00_project_manifest.json"
    if proj_manifest_p.is_file():
        try:
            pm = json.loads(proj_manifest_p.read_text(encoding="utf-8"))
            if isinstance(pm, dict):
                pm["canonical_assets_lock"] = {
                    "library_version": top_lib_ver,
                    "libraries_used": libs_used,
                    "canonical_manifest_sha256": doc["canonical_manifest_sha256"],
                    "canonical_manifest_sha256_by_version": manifest_shas_by_ver,
                    "provenance_file": f"03_visuals/{REF_IMAGES_DIRNAME}/{CANONICAL_PROVENANCE_FILENAME}",
                    "locked_file_count": len(doc["files"]),
                    "slots_used": sorted({v["slot_id"] for v in doc["files"].values()}),
                }
                _atomic_write_json(proj_manifest_p, pm)
        except Exception:
            pass
    return doc


def validate_project_canonical_provenance(
    project_dir: str | Path,
    *,
    custom_root: str | Path | None = None,
) -> dict[str, Any]:
    """
    Audits `<project_dir>/03_visuals/reference_images/` to verify:
      1. Zero retired derivative anchors (`xray_brain75_master`, `ref_r78m_*`, etc.) or `[EXCL]` outliers exist.
      2. Every image with source `canonical_assets_v1` or `canonical_assets_v1_1` in `provenance.json` has a matching
         entry in `canonical_assets_provenance.json`, maps to an `approved` slot in `v1` or `v1_1`, and matches
         the locked SHA-256 byte-for-byte.
    """
    p_dir = Path(project_dir)
    ref_dir = p_dir / "03_visuals" / REF_IMAGES_DIRNAME
    issues: list[str] = []

    if ref_dir.is_dir():
        for img_p in sorted(ref_dir.glob("*.png")):
            if is_retired_derivative_anchor(img_p.name):
                issues.append(f"[canonical_retired_anchor] Retired anchor file staged in project: {img_p.name}")

    vp_p = p_dir / "03_visuals" / "visual_plan.json"
    if vp_p.is_file():
        try:
            vp = json.loads(vp_p.read_text(encoding="utf-8")) or {}
            enforce_r88 = is_r88_faceless_cast_plan(vp, project_id=p_dir.name)
            for c_idx, c in enumerate(vp.get("clips") or [], start=1):
                if not isinstance(c, dict):
                    continue
                for k in ("reference_image", "secondary_reference_image", "end_reference_image"):
                    val = str(c.get(k) or "").strip()
                    if is_retired_derivative_anchor(val):
                        issues.append(f"[canonical_retired_anchor] visual_plan clip {c_idx} {k} uses retired anchor '{val}'")
                if enforce_r88:
                    for k in (
                        "canonical_slot_id",
                        "reference_image",
                        "secondary_reference_image",
                        "start_frame_image",
                        "end_frame_image",
                        "end_reference_image",
                    ):
                        hit_b = _matches_retired_r88_slot_ref(c.get(k))
                        if hit_b:
                            issues.append(
                                f"[r88_retired_cartoon_cast_ban] visual_plan clip {c_idx} {k} uses retired cartoon-cast slot '{hit_b}' (R88)"
                            )
                    for cond_id in c.get("conditioned_on") or []:
                        hit_b = _matches_retired_r88_slot_ref(cond_id)
                        if hit_b:
                            issues.append(
                                f"[r88_retired_cartoon_cast_ban] visual_plan clip {c_idx} conditioned_on uses retired cartoon-cast slot '{hit_b}' (R88)"
                            )
            for anc in vp.get("reference_anchors") or []:
                if not isinstance(anc, dict):
                    continue
                afn = str(anc.get("filename") or anc.get("ref_id") or "")
                if is_retired_derivative_anchor(afn):
                    issues.append(f"[canonical_retired_anchor] reference_anchors entry uses retired anchor '{afn}'")
                if enforce_r88:
                    for field_val in (anc.get("canonical_slot_id"), anc.get("filename"), anc.get("ref_id")):
                        hit_b = _matches_retired_r88_slot_ref(field_val)
                        if hit_b:
                            issues.append(
                                f"[r88_retired_cartoon_cast_ban] reference_anchors '{afn}' uses retired cartoon-cast slot '{hit_b}' (R88)"
                            )
                for cond_id in anc.get("conditioned_on") or []:
                    if is_retired_derivative_anchor(str(cond_id)):
                        issues.append(
                            f"[canonical_retired_anchor] reference_anchors '{afn}' conditioned_on retired anchor '{cond_id}'"
                        )
                    if enforce_r88:
                        hit_b = _matches_retired_r88_slot_ref(cond_id)
                        if hit_b:
                            issues.append(
                                f"[r88_retired_cartoon_cast_ban] reference_anchors '{afn}' conditioned_on retired cartoon-cast slot '{hit_b}' (R88)"
                            )
        except Exception as exc:
            issues.append(f"[canonical_provenance] Failed reading visual_plan.json: {exc}")

    prov_p = ref_dir / "provenance.json"
    can_prov_p = ref_dir / CANONICAL_PROVENANCE_FILENAME
    prov_map: dict[str, str] = {}
    if prov_p.is_file():
        try:
            prov_map = json.loads(prov_p.read_text(encoding="utf-8")) or {}
        except Exception:
            prov_map = {}

    canonical_tagged = [fn for fn, src in prov_map.items() if src in CANONICAL_REF_IMAGE_SOURCES]
    can_doc: dict[str, Any] = {}
    if can_prov_p.is_file():
        try:
            can_doc = json.loads(can_prov_p.read_text(encoding="utf-8")) or {}
        except Exception as exc:
            issues.append(f"[canonical_provenance] Corrupt {CANONICAL_PROVENANCE_FILENAME}: {exc}")

    recorded_files = can_doc.get("files") or {}
    if canonical_tagged and not can_prov_p.is_file():
        issues.append(f"[canonical_provenance] Missing {CANONICAL_PROVENANCE_FILENAME} despite canonical_assets images")

    for fn in canonical_tagged:
        if fn not in recorded_files:
            issues.append(f"[canonical_provenance] '{fn}' missing from {CANONICAL_PROVENANCE_FILENAME}")
            continue
        rec = recorded_files[fn]
        slot_id = str(rec.get("slot_id") or "")
        ver = _normalize_version_key(rec.get("library_version") or CANONICAL_ASSETS_DEFAULT_VERSION)
        frame = str(rec.get("frame") or "single").strip().lower()
        try:
            approved = resolve_canonical_approved_slot(
                slot_id,
                version=ver,
                frame=frame,
                custom_root=custom_root,
                verify_sha256=True,
                allow_retired_r88=True,
            )
        except CanonicalAssetError as exc:
            issues.append(f"[canonical_provenance] '{fn}' -> {exc}")
            continue
        staged_p = ref_dir / fn
        if not staged_p.is_file():
            issues.append(f"[canonical_provenance] Staged canonical image missing on disk: {fn}")
            continue
        disk_sha = compute_file_sha256(staged_p).lower()
        if disk_sha != approved["sha256"] or str(rec.get("sha256") or "").lower() != approved["sha256"]:
            issues.append(
                f"[canonical_sha256_mismatch] '{fn}' ({slot_id}) SHA-256 mismatch: "
                f"disk={disk_sha}, recorded={rec.get('sha256')}, approved={approved['sha256']}"
            )

    return {
        "passed": len(issues) == 0,
        "library_version": can_doc.get("library_version") or CANONICAL_ASSETS_DEFAULT_VERSION,
        "libraries_used": can_doc.get("libraries_used") or [can_doc.get("library_version") or CANONICAL_ASSETS_DEFAULT_VERSION],
        "locked_file_count": len(recorded_files),
        "issues": issues,
    }
