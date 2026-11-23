"""
ALL ABOUT BRAIN — R89 Archival & Supplementary Experiment Video Engine (`Gear 4 PyAV`, `0` Flow Uploads).

Supports safe `2.0–4.0s` muted real-experiment video inserts via two `1080x1920` UI-safe layouts:
  - Mode 1 (`split_sync`): Top rounded real-video viewport (`80..908, 288..728`) + CC-BY cropped/muted
    sync bridge (`735..767`) + synced bespoke Ep #31 3D brain clip (`80..908, 774..1218`).
  - Mode 2 (`viewfinder_locator`): Large dark-navy rounded viewfinder (`80..908, 288..1058`) + `200x200`
    `A01` matte-white porcelain head locator badge (`94..294, 948..1148`) + credit pill (`312..896, 1084..1138`).

Zero Fair Use gambling: permits ONLY verified Tier 1 (`17 U.S.C. § 105` intramural federal work, `CC0 1.0`,
or pre-1931 silent PD) and Tier 2 (`CC BY 4.0`/`3.0` peer-reviewed supplementary movies passing journal,
caption carve-out, `0%` audio, multi-frame `5fps` `YuNet < 0.42` face scan, motion, Cut >= 2 / `>= 2.20s`,
and combined `R88-A + R89 <= 2` cuts & `<= 10%` duration budget).
"""

from __future__ import annotations

import hashlib
import json
import os
import re
import tempfile
from pathlib import Path
from typing import Any

import av
import cv2
import numpy as np
from PIL import Image, ImageDraw

from pipeline.archival_insert_builder import (
    _load_inter_or_dejavu_font,
    _overlay_rgba_onto_bgr,
    normalize_cc_by_label,
)
from pipeline.config import (
    R89_CAPTION_EXCLUSION_PATTERNS,
    R89_CLASSIC_BANNED_SOURCE_KEYWORDS,
    R89_COMBINED_ARCHIVAL_MAX_CUTS,
    R89_COMBINED_ARCHIVAL_MAX_DURATION_SHARE,
    R89_FEDERAL_INTRAMURAL_AGENCIES,
    R89_MIN_CUT_INDEX,
    R89_MIN_FRAME_DIFF,
    R89_MIN_START_SEC,
    R89_MODE1_BOTTOM_BRAIN_BOX,
    R89_MODE1_CREDIT_BOX,
    R89_MODE1_TOP_VIDEO_BOX,
    R89_MODE2_CREDIT_BOX,
    R89_MODE2_LOCATOR_BADGE_BOX,
    R89_MODE2_VIEWFINDER_BOX,
    R89_SAFE_OUTER_BOX,
    R89_VIDEO_DURATION_RANGE,
    R89_YUNET_FACE_SCORE_THRESHOLD,
    R89_YUNET_SAMPLE_FPS,
    WORKSPACE_ROOT,
)
from pipeline.real_world_reference_builder import classify_media_license
from pipeline.source_reenactment import detect_human_faces_yunet

ARCHIVAL_VIDEOS_MANIFEST_REL = "03_visuals/archival_videos_manifest.json"
ARCHIVAL_VIDEO_CLIPS_DIRNAME = "archival_video_clips"
R89_VALID_MODES: frozenset[str] = frozenset({"split_sync", "viewfinder_locator"})
R89_FPS = 30
R89_WIDTH = 1080
R89_HEIGHT = 1920
_MATTE_BGR: tuple[int, int, int] = (22, 12, 8)  # #080C16
_FRAME_OUTER_RGBA: tuple[int, int, int, int] = (28, 38, 59, 255)  # #1C263B
_FRAME_INNER_RGBA: tuple[int, int, int, int] = (49, 66, 98, 255)  # #314262
_CARD_BG_RGBA: tuple[int, int, int, int] = (14, 21, 38, 240)
DEFAULT_A01_HEAD_PATH = (
    WORKSPACE_ROOT
    / "BCI_Shorts_Channel"
    / "canonical_assets"
    / "v1"
    / "A_brain"
    / "A01_mode1_translucent_head_lateral"
    / "cand_01.png"
)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_r89_", suffix=".json")
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        tmp_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(str(tmp_p), str(path))
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)


