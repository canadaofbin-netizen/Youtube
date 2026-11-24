"""
ALL ABOUT BRAIN — R88-A Legal Archival Photo Insert Engine (`Gear 4 FFmpeg/PyAV` Only, `0` Flow Uploads).

Enforces strict copyright, privacy, and temporal budget rules for direct-insert archival photographs:
  - License gate via `classify_media_license`: ONLY `"direct_insert_pd_cc0"` and `"direct_insert_cc_by"` are permitted.
    ShareAlike (`cc-by-sa`, `gfdl`, `wikimedia_open`, `open_license`) is strictly rejected here (R72-R Flow guide only).
  - Privacy gate (`YuNet 0-Face`): runs `detect_human_faces_yunet(bgr, score_threshold=0.42)` (including B&W Haar fallback)
    and rejects any detected human face unless `allow_deceased_pre1931_portrait=True`, `license_class == "direct_insert_pd_cc0"`,
    and `publication_year < 1931`.
  - Episode budget: max `R88A_MAX_INSERTS_PER_EPISODE` (`2`) inserts, each `2.0–4.0s`, total duration `<= 8%` of episode.
  - Gear 4 rendering (`1080x1920 @ 30fps`, `libx264`, `yuv420p`) via PyAV with smooth `1.00x -> 1.08x` Ken Burns zoom over
    a `#080C16` museum matte (`0` Flow uploads) + unobtrusive `CC-BY` credit pill above `MarginV=510` subtitles.
  - SHA-256 tamper verification on both raw source images and rendered `.mp4` clips.
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
from PIL import Image, ImageDraw, ImageFont

from pipeline.config import WORKSPACE_ROOT
from pipeline.real_world_refs import classify_media_license
from pipeline.archival_media import detect_human_faces_yunet

ARCHIVAL_MANIFEST_REL = "03_visuals/archival_inserts_manifest.json"
ARCHIVAL_CLIPS_DIRNAME = "archival_insert_clips"
R88A_MAX_INSERTS_PER_EPISODE = 2
R88A_CLIP_DURATION_RANGE: tuple[float, float] = (2.0, 4.0)
R88A_MAX_EPISODE_DURATION_SHARE = 0.08
R88A_FPS = 30
R88A_WIDTH = 1080
R88A_HEIGHT = 1920
_MATTE_BGR: tuple[int, int, int] = (22, 12, 8)  # #080C16
_FRAME_OUTER_BGR: tuple[int, int, int] = (59, 38, 28)  # #1C263B
_FRAME_INNER_BGR: tuple[int, int, int] = (98, 66, 49)  # #314262
_INTER_FONT_PATH = Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel" / "assets" / "fonts" / "Inter-Variable.ttf"
_DEJAVU_FONT_CANDIDATES: tuple[Path, ...] = (
    Path("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf"),
    Path("/usr/share/fonts/TTF/DejaVuSans.ttf"),
)
_SHA256_HEX_RE = re.compile(r"^[0-9a-f]{64}$")


def normalize_cc_by_label(raw_license: str) -> str:
    """Normalizes a pure CC-BY license string into a clean viewer-facing label such as `CC BY 4.0`."""
    raw = re.sub(r"\s+", " ", str(raw_license or "").strip())
    m_ver = re.search(r"\b(1\.0|2\.0|2\.5|3\.0|4\.0)\b", raw)
    return f"CC BY {m_ver.group(1)}" if m_ver else "CC BY"


def _atomic_write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(dir=str(path.parent), prefix=".tmp_r88a_", suffix=".json")
    os.close(fd)
    tmp_p = Path(tmp_name)
    try:
        tmp_p.write_text(json.dumps(payload, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        os.replace(str(tmp_p), str(path))
    finally:
        if tmp_p.exists():
            tmp_p.unlink(missing_ok=True)


def _extract_entries_key(doc: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    for key in ("inserts", "clips", "items"):
        val = doc.get(key)
        if isinstance(val, list):
            return key, [x for x in val if isinstance(x, dict)]
    return "inserts", []


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
            return None, manifest_path, v_dir, p_dir, True, f"[r88a_manifest_missing] {manifest_path}"
        try:
            doc = json.loads(manifest_path.read_text(encoding="utf-8"))
        except Exception as exc:  # noqa: BLE001
            return None, manifest_path, v_dir, p_dir, True, f"[r88a_manifest_corrupt] {manifest_path}: {exc}"
        if not isinstance(doc, dict):
            return None, manifest_path, v_dir, p_dir, True, f"[r88a_manifest_invalid] {manifest_path}: expected JSON object"
        return doc, manifest_path, v_dir, p_dir, True, None

    p_dir = p
    v_dir = p_dir / "03_visuals"
    manifest_path = p_dir / ARCHIVAL_MANIFEST_REL
    if not manifest_path.is_file():
        return None, manifest_path, v_dir, p_dir, False, None
    try:
        doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    except Exception as exc:  # noqa: BLE001
        return None, manifest_path, v_dir, p_dir, False, f"[r88a_manifest_corrupt] {manifest_path}: {exc}"
    if not isinstance(doc, dict):
        return None, manifest_path, v_dir, p_dir, False, f"[r88a_manifest_invalid] {manifest_path}: expected JSON object"
    return doc, manifest_path, v_dir, p_dir, False, None


def _resolve_source_image_path(
    item: dict[str, Any],
    *,
    project_dir: Path | None,
    visuals_dir: Path | None,
    manifest_path: Path | None,
) -> Path | None:
    raw_img = ""
    for k in ("image_path", "source_image_path", "image_rel_path", "raw_image_path"):
        v = str(item.get(k) or "").strip()
        if v:
            raw_img = v
            break
    if not raw_img:
        return None
    rp = Path(raw_img)
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


def _resolve_rendered_clip_path(
    item: dict[str, Any],
    visuals_dir: Path,
    *,
    clip_num: int,
) -> Path | None:
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


def _parse_pub_year(item: dict[str, Any]) -> int:
    raw = item.get("publication_year")
    if raw is None or raw == "":
        return 9999
    try:
        return int(raw)
    except (TypeError, ValueError):
        return 9999


def validate_archival_inserts_manifest(
    manifest_or_dir: str | Path | dict[str, Any],
    *,
    episode_duration_sec: float = 75.0,
    check_faces: bool = True,
    strict_sha256: bool = False,
) -> dict[str, Any]:
    """
    Validates `03_visuals/archival_inserts_manifest.json` against R88-A license, flow-zero, duration,
    SHA-256 provenance, and YuNet `0-Face` privacy rules.
    """
    doc, manifest_path, visuals_dir, project_dir, explicit_file, load_err = _resolve_manifest_context(manifest_or_dir)
    if load_err is not None:
        return {
            "present": bool(manifest_path and manifest_path.exists()),
            "passed": False,
            "issues": [load_err],
            "insert_count": 0,
            "total_insert_duration_sec": 0.0,
            "max_allowed_duration_sec": round(max(0.0, float(episode_duration_sec)) * R88A_MAX_EPISODE_DURATION_SHARE, 4),
            "episode_duration_sec": float(episode_duration_sec),
            "entries": [],
        }
    if doc is None:
        return {
            "present": False,
            "passed": not explicit_file,
            "issues": ([f"[r88a_manifest_missing] {manifest_path}"] if explicit_file else []),
            "insert_count": 0,
            "total_insert_duration_sec": 0.0,
            "max_allowed_duration_sec": round(max(0.0, float(episode_duration_sec)) * R88A_MAX_EPISODE_DURATION_SHARE, 4),
            "episode_duration_sec": float(episode_duration_sec),
            "entries": [],
        }

    issues: list[str] = []
    ep_dur = float(episode_duration_sec)
    if ep_dur <= 0.0:
        issues.append(f"[r88a_invalid_episode_duration] episode_duration_sec must be > 0, got {ep_dur}")
    max_total_dur = max(0.0, ep_dur * R88A_MAX_EPISODE_DURATION_SHARE)

    _, entries = _extract_entries_key(doc)
    if len(entries) > R88A_MAX_INSERTS_PER_EPISODE:
        issues.append(
            f"[r88a_too_many_inserts] {len(entries)} inserts exceeds R88A_MAX_INSERTS_PER_EPISODE={R88A_MAX_INSERTS_PER_EPISODE}"
        )

    seen_clips: set[int] = set()
    total_dur = 0.0
    validated_entries: list[dict[str, Any]] = []

    for idx, item in enumerate(entries, start=1):
        try:
            clip_num = int(item.get("clip_number") or item.get("clip_index") or 0)
        except (TypeError, ValueError):
            clip_num = 0
        if clip_num < 1:
            issues.append(f"[r88a_invalid_clip_number] entry #{idx}: clip_number must be >= 1")
        elif clip_num in seen_clips:
            issues.append(f"[r88a_duplicate_clip_number] duplicate clip_number={clip_num}")
        seen_clips.add(clip_num)

        raw_dur = item.get("duration_sec")
        try:
            dur = float(raw_dur) if raw_dur is not None else -1.0
        except (TypeError, ValueError):
            dur = -1.0
        lo_d, hi_d = R88A_CLIP_DURATION_RANGE
        if not (lo_d - 1e-6 <= dur <= hi_d + 1e-6):
            issues.append(
                f"[r88a_duration_out_of_range] clip {clip_num}: duration_sec={raw_dur!r} outside [{lo_d:.1f}, {hi_d:.1f}]s"
            )
        if dur > 0.0:
            total_dur += dur

        lic_raw = str(item.get("license") or item.get("license_short_name") or "").strip()
        lic_class = classify_media_license(lic_raw)
        if lic_class == "flow_guide_only_cc_by_sa":
            issues.append(
                f"[r88a_copyleft_sharealike_forbidden] clip {clip_num}: license '{lic_raw}' is ShareAlike "
                "(flow_guide_only_cc_by_sa — allowed ONLY for R72-R Flow guide, never direct R88-A insert)"
            )
        elif lic_class == "banned":
            issues.append(f"[r88a_banned_license] clip {clip_num}: license '{lic_raw}' is banned for archival insert")

        source_url = str(item.get("source_url") or "").strip()
        if not source_url:
            issues.append(f"[r88a_missing_source_url] clip {clip_num}: non-empty source_url required")

        try:
            flow_uploads = int(item.get("flow_upload_count") or 0)
        except (TypeError, ValueError):
            flow_uploads = 1
        uploaded_to_flow = bool(item.get("uploaded_to_flow"))
        if flow_uploads != 0 or uploaded_to_flow:
            issues.append(
                f"[r88a_flow_upload_forbidden] clip {clip_num}: archival inserts must never touch Google Flow "
                f"(flow_upload_count={flow_uploads}, uploaded_to_flow={uploaded_to_flow})"
            )

        author = str(item.get("author") or item.get("attribution") or "").strip()
        license_uri = str(item.get("license_uri") or "").strip()
        if lic_class == "direct_insert_cc_by":
            if not author:
                issues.append(f"[r88a_cc_by_missing_author] clip {clip_num}: author required for direct_insert_cc_by")
            if not license_uri:
                issues.append(f"[r88a_cc_by_missing_license_uri] clip {clip_num}: license_uri required for direct_insert_cc_by")

        img_path = _resolve_source_image_path(
            item,
            project_dir=project_dir,
            visuals_dir=visuals_dir,
            manifest_path=manifest_path,
        )
        computed_img_sha = ""
        bgr: np.ndarray | None = None
        if img_path is None or not img_path.is_file():
            issues.append(f"[r88a_missing_image] clip {clip_num}: source image file missing ({img_path})")
        else:
            computed_img_sha = hashlib.sha256(img_path.read_bytes()).hexdigest()
            expected_sha = str(item.get("image_sha256") or "").strip().lower()
            if expected_sha:
                if computed_img_sha != expected_sha:
                    issues.append(
                        f"[r88a_image_sha256_mismatch] clip {clip_num}: image_sha256 mismatch "
                        f"(expected={expected_sha[:12]}..., actual={computed_img_sha[:12]}...)"
                    )
            elif strict_sha256:
                issues.append(f"[r88a_missing_image_sha256] clip {clip_num}: image_sha256 required in strict mode")

            bgr = cv2.imread(str(img_path))
            if bgr is None or bgr.size == 0:
                issues.append(f"[r88a_corrupt_image] clip {clip_num}: unable to decode image {img_path}")
                bgr = None

        allow_pre1931 = bool(item.get("allow_deceased_pre1931_portrait"))
        pub_year = _parse_pub_year(item)
        face_exempt = allow_pre1931 and (lic_class == "direct_insert_pd_cc0") and (0 < pub_year < 1931)
        faces: list[tuple[int, int, int, int, float]] = []
        if check_faces and bgr is not None:
            faces = detect_human_faces_yunet(bgr, score_threshold=0.42)
            if faces and not face_exempt:
                issues.append(
                    f"[r88a_privacy_human_face_detected] clip {clip_num}: detected {len(faces)} human face(s) in archival photo "
                    f"(requires allow_deceased_pre1931_portrait=True + direct_insert_pd_cc0 + publication_year < 1931)"
                )

        validated_entries.append(
            {
                "clip_number": clip_num,
                "duration_sec": dur,
                "license": lic_raw,
                "license_class": lic_class,
                "source_url": source_url,
                "author": author,
                "license_uri": license_uri,
                "image_path": str(img_path) if img_path is not None else "",
                "image_sha256": computed_img_sha,
                "faces_detected": len(faces),
                "face_exempt_pre1931_pd": bool(face_exempt),
            }
        )

    if ep_dur > 0.0 and total_dur > max_total_dur + 1e-6:
        issues.append(
            f"[r88a_episode_share_exceeded] total archival insert duration {total_dur:.3f}s exceeds "
            f"{R88A_MAX_EPISODE_DURATION_SHARE * 100:.0f}% budget ({max_total_dur:.3f}s of {ep_dur:.2f}s)"
        )

    return {
        "present": True,
        "passed": len(issues) == 0,
        "issues": issues,
        "insert_count": len(entries),
        "total_insert_duration_sec": round(total_dur, 4),
        "max_allowed_duration_sec": round(max_total_dur, 4),
        "episode_duration_sec": ep_dur,
        "entries": validated_entries,
    }


def _load_inter_or_dejavu_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = [_INTER_FONT_PATH, *_DEJAVU_FONT_CANDIDATES]
    for fp in candidates:
        if fp.is_file():
            try:
                font = ImageFont.truetype(str(fp), size=max(12, int(size)))
                if fp.name == "Inter-Variable.ttf":
                    try:
                        font.set_variation_by_axes([600])
                    except Exception:  # noqa: BLE001
                        pass
                return font
            except Exception:  # noqa: BLE001
                continue
    return ImageFont.load_default()


def _render_cc_by_credit_pill_rgba(author: str, license_str: str) -> Image.Image:
    """
    Renders a crisp `Source: <Author> · CC BY ...` pill cleanly within `y = 1150..1200` (above `MarginV=510`
    subtitles and safely clear of top `118pt HookTitle` and Shorts right action rail).
    """
    lic_label = normalize_cc_by_label(license_str)
    author_clean = " ".join(str(author or "").split()).strip()
    font = _load_inter_or_dejavu_font(22)
    max_text_w = 780
    probe = ImageDraw.Draw(Image.new("RGBA", (16, 16), (0, 0, 0, 0)))

    def _fit_text(a_txt: str) -> str:
        return f"Source: {a_txt} · {lic_label}"

    label = _fit_text(author_clean)
    while len(author_clean) > 8:
        tb = probe.textbbox((0, 0), label, font=font)
        if (tb[2] - tb[0]) <= max_text_w:
            break
        author_clean = author_clean[:-4].rstrip() + "..."
        label = _fit_text(author_clean)

    tb = probe.textbbox((0, 0), label, font=font)
    tw = max(1, tb[2] - tb[0])
    th = max(1, tb[3] - tb[1])
    pad_x = 18
    pad_y = 10
    pill_w = min(835, tw + pad_x * 2)
    pill_h = max(40, th + pad_y * 2)
    pill = Image.new("RGBA", (pill_w, pill_h), (0, 0, 0, 0))
    draw = ImageDraw.Draw(pill)
    draw.rounded_rectangle(
        (0, 0, pill_w - 1, pill_h - 1),
        radius=pill_h // 2,
        fill=(18, 25, 42, 224),
        outline=(74, 96, 134, 230),
        width=2,
    )
    tx = pad_x - tb[0]
    ty = (pill_h - th) // 2 - tb[1]
    draw.text((tx, ty), label, font=font, fill=(228, 234, 245, 255))
    return pill


def _fit_museum_rect(src_w: int, src_h: int) -> tuple[int, int, int, int]:
    """Fits source photo inside clean `1080x1920` museum matte viewport `[60..1020, 220..1120]`."""
    max_w, max_h = 960, 880
    scale = min(max_w / float(max(1, src_w)), max_h / float(max(1, src_h)))
    vw = max(120, (int(round(src_w * scale)) // 2) * 2)
    vh = max(120, (int(round(src_h * scale)) // 2) * 2)
    vw = min(max_w, vw)
    vh = min(max_h, vh)
    vx = (R88A_WIDTH - vw) // 2
    vy = max(210, min(1124 - vh, 670 - vh // 2))
    return vx, vy, vw, vh


def _overlay_rgba_onto_bgr(dst_bgr: np.ndarray, overlay_rgba: np.ndarray, x: int, y: int) -> None:
    oh, ow = overlay_rgba.shape[:2]
    dh, dw = dst_bgr.shape[:2]
    if x >= dw or y >= dh or x + ow <= 0 or y + oh <= 0:
        return
    x0 = max(0, x)
    y0 = max(0, y)
    x1 = min(dw, x + ow)
    y1 = min(dh, y + oh)
    ox0 = x0 - x
    oy0 = y0 - y
    sub_ov = overlay_rgba[oy0 : oy0 + (y1 - y0), ox0 : ox0 + (x1 - x0)]
    alpha = (sub_ov[:, :, 3:4].astype(np.float32)) / 255.0
    ov_bgr = sub_ov[:, :, [2, 1, 0]].astype(np.float32)
    dst_slice = dst_bgr[y0:y1, x0:x1].astype(np.float32)
    dst_bgr[y0:y1, x0:x1] = np.clip(dst_slice * (1.0 - alpha) + ov_bgr * alpha, 0, 255).astype(np.uint8)


def _render_ken_burns_archival_mp4(
    src_bgr: np.ndarray,
    out_mp4: Path,
    *,
    duration_sec: float,
    credit_pill_rgba: Image.Image | None,
) -> str:
    """Renders a `1080x1920 @ 30fps` `libx264` `yuv420p` Ken Burns (`1.00x -> 1.08x`) archival insert atomically."""
    out_mp4.parent.mkdir(parents=True, exist_ok=True)
    sh, sw = src_bgr.shape[:2]
    vx, vy, vw, vh = _fit_museum_rect(sw, sh)
    base_scale = max(vw / float(max(1, sw)), vh / float(max(1, sh)))
    n_frames = max(60, int(round(float(duration_sec) * R88A_FPS)))

    pill_np: np.ndarray | None = None
    pill_x = 72
    pill_y = 1152
    if credit_pill_rgba is not None:
        pill_np = np.array(credit_pill_rgba)
        pw = pill_np.shape[1]
        pill_x = max(72, min(912 - pw, vx))
        pill_y = max(vy + vh + 24, 1152)
        pill_y = min(1176, pill_y)

    base_canvas = np.full((R88A_HEIGHT, R88A_WIDTH, 3), _MATTE_BGR, dtype=np.uint8)
    cv2.rectangle(
        base_canvas,
        (max(0, vx - 3), max(0, vy - 3)),
        (min(R88A_WIDTH - 1, vx + vw + 2), min(R88A_HEIGHT - 1, vy + vh + 2)),
        _FRAME_OUTER_BGR,
        2,
    )
    cv2.rectangle(
        base_canvas,
        (max(0, vx - 1), max(0, vy - 1)),
        (min(R88A_WIDTH - 1, vx + vw), min(R88A_HEIGHT - 1, vy + vh)),
        _FRAME_INNER_BGR,
        1,
    )
    if pill_np is not None:
        _overlay_rgba_onto_bgr(base_canvas, pill_np, pill_x, pill_y)

    fd, tmp_name = tempfile.mkstemp(dir=str(out_mp4.parent), prefix=".tmp_r88a_", suffix=".mp4")
    os.close(fd)
    tmp_mp4 = Path(tmp_name)
    try:
        container = av.open(str(tmp_mp4), mode="w", format="mp4")
        try:
            stream = container.add_stream("libx264", rate=R88A_FPS)
            stream.width = R88A_WIDTH
            stream.height = R88A_HEIGHT
            stream.pix_fmt = "yuv420p"
            stream.options = {"crf": "18", "preset": "fast"}

            cx = sw * 0.5
            cy = sh * 0.5
            for fi in range(n_frames):
                t = fi / float(max(1, n_frames - 1))
                zoom = 1.0 + 0.08 * t
                eff_scale = base_scale * zoom
                cw = vw / eff_scale
                ch = vh / eff_scale
                x0 = max(0.0, cx - cw * 0.5)
                y0 = max(0.0, cy - ch * 0.5)
                mat = np.array(
                    [[eff_scale, 0.0, -x0 * eff_scale], [0.0, eff_scale, -y0 * eff_scale]],
                    dtype=np.float32,
                )
                patch = cv2.warpAffine(
                    src_bgr,
                    mat,
                    (vw, vh),
                    flags=cv2.INTER_CUBIC,
                    borderMode=cv2.BORDER_REFLECT_101,
                )
                frame = base_canvas.copy()
                frame[vy : vy + vh, vx : vx + vw] = patch
                vf = av.VideoFrame.from_ndarray(frame, format="bgr24")
                for pkt in stream.encode(vf):
                    container.mux(pkt)
            for pkt in stream.encode():
                container.mux(pkt)
        finally:
            container.close()

        clip_sha256 = hashlib.sha256(tmp_mp4.read_bytes()).hexdigest()
        os.replace(str(tmp_mp4), str(out_mp4))
        return clip_sha256
    finally:
        if tmp_mp4.exists():
            tmp_mp4.unlink(missing_ok=True)


def render_archival_insert_clips(
    project_dir: str | Path,
    *,
    episode_duration_sec: float = 75.0,
) -> dict[str, Any]:
    """
    Validates `03_visuals/archival_inserts_manifest.json`, renders `1080x1920 @ 30fps` Ken Burns clips
    into `03_visuals/archival_insert_clips/clip_<clip_number:02d>.mp4`, burns CC-BY credit pills, and
    atomically updates `rendered_clip_rel_path` & `rendered_clip_sha256` on disk.
    """
    p_dir = Path(project_dir)
    val = validate_archival_inserts_manifest(p_dir, episode_duration_sec=episode_duration_sec, check_faces=True)
    if not val["present"]:
        raise ValueError(f"Missing archival inserts manifest at {p_dir / ARCHIVAL_MANIFEST_REL}")
    if not val["passed"]:
        raise ValueError("Archival inserts manifest validation failed: " + "; ".join(val["issues"]))

    manifest_path = p_dir / ARCHIVAL_MANIFEST_REL
    doc = json.loads(manifest_path.read_text(encoding="utf-8"))
    entries_key, raw_entries = _extract_entries_key(doc)
    clips_dir = p_dir / "03_visuals" / ARCHIVAL_CLIPS_DIRNAME
    clips_dir.mkdir(parents=True, exist_ok=True)

    rendered_clips: list[dict[str, Any]] = []
    updated_entries: list[dict[str, Any]] = []
    for raw_item, v_item in zip(raw_entries, val["entries"]):
        clip_num = int(v_item["clip_number"])
        dur = float(v_item["duration_sec"])
        lic_class = str(v_item["license_class"])
        img_path = Path(v_item["image_path"])
        src_bgr = cv2.imread(str(img_path))
        if src_bgr is None or src_bgr.size == 0:
            raise ValueError(f"Failed to decode archival source image: {img_path}")

        pill_rgba: Image.Image | None = None
        if lic_class == "direct_insert_cc_by":
            pill_rgba = _render_cc_by_credit_pill_rgba(v_item["author"], v_item["license"])

        out_mp4 = clips_dir / f"clip_{clip_num:02d}.mp4"
        clip_sha256 = _render_ken_burns_archival_mp4(
            src_bgr,
            out_mp4,
            duration_sec=dur,
            credit_pill_rgba=pill_rgba,
        )
        rel_path = f"03_visuals/{ARCHIVAL_CLIPS_DIRNAME}/clip_{clip_num:02d}.mp4"

        new_item = {
            **raw_item,
            "clip_number": clip_num,
            "license_class": lic_class,
            "image_sha256": v_item["image_sha256"],
            "flow_upload_count": 0,
            "uploaded_to_flow": False,
            "rendered_clip_rel_path": rel_path,
            "rendered_clip_sha256": clip_sha256,
            "fps": R88A_FPS,
            "resolution": [R88A_WIDTH, R88A_HEIGHT],
        }
        updated_entries.append(new_item)
        rendered_clips.append(
            {
                "clip_number": clip_num,
                "path": str(out_mp4),
                "rel_path": rel_path,
                "sha256": clip_sha256,
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


def load_verified_archival_insert_clip_map(visuals_dir: Path) -> dict[int, dict[str, Any]]:
    """
    Loads verified archival insert clips (`{clip_number: entry}`) ONLY when:
      - `classify_media_license` returns `"direct_insert_pd_cc0"` or `"direct_insert_cc_by"`;
      - `flow_upload_count == 0` and not `uploaded_to_flow`, with valid provenance fields;
      - `rendered_clip_sha256` matches the `.mp4` bytes on disk byte-for-byte.
    """
    v_dir = Path(visuals_dir)
    mf_path = v_dir / "archival_inserts_manifest.json"
    if not mf_path.is_file():
        return {}
    try:
        doc = json.loads(mf_path.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001
        return {}
    if not isinstance(doc, dict):
        return {}

    _, entries = _extract_entries_key(doc)
    if len(entries) > R88A_MAX_INSERTS_PER_EPISODE:
        return {}

    verified: dict[int, dict[str, Any]] = {}
    for item in entries:
        try:
            clip_num = int(item.get("clip_number") or item.get("clip_index") or 0)
        except (TypeError, ValueError):
            continue
        if clip_num < 1:
            continue
        try:
            flow_uploads = int(item.get("flow_upload_count") or 0)
        except (TypeError, ValueError):
            continue
        if flow_uploads != 0 or bool(item.get("uploaded_to_flow")):
            continue

        lic_raw = str(item.get("license") or item.get("license_short_name") or "").strip()
        lic_class = classify_media_license(lic_raw)
        if not lic_class.startswith("direct_insert_"):
            continue
        if not str(item.get("source_url") or "").strip():
            continue
        if lic_class == "direct_insert_cc_by":
            if not str(item.get("author") or item.get("attribution") or "").strip():
                continue
            if not str(item.get("license_uri") or "").strip():
                continue

        expected_sha = str(item.get("rendered_clip_sha256") or "").strip().lower()
        if not _SHA256_HEX_RE.match(expected_sha):
            continue
        clip_path = _resolve_rendered_clip_path(item, v_dir, clip_num=clip_num)
        if clip_path is None or not clip_path.is_file():
            continue
        actual_sha = hashlib.sha256(clip_path.read_bytes()).hexdigest().lower()
        if actual_sha != expected_sha:
            continue

        verified[clip_num] = {
            **item,
            "clip_number": clip_num,
            "license_class": lic_class,
            "clip_path": clip_path,
            "resolved_clip_path": str(clip_path),
        }
    return verified


__all__ = [
    "ARCHIVAL_CLIPS_DIRNAME",
    "ARCHIVAL_MANIFEST_REL",
    "R88A_CLIP_DURATION_RANGE",
    "R88A_FPS",
    "R88A_HEIGHT",
    "R88A_MAX_EPISODE_DURATION_SHARE",
    "R88A_MAX_INSERTS_PER_EPISODE",
    "R88A_WIDTH",
    "load_verified_archival_insert_clip_map",
    "normalize_cc_by_label",
    "render_archival_insert_clips",
    "validate_archival_inserts_manifest",
]