def _extract_entries_key(doc: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    for key in ("videos", "inserts", "clips", "items"):
        val = doc.get(key)
        if isinstance(val, list):
            return key, [x for x in val if isinstance(x, dict)]
    return "videos", []


def _parse_pub_year(item: dict[str, Any]) -> int:
    raw = item.get("publication_year")
    if raw is None or raw == "":
        return 9999
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 9999


def count_mp4_audio_streams(video_path: str | Path) -> int:
    """Returns the number of audio streams inside `video_path` via PyAV."""
    vp = Path(video_path)
    if not vp.is_file():
        return -1
    container = av.open(str(vp))
    try:
        return len(container.streams.audio)
    finally:
        container.close()


def _resolve_manifest_context(
    manifest_or_dir: str | Path | dict[str, Any],
) -> tuple[dict[str, Any] | None, Path | None, Path | None, Path | None, bool, str | None]:
    if isinstance(manifest_or_dir, dict):
        raw_pdir = manifest_or_dir.get("project_dir")
        p_dir = Path(str(raw_pdir)) if raw_pdir else None
        v_dir = (p_dir / "03_visuals") if p_dir is not None else None
        return manifest_or_dir, None, v_dir, p_dir, False, None

    p = Path(manifest_or_dir)
    if p.suffix.lower() == ".json":
        manifest_path = p
        v_dir = p.parent
        p_dir = v_dir.parent if v_dir.name == "03_visuals" else v_dir
        if not manifest_path.is_file():
            return None, manifest_path, v_dir, p_dir, True, f"[r89_manifest_missing] {manifest_path}"
        try:
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return None, manifest_path, v_dir, p_dir, True, f"[r89_manifest_corrupt] {manifest_path}: {exc}"
        if not isinstance(doc, dict):
            return None, manifest_path, v_dir, p_dir, True, f"[r89_manifest_invalid] {manifest_path}: expected JSON object"
        return doc, manifest_path, v_dir, p_dir, True, None

    p_dir = p
    v_dir = p_dir / "03_visuals"
    manifest_path = p_dir / ARCHIVAL_VIDEOS_MANIFEST_REL
    if not manifest_path.is_file():
        return None, manifest_path, v_dir, p_dir, False, None
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, manifest_path, v_dir, p_dir, False, f"[r89_manifest_corrupt] {manifest_path}: {exc}"
    if not isinstance(doc, dict):
        return None, manifest_path, v_dir, p_dir, False, f"[r89_manifest_invalid] {manifest_path}: expected JSON object"
    return doc, manifest_path, v_dir, p_dir, False, None


def _resolve_media_path(
    item: dict[str, Any],
    keys: tuple[str, ...],
    *,
    project_dir: Path | None,
    visuals_dir: Path | None,
    manifest_path: Path | None,
) -> Path | None:
    raw = ""
    for k in keys:
        v = str(item.get(k) or "").strip()
        if v:
            raw = v
            break
    if not raw:
        return None
    rp = Path(raw)
    if rp.is_absolute():
        return rp
    candidates: list[Path] = []
    if project_dir is not None:
        candidates.append(project_dir / rp)
    if visuals_dir is not None:
        candidates.append(visuals_dir / rp)
    if manifest_path is not None:
        candidates.append(manifest_path.parent / rp)
    candidates.append(rp)
    for cand in candidates:
        if cand.is_file():
            return cand
    return candidates[0]


def _resolve_rendered_clip_path(item: dict[str, Any], visuals_dir: Path) -> Path | None:
    rel_raw = str(item.get("rendered_clip_rel_path") or "").strip().replace("\\", "/")
    if not rel_raw:
        return None
    v_resolved = visuals_dir.resolve()
    candidates: list[Path] = []
    if rel_raw.startswith("03_visuals/"):
        candidates.append(visuals_dir.parent / rel_raw)
        candidates.append(visuals_dir / rel_raw[len("03_visuals/") :])
    else:
        candidates.append(visuals_dir / rel_raw)
    for cand in candidates:
        try:
            c_res = cand.resolve()
            c_res.relative_to(v_resolved)
        except ValueError:
            continue
        if c_res.is_file():
            return cand
    return None


def _normalize_crop_box(raw_crop: Any, width: int, height: int) -> tuple[int, int, int, int] | None:
    if not isinstance(raw_crop, (list, tuple)) or len(raw_crop) != 4:
        return None
    try:
        x0, y0, x1, y1 = [int(round(float(v))) for v in raw_crop]
    except (TypeError, ValueError):
        return None
    x0 = max(0, min(width - 16, x0))
    y0 = max(0, min(height - 16, y0))
    x1 = max(x0 + 16, min(width, x1))
    y1 = max(y0 + 16, min(height, y1))
    return (x0, y0, x1, y1)


def _decode_video_frames_with_fps(
    video_path: Path,
    *,
    sample_fps: float | None = None,
    crop_box: Any = None,
) -> tuple[list[np.ndarray], float]:
    """Decode all frames (or evenly sampled at `sample_fps`) as BGR uint8 arrays."""
    container = av.open(str(video_path))
    try:
        if not container.streams.video:
            raise ValueError(f"Video has no video streams: {video_path}")
        v_stream = container.streams.video[0]
        src_fps = float(v_stream.average_rate or v_stream.base_rate or 30.0)
        if src_fps <= 1.0 or src_fps > 240.0:
            src_fps = 30.0

        all_bgr: list[np.ndarray] = []
        for frame in container.decode(video=0):
            bgr = frame.to_ndarray(format="bgr24")
            cb = _normalize_crop_box(crop_box, bgr.shape[1], bgr.shape[0])
            if cb is not None:
                bgr = np.ascontiguousarray(bgr[cb[1] : cb[3], cb[0] : cb[2]])
            all_bgr.append(bgr)
    finally:
        container.close()

    if not all_bgr:
        return [], src_fps
    if sample_fps is None or sample_fps <= 0.0:
        return all_bgr, src_fps

    step = max(1, int(round(src_fps / float(sample_fps))))
    sampled = all_bgr[::step]
    if len(all_bgr) > 1 and (len(all_bgr) - 1) % step != 0:
        sampled.append(all_bgr[-1])
    return sampled, src_fps


def _has_federal_intramural_agency(agency_raw: str) -> bool:
    low = " ".join(str(agency_raw or "").lower().split())
    return bool(low) and any(tok in low for tok in R89_FEDERAL_INTRAMURAL_AGENCIES)


def _classify_r89_license_and_traps(item: dict[str, Any]) -> tuple[str, list[str], str | None]:
    """
    Evaluate tier classification (`direct_insert_pd_cc0` | `direct_insert_cc_by` | `banned`)
    and catch Fair Use, classic experiment copyright/privacy traps, grant-funded vs federal agency traps,
    publisher carve-outs, and archive.org false-PD uploads.
    """
    issues: list[str] = []
    route_to: str | None = None

    lic_raw = str(item.get("license") or item.get("license_short_name") or "").strip()
    lic_low = re.sub(r"\s+", " ", lic_raw.lower())
    journal_raw = str(item.get("journal") or item.get("publisher") or "").strip()
    journal_low = journal_raw.lower()
    source_url = str(item.get("source_url") or "").strip()
    source_low = source_url.lower()
    agency_raw = str(item.get("creator_agency") or "").strip()
    pub_year = _parse_pub_year(item)

    meta_blob = " ".join(
        str(item.get(k) or "")
        for k in (
            "title",
            "description",
            "source_url",
            "caption",
            "legend",
            "rights_note",
            "rights_and_permissions",
            "license_note",
            "journal",
            "publisher",
            "author",
            "attribution",
            "creator_agency",
            "provenance_note",
            "license",
            "license_short_name",
        )
    ).lower()

    if any(tok in meta_blob for tok in ("fair use", "section 107", "17 u.s.c. 107", "17 usc 107")):
        issues.append("[r89_fair_use_forbidden] Fair Use is permanently banned for automated archival video; route to R67")
        return "banned", issues, "R67"

    hit_banned = [kw for kw in R89_CLASSIC_BANNED_SOURCE_KEYWORDS if kw in meta_blob]
    if hit_banned:
        skinner_federal_ok = (
            "project pigeon" in meta_blob
            and _has_federal_intramural_agency(agency_raw)
            and "skinner foundation" not in meta_blob
            and "harvard film archive" not in meta_blob
        )
        if not skinner_federal_ok:
            issues.append(
                f"[r89_classic_copyright_or_privacy_trap] classic restricted footage matched {hit_banned}; route to R67"
            )
            return "banned", issues, "R67"

    if bool(item.get("contains_minor")) or bool(item.get("contains_identifiable_patient")):
        issues.append("[r89_minor_or_patient_banned] living patients and minors (<18) banned from direct video insert; route to R67")
        return "banned", issues, "R67"

    # Explicit copyleft / non-commercial / no-derivatives rejections
    if any(
        tok in lic_low
        for tok in (
            "by-nc",
            "nc-nd",
            "by-nd",
            "noncommercial",
            "non-commercial",
            "no derivatives",
            "noderivs",
            "by-sa",
            "sharealike",
            "gfdl",
            "all rights reserved",
            "author manuscript",
            "editorial",
        )
    ):
        issues.append(f"[r89_banned_or_sharealike_license] license '{lic_raw}' is not commercial/derivative-safe for R89")
        return "banned", issues, None

    # Federal 17 U.S.C. § 105 vs university grant-funded trap
    claims_105 = any(tok in lic_low or tok in meta_blob for tok in ("17 u.s.c. 105", "17 u.s.c. § 105", "17 usc 105", "usgov", "us gov"))
    if claims_105:
        is_grant_trap = (
            any(tok in meta_blob for tok in ("grant", "r01", "r21", "funded by nih", "funded by darpa", "funded by nsf", "university"))
            and not bool(item.get("is_federal_employee_work"))
            and not _has_federal_intramural_agency(agency_raw)
        )
        if is_grant_trap or not _has_federal_intramural_agency(agency_raw):
            issues.append(
                "[r89_grant_funded_not_federal_work] 17 U.S.C. § 105 requires verified U.S. federal intramural employee agency "
                "(NIH/NIMH/DARPA/NASA/NARA), never grant-funded university clips"
            )
            return "banned", issues, None
        lic_class = "direct_insert_pd_cc0"
    else:
        lic_class = classify_media_license(lic_raw)

    if lic_class == "flow_guide_only_cc_by_sa":
        issues.append(f"[r89_banned_or_sharealike_license] ShareAlike '{lic_raw}' is forbidden for direct video insert")
        return "banned", issues, None
    if lic_class == "banned":
        if "free in pmc" in lic_low or "pmc" in lic_low:
            issues.append("[r89_journal_license_unverified] 'Free in PMC' without verified CC BY / CC0 open-access license is banned")
        else:
            issues.append(f"[r89_banned_or_sharealike_license] unrecognized or non-open license '{lic_raw}'")
        return "banned", issues, None

    # Archive.org / self-tagged "Public Domain" trap guard
    is_cc0 = ("cc0" in lic_low) or ("cc-0" in lic_low)
    is_federal_pd = claims_105 and _has_federal_intramural_agency(agency_raw)
    if lic_class == "direct_insert_pd_cc0" and not is_cc0 and not is_federal_pd:
        is_pre1931_silent = (0 < pub_year <= 1930) and ("sound" not in meta_blob)
        if ("archive.org" in source_low and not is_pre1931_silent) or not is_pre1931_silent:
            issues.append(
                "[r89_false_public_domain_trap] post-1930 'Public Domain' claims require verified CC0 1.0 or 17 U.S.C. § 105 federal intramural provenance"
            )
            return "banned", issues, None

    # Journal-specific strict traps (PNAS CC BY-NC-ND, Science Advances CC BY-NC, PMC OA Subset)
    if any(j_tok in journal_low for j_tok in ("pnas", "science advances", "pmc")) or "free in pmc" in meta_blob:
        if item.get("article_license_verified") is not True:
            issues.append(
                f"[r89_journal_license_unverified] journal/repo '{journal_raw or 'PMC'}' requires explicit article_license_verified=True "
                "confirming per-article CC BY 4.0 / CC0 (not NC/ND/Author Manuscript)"
            )

    # Caption / Rights exclusion audit (Springer Nature / Nature Communications third-party carve-out trap)
    rights_blob = " ".join(
        str(item.get(k) or "")
        for k in ("caption", "legend", "rights_note", "rights_and_permissions", "license_note")
    ).lower()
    if any(pat in rights_blob for pat in R89_CAPTION_EXCLUSION_PATTERNS) or item.get("caption_exclusion_audit_passed") is False:
        issues.append(
            "[r89_caption_carveout_excluded] caption or Rights note excludes clip from CC BY ('excluded from' / 'third party' / 'permission')"
        )
        return "banned", issues, None

    if lic_class == "direct_insert_cc_by":
        if not str(item.get("author") or item.get("attribution") or "").strip():
            issues.append("[r89_cc_by_missing_author] lead author required for CC BY 4.0 § 3(a)")
        if not journal_raw:
            issues.append("[r89_cc_by_missing_journal] journal required for CC BY 4.0 Video credit")
        if not (1990 <= pub_year <= 2035):
            issues.append(f"[r89_cc_by_invalid_year] valid publication_year required, got {item.get('publication_year')!r}")
        if not str(item.get("supplementary_movie_id") or "").strip():
            issues.append("[r89_cc_by_missing_movie_id] supplementary_movie_id required (e.g. 'Supplementary Movie 1')")
        if not (str(item.get("article_url") or "").strip() or str(item.get("doi") or "").strip()):
            issues.append("[r89_cc_by_missing_article_url] article_url or doi required for CC BY attribution")
        lic_uri = str(item.get("license_uri") or "").strip()
        if not lic_uri.startswith("http") or any(x in lic_uri.lower() for x in ("by-nc", "by-nd", "by-sa")):
            issues.append(f"[r89_cc_by_invalid_license_uri] invalid CC-BY license_uri: {lic_uri!r}")

    if not source_url:
        issues.append("[r89_missing_source_url] non-empty primary source_url required")

    if issues:
        return "banned", issues, route_to
    return lic_class, [], None


def audit_archival_video_eligibility(
    item: dict[str, Any],
    *,
    video_path: Path | None = None,
    check_video_pixels: bool = True,
) -> dict[str, Any]:
    """
    Runs all R89 legal, publisher, provenance, 5fps multi-frame YuNet 0-Face, and natural-motion checks
    for a candidate archival or supplementary experiment video entry.
    """
    lic_class, issues, route_to = _classify_r89_license_and_traps(item)
    max_face_score = 0.0
    total_faces_found = 0
    sampled_frames_count = 0
    max_frame_diff = 0.0
    video_sha256 = ""

    pub_year = _parse_pub_year(item)
    face_exempt = (
        bool(item.get("allow_deceased_pre1931_portrait"))
        and lic_class == "direct_insert_pd_cc0"
        and (0 < pub_year <= 1930)
        and not bool(item.get("contains_minor"))
    )

    if video_path is not None:
        if not video_path.is_file():
            issues.append(f"[r89_missing_video] video file missing: {video_path}")
        else:
            video_sha256 = hashlib.sha256(video_path.read_bytes()).hexdigest()
            if check_video_pixels and lic_class != "banned":
                try:
                    sampled, _src_fps = _decode_video_frames_with_fps(
                        video_path,
                        sample_fps=R89_YUNET_SAMPLE_FPS,
                        crop_box=item.get("crop_box"),
                    )
                except Exception as exc:  # noqa: BLE001
                    issues.append(f"[r89_corrupt_video] unable to decode video {video_path}: {exc}")
                    sampled = []
                sampled_frames_count = len(sampled)
                if sampled:
                    prev_gray = cv2.cvtColor(sampled[0], cv2.COLOR_BGR2GRAY).astype(np.float32)
                    for idx_s, fr in enumerate(sampled):
                        if idx_s > 0:
                            cur_gray = cv2.cvtColor(fr, cv2.COLOR_BGR2GRAY).astype(np.float32)
                            d_val = float(np.mean(np.abs(cur_gray - prev_gray)))
                            max_frame_diff = max(max_frame_diff, d_val)
                            prev_gray = cur_gray
                        dets = detect_human_faces_yunet(fr, score_threshold=R89_YUNET_FACE_SCORE_THRESHOLD)
                        if dets:
                            total_faces_found += len(dets)
                            max_face_score = max(max_face_score, max(float(d[4]) for d in dets))
                    if sampled_frames_count < 2 or max_frame_diff < R89_MIN_FRAME_DIFF:
                        issues.append(
                            f"[r89_frozen_video_source] insufficient natural motion inside viewport "
                            f"(max_frame_diff={max_frame_diff:.3f} < {R89_MIN_FRAME_DIFF:.2f})"
                        )
                    if total_faces_found > 0 and not face_exempt:
                        issues.append(
                            f"[r89_privacy_human_face_detected] detected {total_faces_found} human face(s) at "
                            f"{R89_YUNET_SAMPLE_FPS:.0f}fps scan (max_score={max_face_score:.3f} >= {R89_YUNET_FACE_SCORE_THRESHOLD:.2f})"
                        )

    return {
        "eligible": len(issues) == 0 and lic_class in ("direct_insert_pd_cc0", "direct_insert_cc_by"),
        "license_class": lic_class,
        "route_to": route_to,
        "issues": issues,
        "video_sha256": video_sha256,
        "sampled_frames_5fps": sampled_frames_count,
        "yunet_faces_detected": total_faces_found,
        "yunet_max_face_score": round(max_face_score, 4),
        "face_exempt_pre1931_pd": bool(face_exempt),
        "max_frame_diff": round(max_frame_diff, 4),
    }


def _render_r89_credit_pill_rgba(
    text: str,
    *,
    max_w: int,
    max_h: int,
    font_size: int = 19,
) -> Image.Image:
    clean_txt = " ".join(str(text or "").split()).strip()
    probe = ImageDraw.Draw(Image.new("RGBA", (16, 16), (0, 0, 0, 0)))
    chosen_font = _load_inter_or_dejavu_font(font_size)
    label = clean_txt
    for fs in range(font_size, 11, -1):
        chosen_font = _load_inter_or_dejavu_font(fs)
        tb = probe.textbbox((0, 0), label, font=chosen_font)
        if (tb[2] - tb[0] + 24) <= max_w and (tb[3] - tb[1] + 10) <= max_h:
            break
    while len(label) > 12:
        tb = probe.textbbox((0, 0), label, font=chosen_font)
        if (tb[2] - tb[0] + 24) <= max_w:
            break
        label = label[:-4].rstrip() + "..."
    tb = probe.textbbox((0, 0), label, font=chosen_font)
    tw = max(1, tb[2] - tb[0])
    th = max(1, tb[3] - tb[1])
    pw = min(max_w, tw + 24)
    ph = min(max_h, max(24, th + 10))
    pill = Image.new("RGBA", (pw, ph), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)
    draw.rounded_rectangle(
        (0, 0, pw - 1, ph - 1),
        radius=min(16, ph // 2),
        fill=_CARD_BG_RGBA,
        outline=_FRAME_INNER_RGBA,
        width=2,
    )
    tx = (pw - tw) // 2 - tb[0]
    ty = (ph - th) // 2 - tb[1]
    draw.text((tx, ty), label, font=chosen_font, fill=(228, 236, 248, 255))
    return pill


def _build_r89_credit_text(
    *,
    author: str,
    publication_year: int | str,
    license_str: str,
    license_class: str,
    creator_agency: str = "",
) -> str:
    yr = str(publication_year or "").strip()
    if license_class == "direct_insert_cc_by":
        lic_label = normalize_cc_by_label(license_str)
        a_clean = " ".join(str(author or "").split()).strip()
        if a_clean and "et al" not in a_clean.lower():
            a_display = f"{a_clean} et al." if "," in a_clean else a_clean
        else:
            a_display = a_clean or "Authors"
        return f"Source: {a_display} ({yr}) · {lic_label} (cropped, muted)"
    agency = " ".join(str(creator_agency or author or "Public Domain").split()).strip()
    return f"Source: {agency} ({yr}) · Public Domain (muted)"


def _rounded_window_mask(width: int, height: int, radius: int) -> np.ndarray:
    im = Image.new("L", (width, height), 0)
    draw = ImageDraw.Draw(im)
    draw.rounded_rectangle((0, 0, width - 1, height - 1), radius=radius, fill=255)
    return (np.array(im, dtype=np.float32) / 255.0)[:, :, None]


def _draw_rounded_bezel_onto_bgr(
    canvas_bgr: np.ndarray,
    box: tuple[int, int, int, int],
    *,
    radius: int = 20,
    fill_rgba: tuple[int, int, int, int] = (10, 15, 28, 255),
) -> tuple[int, int, int, int]:
    """Draws rounded dark-navy bezel strictly within [x0, y0, x1, y1) and returns inner viewport box."""
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    ov = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    draw = ImageDraw.Draw(ov)
    draw.rounded_rectangle((0, 0, bw - 1, bh - 1), radius=radius, fill=fill_rgba, outline=_FRAME_OUTER_RGBA, width=3)
    draw.rounded_rectangle((3, 3, bw - 4, bh - 4), radius=max(4, radius - 3), outline=_FRAME_INNER_RGBA, width=1)
    _overlay_rgba_onto_bgr(canvas_bgr, np.array(ov), x0, y0)
    inset = 10
    return (x0 + inset, y0 + inset, x1 - inset, y1 - inset)


def _fit_and_paste_rounded_frame(
    canvas_bgr: np.ndarray,
    src_bgr: np.ndarray,
    inner_box: tuple[int, int, int, int],
    *,
    mask_3d: np.ndarray,
    cover: bool = False,
) -> None:
    ix0, iy0, ix1, iy1 = inner_box
    iw, ih = ix1 - ix0, iy1 - iy0
    sh, sw = src_bgr.shape[:2]
    scale = max(iw / float(max(1, sw)), ih / float(max(1, sh))) if cover else min(iw / float(max(1, sw)), ih / float(max(1, sh)))
    rw = max(2, int(round(sw * scale)))
    rh = max(2, int(round(sh * scale)))
    resized = cv2.resize(src_bgr, (rw, rh), interpolation=cv2.INTER_AREA if scale < 1.0 else cv2.INTER_CUBIC)
    patch = np.full((ih, iw, 3), _MATTE_BGR, dtype=np.uint8)
    if cover:
        sx0 = max(0, (rw - iw) // 2)
        sy0 = max(0, (rh - ih) // 2)
        patch[:, :] = resized[sy0 : sy0 + ih, sx0 : sx0 + iw]
    else:
        dx0 = max(0, (iw - rw) // 2)
        dy0 = max(0, (ih - rh) // 2)
        patch[dy0 : dy0 + rh, dx0 : dx0 + rw] = resized[: min(rh, ih), : min(rw, iw)]
    roi = canvas_bgr[iy0:iy1, ix0:ix1].astype(np.float32)
    blended = roi * (1.0 - mask_3d) + patch.astype(np.float32) * mask_3d
    canvas_bgr[iy0:iy1, ix0:ix1] = np.clip(blended, 0, 255).astype(np.uint8)


def _render_a01_porcelain_locator_badge(
    badge_size: int = 200,
    locator_xy_norm: tuple[float, float] = (0.52, 0.36),
    a01_head_path: Path | None = None,
) -> Image.Image:
    """Renders 200x200 matte-white faceless A01 porcelain head locator badge with crimson/cyan target dot."""
    badge = Image.new("RGBA", (badge_size, badge_size), (0, 0, 0, 0))
    draw = ImageDraw.Draw(badge)
    draw.rounded_rectangle(
        (0, 0, badge_size - 1, badge_size - 1),
        radius=24,
        fill=(14, 21, 38, 242),
        outline=_FRAME_INNER_RGBA,
        width=2,
    )
    head_fp = a01_head_path or DEFAULT_A01_HEAD_PATH
    if head_fp.is_file():
        bgr = cv2.imread(str(head_fp), cv2.IMREAD_COLOR)
        if bgr is not None and bgr.size > 0:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB).astype(np.float32)
            bg = np.median(rgb[:20, :20].reshape(-1, 3), axis=0)
            score = np.linalg.norm(rgb - bg[None, None, :], axis=2)
            sil = np.clip((score - 12.0) / 16.0, 0.0, 1.0)
            ys, xs = np.where(sil > 0.25)
            if len(xs) > 0 and len(ys) > 0:
                crop_sil = sil[ys.min() : ys.max() + 1, xs.min() : xs.max() + 1]
                ch, cw = crop_sil.shape
                sc = min((badge_size - 34) / float(cw), (badge_size - 34) / float(ch))
                nw, nh = max(12, int(round(cw * sc))), max(12, int(round(ch * sc)))
                sil_rs = cv2.resize(crop_sil, (nw, nh), interpolation=cv2.INTER_AREA)
                matte_rgba = np.zeros((nh, nw, 4), dtype=np.uint8)
                matte_rgba[:, :, 0] = 232
                matte_rgba[:, :, 1] = 238
                matte_rgba[:, :, 2] = 246
                matte_rgba[:, :, 3] = np.clip(sil_rs * 245.0, 0, 255).astype(np.uint8)
                head_img = Image.fromarray(matte_rgba, mode="RGBA")
                badge.alpha_composite(head_img, ((badge_size - nw) // 2, (badge_size - nh) // 2))
    else:
        draw.ellipse((46, 32, 154, 140), fill=(232, 238, 246, 235))
        draw.rounded_rectangle((74, 128, 126, 168), radius=12, fill=(232, 238, 246, 235))

    lx = max(24, min(badge_size - 24, int(round(float(locator_xy_norm[0]) * badge_size))))
    ly = max(24, min(badge_size - 24, int(round(float(locator_xy_norm[1]) * badge_size))))
    draw.ellipse((lx - 14, ly - 14, lx + 14, ly + 14), outline=(39, 216, 255, 220), width=2)
    draw.ellipse((lx - 7, ly - 7, lx + 7, ly + 7), fill=(230, 43, 30, 255), outline=(255, 255, 255, 235), width=2)
    return badge


def _sample_sequence_frame(frames: list[np.ndarray], out_idx: int, total_out: int) -> np.ndarray:
    if len(frames) == 1:
        return frames[0]
    u = out_idx / float(max(1, total_out - 1))
    src_idx = min(len(frames) - 1, int(round(u * (len(frames) - 1))))
    return frames[src_idx]


def _encode_bgr_frames_to_mp4(frames: list[np.ndarray], out_mp4: Path, *, fps: int = R89_FPS) -> str:
    """Atomically encodes BGR frames into `1080x1920 @ 30fps` `libx264` `yuv420p` with ZERO audio streams."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(out_mp4.parent), prefix=".tmp_r89_", suffix=".mp4")
    os.close(fd)
    tmp_mp4 = Path(tmp_name)
    try:
        container = av.open(str(tmp_mp4), mode="w", format="mp4")
        try:
            stream = container.add_stream("libx264", rate=fps)
            stream.width = R89_WIDTH
            stream.height = R89_HEIGHT
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "18", "preset": "fast"}
            for fr in frames:
                vf = av.VideoFrame.from_ndarray(fr, format="bgr24")
                for pkt in stream.encode(vf):
                    container.mux(pkt)
            for pkt in stream.encode():
                container.mux(pkt)
        finally:
            container.close()
        sha = hashlib.sha256(tmp_mp4.read_bytes()).hexdigest()
        os.replace(str(tmp_mp4), str(out_mp4))
        return sha
    finally:
        if tmp_mp4.exists():
            tmp_mp4.unlink(missing_ok=True)


def render_split_sync_video_clip(
    source_video_path: str | Path,
    brain_video_path: str | Path,
    out_mp4: str | Path,
    *,
    duration_sec: float = 3.0,
    crop_box: Any = None,
    credit_text: str | None = None,
) -> str:
    """
    Render R89 Mode 1 (`Split-Sync Dual-Stage`) strictly inside `R89_SAFE_OUTER_BOX=(80, 288, 908, 1218)`:
      - Top muted real video window: `R89_MODE1_TOP_VIDEO_BOX=(80, 288, 908, 728)`
      - Attribution/sync bridge: `R89_MODE1_CREDIT_BOX=(80, 735, 908, 767)`
      - Synced bottom Ep #31 3D brain stage: `R89_MODE1_BOTTOM_BRAIN_BOX=(80, 774, 908, 1218)`
    """
    src_frames, _ = _decode_video_frames_with_fps(Path(source_video_path), crop_box=crop_box)
    brain_frames, _ = _decode_video_frames_with_fps(Path(brain_video_path))
    if not src_frames or not brain_frames:
        raise ValueError("Source and synced brain video must each decode >= 1 frame")

    n_frames = max(60, int(round(float(duration_sec) * R89_FPS)))
    base_canvas = np.full((R89_HEIGHT, R89_WIDTH, 3), _MATTE_BGR, dtype=np.uint8)
    top_inner = _draw_rounded_bezel_onto_bgr(base_canvas, R89_MODE1_TOP_VIDEO_BOX, radius=18)
    bot_inner = _draw_rounded_bezel_onto_bgr(base_canvas, R89_MODE1_BOTTOM_BRAIN_BOX, radius=18)

    top_mask = _rounded_window_mask(top_inner[2] - top_inner[0], top_inner[3] - top_inner[1], radius=12)
    bot_mask = _rounded_window_mask(bot_inner[2] - bot_inner[0], bot_inner[3] - bot_inner[1], radius=12)

    cx0, cy0, cx1, cy1 = R89_MODE1_CREDIT_BOX
    if credit_text:
        pill = np.array(
            _render_r89_credit_pill_rgba(credit_text, max_w=cx1 - cx0, max_h=cy1 - cy0, font_size=18)
        )
        px = cx0
        py = cy0 + max(0, ((cy1 - cy0) - pill.shape[0]) // 2)
        _overlay_rgba_onto_bgr(base_canvas, pill, px, py)
    else:
        mid_y = (cy0 + cy1) // 2
        cv2.line(base_canvas, (cx0, mid_y), (cx1 - 1, mid_y), (98, 66, 49), 2)

    out_frames: list[np.ndarray] = []
    for fi in range(n_frames):
        fr = base_canvas.copy()
        s_fr = _sample_sequence_frame(src_frames, fi, n_frames)
        b_fr = _sample_sequence_frame(brain_frames, fi, n_frames)
        _fit_and_paste_rounded_frame(fr, s_fr, top_inner, mask_3d=top_mask, cover=False)
        _fit_and_paste_rounded_frame(fr, b_fr, bot_inner, mask_3d=bot_mask, cover=True)
        out_frames.append(fr)

    return _encode_bgr_frames_to_mp4(out_frames, Path(out_mp4))


def render_viewfinder_video_clip(
    source_video_path: str | Path,
    out_mp4: str | Path,
    *,
    duration_sec: float = 3.0,
    crop_box: Any = None,
    credit_text: str | None = None,
    locator_xy_norm: tuple[float, float] = (0.52, 0.36),
    a01_head_path: Path | None = None,
) -> str:
    """
    Render R89 Mode 2 (`Dark-Navy Rounded Viewfinder + Porcelain Locator`) strictly inside `(80, 288, 908, 1218)`:
      - Viewfinder: `R89_MODE2_VIEWFINDER_BOX=(80, 288, 908, 1058)`
      - 200x200 A01 porcelain head badge: `R89_MODE2_LOCATOR_BADGE_BOX=(94, 948, 294, 1148)`
      - Credit pill: `R89_MODE2_CREDIT_BOX=(312, 1084, 896, 1138)`
    """
    src_frames, _ = _decode_video_frames_with_fps(Path(source_video_path), crop_box=crop_box)
    if not src_frames:
        raise ValueError(f"Source video decoded 0 frames: {source_video_path}")

    n_frames = max(60, int(round(float(duration_sec) * R89_FPS)))
    base_canvas = np.full((R89_HEIGHT, R89_WIDTH, 3), _MATTE_BGR, dtype=np.uint8)
    vf_inner = _draw_rounded_bezel_onto_bgr(base_canvas, R89_MODE2_VIEWFINDER_BOX, radius=20)
    vf_mask = _rounded_window_mask(vf_inner[2] - vf_inner[0], vf_inner[3] - vf_inner[1], radius=14)

    bx0, by0, bx1, by1 = R89_MODE2_LOCATOR_BADGE_BOX
    badge_np = np.array(
        _render_a01_porcelain_locator_badge(
            badge_size=min(bx1 - bx0, by1 - by0),
            locator_xy_norm=locator_xy_norm,
            a01_head_path=a01_head_path,
        )
    )
    cx0, cy0, cx1, cy1 = R89_MODE2_CREDIT_BOX
    pill_np: np.ndarray | None = None
    pill_xy = (cx0, cy0)
    if credit_text:
        pill_np = np.array(
            _render_r89_credit_pill_rgba(credit_text, max_w=cx1 - cx0, max_h=cy1 - cy0, font_size=18)
        )
        pill_xy = (cx0, cy0 + max(0, ((cy1 - cy0) - pill_np.shape[0]) // 2))

    out_frames: list[np.ndarray] = []
    for fi in range(n_frames):
        fr = base_canvas.copy()
        s_fr = _sample_sequence_frame(src_frames, fi, n_frames)
        _fit_and_paste_rounded_frame(fr, s_fr, vf_inner, mask_3d=vf_mask, cover=False)
        _overlay_rgba_onto_bgr(fr, badge_np, bx0, by0)
        if pill_np is not None:
            _overlay_rgba_onto_bgr(fr, pill_np, pill_xy[0], pill_xy[1])
        out_frames.append(fr)

    return _encode_bgr_frames_to_mp4(out_frames, Path(out_mp4))


def _load_r88a_counts_and_duration(project_dir: Path | None) -> tuple[int, float]:
    if project_dir is None:
        return 0, 0.0
    r88a_path = project_dir / "03_visuals" / "archival_inserts_manifest.json"
    if not r88a_path.is_file():
        return 0, 0.0
    try:
        doc = json.loads(r88a_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return 0, 0.0
    entries = doc.get("inserts") or doc.get("clips") or doc.get("items") or []
    if not isinstance(entries, list):
        return 0, 0.0
    cnt = sum(1 for e in entries if isinstance(e, dict))
    dur = sum(max(0.0, float(e.get("duration_sec") or 0.0)) for e in entries if isinstance(e, dict))
    return cnt, dur


def validate_combined_archival_budget(
    r88a_count: int,
    r88a_duration_sec: float,
    r89_count: int,
    r89_duration_sec: float,
    *,
    episode_duration_sec: float,
) -> list[str]:
    """Enforces combined R88-A + R89 archival quota: `<= 2` cuts and `<= 10%` of episode runtime."""
    issues: list[str] = []
    tot_cuts = int(r88a_count) + int(r89_count)
    tot_dur = float(r88a_duration_sec) + float(r89_duration_sec)
    if tot_cuts > R89_COMBINED_ARCHIVAL_MAX_CUTS:
        issues.append(
            f"[r89_combined_cut_cap_exceeded] combined R88-A ({r88a_count}) + R89 ({r89_count}) = {tot_cuts} cuts > {R89_COMBINED_ARCHIVAL_MAX_CUTS}"
        )
    max_dur = max(0.0, float(episode_duration_sec) * R89_COMBINED_ARCHIVAL_MAX_DURATION_SHARE)
    if episode_duration_sec > 0.0 and tot_dur > max_dur + 1e-6:
        issues.append(
            f"[r89_combined_share_exceeded] combined R88-A + R89 duration {tot_dur:.3f}s exceeds "
            f"{R89_COMBINED_ARCHIVAL_MAX_DURATION_SHARE * 100:.0f}% budget ({max_dur:.3f}s of {episode_duration_sec:.2f}s)"
        )
    return issues


def validate_archival_videos_manifest(
    manifest_or_dir: str | Path | dict[str, Any],
    *,
    episode_duration_sec: float = 75.0,
    edl: dict[str, Any] | None = None,
    check_faces: bool = True,
    strict_sha256: bool = False,
) -> dict[str, Any]:
    """
    Validates `03_visuals/archival_videos_manifest.json` against R89 legal, privacy, flow-zero,
    `Cut >= 2` / `>= 2.20s`, `0` audio streams, SHA-256 provenance, and combined `R88-A + R89` budget rules.
    """
    doc, manifest_path, visuals_dir, project_dir, explicit_file, load_err = _resolve_manifest_context(manifest_or_dir)
    max_combined_dur = round(max(0.0, float(episode_duration_sec)) * R89_COMBINED_ARCHIVAL_MAX_DURATION_SHARE, 4)
    if load_err is not None:
        return {
            "present": bool(manifest_path and manifest_path.exists()),
            "passed": False,
            "issues": [load_err],
            "video_count": 0,
            "total_video_duration_sec": 0.0,
            "max_combined_duration_sec": max_combined_dur,
            "entries": [],
        }
    if doc is None:
        return {
            "present": False,
            "passed": not explicit_file,
            "issues": ([f"[r89_manifest_missing] {manifest_path}"] if explicit_file else []),
            "video_count": 0,
            "total_video_duration_sec": 0.0,
            "max_combined_duration_sec": max_combined_dur,
            "entries": [],
        }

    issues: list[str] = []
    ep_dur = float(episode_duration_sec)
    _, entries = _extract_entries_key(doc)
    if len(entries) > R89_COMBINED_ARCHIVAL_MAX_CUTS:
        issues.append(f"[r89_too_many_videos] {len(entries)} entries > max {R89_COMBINED_ARCHIVAL_MAX_CUTS}")

    edl_by_clip: dict[int, dict[str, Any]] = {}
    if isinstance(edl, dict):
        for c in edl.get("cuts") or []:
            if isinstance(c, dict) and int(c.get("clip_index") or 0) > 0:
                edl_by_clip[int(c["clip_index"])] = c

    seen_clips: set[int] = set()
    total_r89_dur = 0.0
    validated_entries: list[dict[str, Any]] = []
    lo_d, hi_d = R89_VIDEO_DURATION_RANGE

    for idx, item in enumerate(entries, start=1):
        try:
            clip_num = int(item.get("clip_number") or item.get("clip_index") or 0)
        except (TypeError, ValueError):
            clip_num = 0
        if clip_num < R89_MIN_CUT_INDEX:
            issues.append(
                f"[r89_cut_1_hook_forbidden] entry #{idx}: clip_number={clip_num} < R89_MIN_CUT_INDEX={R89_MIN_CUT_INDEX} "
                "(Cut 1 / 118pt HookTitle forbidden for R89)"
            )
        elif clip_num in seen_clips:
            issues.append(f"[r89_duplicate_clip_number] duplicate clip_number={clip_num}")
        seen_clips.add(clip_num)

        raw_start = item.get("start_sec")
        if raw_start is None and clip_num in edl_by_clip:
            raw_start = edl_by_clip[clip_num].get("start")
        if raw_start is not None:
            try:
                start_val = float(raw_start)
            except (TypeError, ValueError):
                start_val = -1.0
            if start_val < R89_MIN_START_SEC - 1e-6:
                issues.append(
                    f"[r89_start_before_hook_clearance] clip {clip_num}: start_sec={start_val:.2f}s < R89_MIN_START_SEC={R89_MIN_START_SEC:.2f}s"
                )

        mode = str(item.get("mode") or "").strip().lower()
        if mode not in R89_VALID_MODES:
            issues.append(f"[r89_invalid_mode] clip {clip_num}: mode={mode!r} must be one of {sorted(R89_VALID_MODES)}")

        raw_dur = item.get("duration_sec")
        try:
            dur = float(raw_dur) if raw_dur is not None else -1.0
        except (TypeError, ValueError):
            dur = -1.0
        if not (lo_d - 1e-6 <= dur <= hi_d + 1e-6):
            issues.append(f"[r89_duration_out_of_range] clip {clip_num}: duration_sec={raw_dur!r} outside [{lo_d:.1f}, {hi_d:.1f}]s")
        if dur > 0.0:
            total_r89_dur += dur

        try:
            flow_uploads = int(item.get("flow_upload_count") or 0)
        except (TypeError, ValueError):
            flow_uploads = 1
        if flow_uploads != 0 or bool(item.get("uploaded_to_flow")):
            issues.append(f"[r89_flow_upload_forbidden] clip {clip_num}: archival videos must keep flow_upload_count == 0")

        video_path = _resolve_media_path(
            item,
            ("video_path", "source_video_path", "video_rel_path"),
            project_dir=project_dir,
            visuals_dir=visuals_dir,
            manifest_path=manifest_path,
        )
        audit = audit_archival_video_eligibility(item, video_path=video_path, check_video_pixels=check_faces)
        for msg in audit["issues"]:
            issues.append(f"clip {clip_num}: {msg}")

        expected_vsha = str(item.get("video_sha256") or "").strip().lower()
        if expected_vsha and audit["video_sha256"] and audit["video_sha256"] != expected_vsha:
            issues.append(f"[r89_video_sha256_mismatch] clip {clip_num}: source video SHA-256 mismatch")
        elif strict_sha256 and not expected_vsha:
            issues.append(f"[r89_missing_video_sha256] clip {clip_num}: video_sha256 required in strict mode")

        brain_path: Path | None = None
        if mode == "split_sync":
            brain_path = _resolve_media_path(
                item,
                ("brain_video_path", "brain_clip_path", "brain_video_rel_path"),
                project_dir=project_dir,
                visuals_dir=visuals_dir,
                manifest_path=manifest_path,
            )
            if brain_path is None or not brain_path.is_file():
                issues.append(f"[r89_missing_synced_brain_clip] clip {clip_num}: split_sync mode requires brain_video_path")

        if strict_sha256 and visuals_dir is not None:
            exp_rsha = str(item.get("rendered_clip_sha256") or "").strip().lower()
            r_path = _resolve_rendered_clip_path(item, visuals_dir)
            if not _SHA256_HEX_RE.match(exp_rsha) or r_path is None:
                issues.append(f"[r89_missing_rendered_clip] clip {clip_num}: valid rendered_clip_rel_path & sha256 required")
            else:
                act_rsha = hashlib.sha256(r_path.read_bytes()).hexdigest().lower()
                if act_rsha != exp_rsha:
                    issues.append(f"[r89_rendered_clip_sha256_mismatch] clip {clip_num}: rendered mp4 SHA-256 mismatch")
                elif count_mp4_audio_streams(r_path) != 0:
                    issues.append(f"[r89_nonzero_audio_streams] clip {clip_num}: rendered R89 clip must contain 0 audio streams")

        validated_entries.append(
            {
                "clip_number": clip_num,
                "mode": mode,
                "duration_sec": dur,
                "license": str(item.get("license") or ""),
                "license_class": audit["license_class"],
                "author": str(item.get("author") or item.get("attribution") or ""),
                "journal": str(item.get("journal") or ""),
                "publication_year": _parse_pub_year(item),
                "supplementary_movie_id": str(item.get("supplementary_movie_id") or ""),
                "license_uri": str(item.get("license_uri") or ""),
                "article_url": str(item.get("article_url") or ""),
                "doi": str(item.get("doi") or ""),
                "source_url": str(item.get("source_url") or ""),
                "creator_agency": str(item.get("creator_agency") or ""),
                "crop_box": item.get("crop_box"),
                "locator_xy_norm": item.get("locator_xy_norm"),
                "video_path": str(video_path) if video_path is not None else "",
                "brain_video_path": str(brain_path) if brain_path is not None else "",
                "video_sha256": audit["video_sha256"],
                "yunet_faces_detected": audit["yunet_faces_detected"],
                "face_exempt_pre1931_pd": audit["face_exempt_pre1931_pd"],
            }
        )

    r88a_cnt, r88a_dur = _load_r88a_counts_and_duration(project_dir)
    issues.extend(
        validate_combined_archival_budget(
            r88a_cnt,
            r88a_dur,
            len(entries),
            total_r89_dur,
            episode_duration_sec=ep_dur,
        )
    )

    return {
        "present": True,
        "passed": len(issues) == 0,
        "issues": issues,
        "video_count": len(entries),
        "total_video_duration_sec": round(total_r89_dur, 4),
        "r88a_count": r88a_cnt,
        "r88a_duration_sec": round(r88a_dur, 4),
        "max_combined_duration_sec": max_combined_dur,
        "entries": validated_entries,
    }


def render_archival_video_clips(
    project_dir: str | Path,
    *,
    episode_duration_sec: float = 75.0,
) -> dict[str, Any]:
    """
    Validates `03_visuals/archival_videos_manifest.json`, renders `1080x1920 @ 30fps` muted clips
    into `03_visuals/archival_video_clips/clip_<NN>.mp4`, and atomically locks SHA-256 receipts.
    """
    p_dir = Path(project_dir)
    val = validate_archival_videos_manifest(p_dir, episode_duration_sec=episode_duration_sec, check_faces=True)
    if not val["present"]:
        raise ValueError(f"Missing archival videos manifest at {p_dir / ARCHIVAL_VIDEOS_MANIFEST_REL}")
    if not val["passed"]:
        raise ValueError("Archival videos manifest validation failed: " + "; ".join(val["issues"]))

    manifest_path = p_dir / ARCHIVAL_VIDEOS_MANIFEST_REL
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries_key, raw_entries = _extract_entries_key(doc)
    clips_dir = p_dir / "03_visuals" / ARCHIVAL_VIDEO_CLIPS_DIRNAME
    clips_dir.mkdir(parents=True, exist_ok=True)

    rendered_clips: list[dict[str, Any]] = []
    updated_entries: list[dict[str, Any]] = []
    for raw_item, v_item in zip(raw_entries, val["entries"]):
        clip_num = int(v_item["clip_number"])
        mode = str(v_item["mode"])
        dur = float(v_item["duration_sec"])
        lic_class = str(v_item["license_class"])
        credit_txt = (
            _build_r89_credit_text(
                author=v_item["author"],
                publication_year=v_item["publication_year"],
                license_str=v_item["license"],
                license_class=lic_class,
                creator_agency=v_item["creator_agency"],
            )
            if lic_class == "direct_insert_cc_by"
            else None
        )
        out_mp4 = clips_dir / f"clip_{clip_num:02d}.mp4"
        if mode == "split_sync":
            clip_sha = render_split_sync_video_clip(
                v_item["video_path"],
                v_item["brain_video_path"],
                out_mp4,
                duration_sec=dur,
                crop_box=v_item.get("crop_box"),
                credit_text=credit_txt,
            )
        else:
            raw_loc = v_item.get("locator_xy_norm")
            loc_xy = (
                (float(raw_loc[0]), float(raw_loc[1]))
                if isinstance(raw_loc, (list, tuple)) and len(raw_loc) == 2
                else (0.52, 0.36)
            )
            clip_sha = render_viewfinder_video_clip(
                v_item["video_path"],
                out_mp4,
                duration_sec=dur,
                crop_box=v_item.get("crop_box"),
                credit_text=credit_txt,
                locator_xy_norm=loc_xy,
            )

        rel_path = f"03_visuals/{ARCHIVAL_VIDEO_CLIPS_DIRNAME}/clip_{clip_num:02d}.mp4"
        n_audio = count_mp4_audio_streams(out_mp4)
        new_item = {
            **raw_item,
            "clip_number": clip_num,
            "mode": mode,
            "license_class": lic_class,
            "video_sha256": v_item["video_sha256"],
            "flow_upload_count": 0,
            "uploaded_to_flow": False,
            "audio_stream_count": n_audio,
            "rendered_clip_rel_path": rel_path,
            "rendered_clip_sha256": clip_sha,
            "fps": R89_FPS,
            "resolution": [R89_WIDTH, R89_HEIGHT],
        }
        updated_entries.append(new_item)
        rendered_clips.append(
            {
                "clip_number": clip_num,
                "mode": mode,
                "path": str(out_mp4),
                "rel_path": rel_path,
                "sha256": clip_sha,
                "audio_stream_count": n_audio,
                "license_class": lic_class,
                "duration_sec": dur,
            }
        )

    doc[entries_key] = updated_entries
    _atomic_write_json(manifest_path, doc)
    return {
        "passed": True,
        "manifest_path": str(manifest_path),
        "rendered_clips": rendered_clips,
    }


def load_verified_archival_video_clip_map(visuals_dir: Path) -> dict[int, dict[str, Any]]:
    """
    Loads verified R89 archival video clips (`{clip_number: entry}`) ONLY when legal/provenance audit passes,
    `clip_number >= R89_MIN_CUT_INDEX`, `flow_upload_count == 0`, `audio_stream_count == 0`,
    and `rendered_clip_sha256` matches disk bytes.
    """
    v_dir = Path(visuals_dir)
    mf_path = v_dir / "archival_videos_manifest.json"
    if not mf_path.is_file():
        return {}
    try:
        doc = json.loads(mf_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(doc, dict):
        return {}

    _, entries = _extract_entries_key(doc)
    if len(entries) > R89_COMBINED_ARCHIVAL_MAX_CUTS:
        return {}

    verified: dict[int, dict[str, Any]] = {}
    for item in entries:
        try:
            clip_num = int(item.get("clip_number") or item.get("clip_index") or 0)
        except (TypeError, ValueError):
            continue
        if clip_num < R89_MIN_CUT_INDEX:
            continue
        mode = str(item.get("mode") or "").strip().lower()
        if mode not in R89_VALID_MODES:
            continue
        try:
            flow_uploads = int(item.get("flow_upload_count") or 0)
        except (TypeError, ValueError):
            continue
        if flow_uploads != 0 or bool(item.get("uploaded_to_flow")):
            continue

        lic_class, legal_issues, _ = _classify_r89_license_and_traps(item)
        if legal_issues or not lic_class.startswith("direct_insert_"):
            continue

        exp_sha = str(item.get("rendered_clip_sha256") or "").strip().lower()
        if not _SHA256_HEX_RE.match(exp_sha):
            continue
        clip_path = _resolve_rendered_clip_path(item, v_dir)
        if clip_path is None or not clip_path.is_file():
            continue
        actual_sha = hashlib.sha256(clip_path.read_bytes()).hexdigest().lower()
        if actual_sha != exp_sha:
            continue
        if count_mp4_audio_streams(clip_path) != 0:
            continue

        verified[clip_num] = {
            **item,
            "clip_number": clip_num,
            "mode": mode,
            "license_class": lic_class,
            "clip_path": clip_path,
            "resolved_clip_path": str(clip_path),
        }
    return verified


__all__ = [
    "ARCHIVAL_VIDEOS_MANIFEST_REL",
    "ARCHIVAL_VIDEO_CLIPS_DIRNAME",
    "DEFAULT_A01_HEAD_PATH",
    "R89_FPS",
    "R89_HEIGHT",
    "R89_VALID_MODES",
    "R89_WIDTH",
    "audit_archival_video_eligibility",
    "count_mp4_audio_streams",
    "load_verified_archival_video_clip_map",
    "render_archival_video_clips",
    "render_split_sync_video_clip",
    "render_viewfinder_video_clip",
    "validate_archival_videos_manifest",
    "validate_combined_archival_budget",
]
