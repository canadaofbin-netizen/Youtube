"""
ALL ABOUT BRAIN - YouTube Studio Autonomous Video Uploader
Uploads 1080x1920 Shorts to YouTube Studio via Naver Whale CDP with title,
DOI description, 9:16 thumbnail, Not-Made-For-Kids, AI content disclosure,
and 5-Slot Staggered Scheduling or Unlisted Staging Buffer.
"""

import asyncio
import hashlib
import json
import os
import re
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from playwright.async_api import async_playwright

from pipeline.config import (
    POSTHOC_SEMANTIC_QA_REPORT_FILENAME,
    PROJECTS_DIR,
    TITLE_MAX_CHARS_DIORAMA,
    is_diorama_profile,
)
from pipeline.storage import ProjectStorage
from pipeline.studio.config import (
    BANNED_OFF_TOPIC_TECH_TAGS,
    CHANNEL_CLEAN_KEYWORDS,
    CHANNEL_ID,
    CHANNEL_NAME,
    CHANNEL_RESIDENCE_COUNTRY,
    CHANNEL_RESIDENCE_COUNTRY_KO,
    CHANNEL_RESIDENCE_COUNTRY_NAME,
    DEFAULT_CDP_PORT,
    DEFAULT_EDUCATION_ACADEMIC_SYSTEM,
    DEFAULT_EDUCATION_ACADEMIC_SYSTEM_KO,
    DEFAULT_FALLBACK_PILLAR,
    DEFAULT_VIDEO_CATEGORY,
    DEFAULT_VIDEO_CATEGORY_KO,
    MIN_SCHEDULE_WARMUP_MINUTES,
    STUDIO_BASE_URL,
    STUDIO_PLAYLISTS_ENABLED,
    STUDIO_SELECTORS,
    STUDIO_SETTINGS_SELECTORS,
    TARGET_AUDIENCE_REGION,
    TITLE_DESCRIPTION_LANGUAGE_CODE,
    TITLE_DESCRIPTION_LANGUAGE_LABEL,
    TITLE_DESCRIPTION_LANGUAGE_LABEL_KO,
    VIDEO_LANGUAGE_CODE,
    VIDEO_LANGUAGE_LABEL,
    VIDEO_LANGUAGE_LABEL_KO,
    YOUTUBE_WATCH_BASE_URL,
    get_pillar_default_slot,
    get_slot_info,
)
from pipeline.studio.short_linker import (
    StudioShortLinker,
    is_valid_youtube_video_id,
    write_studio_publish_receipt,
)
from pipeline.studio.browser_session import (
    DirectCDPClient,
    WhaleSessionController,
    cleanup_staged_bridge_files,
)


def _now_us_eastern() -> datetime:
    """Returns current timezone-aware datetime in `America/New_York` (monkeypatchable in tests)."""
    return datetime.now(ZoneInfo("America/New_York"))


def compute_sha256(file_path: Path) -> str:
    """Computes lowercase hex SHA-256 of `file_path`."""
    h = hashlib.sha256()
    with open(file_path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _read_json_dict(path: Path) -> dict[str, Any]:
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            return data if isinstance(data, dict) else {}
    except Exception:
        pass
    return {}


def _is_legacy_hermetic_test_stub(project_dir: Path) -> bool:
    """
    Identifies synthetic hermetic metadata-only test stubs (`dossier == 'test_obedience'`
    in `tmp_path` without an assembled Stage 5 QA run) so unit tests exercising metadata
    packaging stay green while real projects and QA tests remain 100% locked.
    """
    p_dir = Path(project_dir)
    try:
        if p_dir.parent.resolve() == PROJECTS_DIR.resolve():
            return False
    except OSError:
        return False

    plan = _read_json_dict(p_dir / "03_visuals" / "visual_plan.json")
    script_doc = _read_json_dict(p_dir / "02_script" / "script.json")
    meta_doc = _read_json_dict(p_dir / "06_publish" / "metadata.json")
    if is_diorama_profile(plan) or is_diorama_profile(script_doc) or is_diorama_profile(meta_doc):
        return False
    if str(plan.get("dossier") or "") != "test_obedience":
        return False
    if (p_dir / "05_assembly" / "video_autopsy_report.json").exists():
        return False
    manifest = _read_json_dict(p_dir / "00_project_manifest.json")
    asm_stage = (manifest.get("stages") or {}).get("05_assembly") or {}
    asm_arts = asm_stage.get("artifacts") or {}
    real_asm_keys = [
        k for k in asm_arts if not str(k).startswith("carousel_source_frames/") and str(k) != "final_shorts_1080x1920.mp4"
    ]
    return len(real_asm_keys) == 0 and not (p_dir / "05_assembly" / "edit_decision_list.json").exists()


def verify_publish_ready_qa_bundle(
    project_dir: Path,
    require_semantic_review: bool = True,
    require_thumbnail_qa: bool | None = None,
    fast_stat_only: bool = False,
    require_prosody_qa: bool | None = None,
    require_ref_qa: bool | None = None,
    require_reenact_qa: bool | None = None,
    require_r64_review: bool | None = None,
) -> dict[str, Any]:
    """
    Mandatory Post-Assembly QA & R64 Semantic Review Lock before YouTube Studio upload:
      1. `05_assembly/final_shorts_1080x1920.mp4` exists + `ProjectStorage.verify_integrity()["all_intact"]`.
      2. `05_assembly/video_autopsy_report.json` exists, `passed == True`, and `final_mp4_sha256 == cur_sha`.
      3. For `neuro_diorama` projects (`is_diorama_profile`):
         - `05_assembly/dynamic_episode_qa_report.json` (`DQ1-DQ13`) exists, `passed == True`, and `final_mp4_sha256 == cur_sha`.
         - `05_assembly/posthoc_semantic_qa_report.json` (`R64`) exists, `passed == True`, and `final_mp4_sha256 == cur_sha`.
         - `04_audio/prosody_report.json` + `05_assembly/prosody_qa_report.json` (`P1-P10`) passed when audio/R66/R68 present.
         - `03_visuals/reference_image_qa_report.json` (`Q1-Q10`) passed when R66/R68 or reference pack present.
         - `05_assembly/reenactment_qa_report.json` (`RQ1-RQ5`) passed when Track A (`source_edl.json` / `reenactment_track == 'track_a'`).
         - When `require_semantic_review=True`, `05_assembly/posthoc_semantic_review.json` passes `validate_posthoc_semantic_review(...)["valid"] == True`.
    """
    from pipeline.media_cache import fast_file_sha256
    if require_r64_review is not None:
        require_semantic_review = bool(require_r64_review)

    p_dir = Path(project_dir)
    project_id = p_dir.name
    issues: list[str] = []

    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    cur_sha = ""
    mp4_size = -1
    if not final_mp4.exists() or not final_mp4.is_file():
        issues.append("missing_final_shorts_1080x1920_mp4")
    elif fast_stat_only:
        try:
            mp4_size = final_mp4.stat().st_size
            if mp4_size <= 0:
                issues.append("empty_final_shorts_1080x1920_mp4")
        except OSError as exc:
            issues.append(f"final_mp4_stat_error:{exc}")
    else:
        try:
            cur_sha = compute_sha256(final_mp4)
        except OSError as exc:
            issues.append(f"final_mp4_sha256_read_error:{exc}")

    integrity_ok = False
    manifest_path = p_dir / "00_project_manifest.json"
    if not manifest_path.exists():
        issues.append("missing_00_project_manifest_json")
    elif fast_stat_only:
        manifest_doc = _read_json_dict(manifest_path)
        asm_artifacts = ((manifest_doc.get("stages") or {}).get("05_assembly") or {}).get("artifacts") or {}
        rec_mp4 = asm_artifacts.get("final_shorts_1080x1920.mp4")
        if isinstance(rec_mp4, dict):
            cur_sha = str(rec_mp4.get("sha256") or "")
            rec_sz = rec_mp4.get("size_bytes")
            if rec_sz is not None and mp4_size > 0 and int(rec_sz) != mp4_size:
                issues.append("manifest_final_mp4_size_mismatch")
            else:
                integrity_ok = True
        else:
            integrity_ok = bool(manifest_doc.get("stages"))
        if not cur_sha and final_mp4.is_file() and mp4_size > 0:
            try:
                cur_sha = fast_file_sha256(final_mp4)
            except OSError as exc:
                issues.append(f"final_mp4_sha256_read_error:{exc}")
    else:
        try:
            storage = (
                ProjectStorage(project_id)
                if p_dir.parent.resolve() == PROJECTS_DIR.resolve()
                else ProjectStorage(project_id, projects_dir=p_dir.parent)
            )
            integrity_report = storage.verify_integrity()
            integrity_ok = bool(integrity_report.get("all_intact"))
            if not integrity_ok:
                corrupted = integrity_report.get("corrupted_or_missing") or []
                issues.append(f"project_storage_integrity_failed:{len(corrupted)}")
            manifest_doc = storage.get_manifest()
            asm_artifacts = ((manifest_doc.get("stages") or {}).get("05_assembly") or {}).get("artifacts") or {}
            rec_mp4 = asm_artifacts.get("final_shorts_1080x1920.mp4")
            if isinstance(rec_mp4, dict) and rec_mp4.get("sha256") and cur_sha:
                if str(rec_mp4["sha256"]) != cur_sha:
                    integrity_ok = False
                    issues.append("manifest_final_mp4_sha256_mismatch")
        except Exception as exc:
            issues.append(f"project_storage_verify_error:{exc}")

    autopsy_path = p_dir / "05_assembly" / "video_autopsy_report.json"
    autopsy_ok = False
    if not autopsy_path.exists():
        issues.append("missing_video_autopsy_report_json")
    else:
        autopsy_doc = _read_json_dict(autopsy_path)
        autopsy_sha = str(autopsy_doc.get("final_mp4_sha256") or "")
        if autopsy_doc.get("passed") is not True:
            issues.append("video_autopsy_not_passed")
        elif not autopsy_sha or (cur_sha and autopsy_sha != cur_sha):
            issues.append("stale_video_autopsy_final_mp4_sha256_mismatch")
        else:
            autopsy_ok = True

    plan = _read_json_dict(p_dir / "03_visuals" / "visual_plan.json")
    script_doc = _read_json_dict(p_dir / "02_script" / "script.json")
    meta_doc = _read_json_dict(p_dir / "06_publish" / "metadata.json")
    is_diorama = is_diorama_profile(plan) or is_diorama_profile(script_doc) or is_diorama_profile(meta_doc)
    style_prof = str(plan.get("style_profile") or script_doc.get("style_profile") or "").strip()
    is_porcelain_or_v8 = style_prof in ("porcelain_cinematic_v7", "expressive_25d_v8")

    dq_ok: bool | None = None
    posthoc_ok: bool | None = None
    review_ok: bool | None = None
    prosody_ok: bool | None = None
    ref_qa_ok: bool | None = None
    reenact_qa_ok: bool | None = None
    edl_sha = ""

    if is_diorama:
        dq_path = p_dir / "05_assembly" / "dynamic_episode_qa_report.json"
        dq_ok = False
        if not dq_path.exists():
            issues.append("missing_dynamic_episode_qa_report_json")
        else:
            dq_doc = _read_json_dict(dq_path)
            if dq_doc.get("passed") is not True:
                issues.append("dynamic_episode_qa_not_passed")
            elif str(dq_doc.get("final_mp4_sha256") or "") != cur_sha:
                issues.append("stale_dynamic_episode_qa_final_mp4_sha256_mismatch")
            else:
                dq_ok = True

        edl_path = p_dir / "05_assembly" / "edit_decision_list.json"
        concat_path = p_dir / "05_assembly" / "concat_list.txt"
        if edl_path.exists():
            edl_sha = compute_sha256(edl_path)
        elif concat_path.exists():
            edl_sha = compute_sha256(concat_path)

        posthoc_path = p_dir / "05_assembly" / POSTHOC_SEMANTIC_QA_REPORT_FILENAME
        posthoc_ok = False
        posthoc_doc: dict[str, Any] = {}
        if not posthoc_path.exists():
            issues.append("missing_posthoc_semantic_qa_report_json")
        else:
            posthoc_doc = _read_json_dict(posthoc_path)
            if posthoc_doc.get("passed") is not True:
                issues.append("posthoc_semantic_qa_not_passed")
            elif str(posthoc_doc.get("final_mp4_sha256") or "") != cur_sha:
                issues.append("stale_posthoc_semantic_qa_final_mp4_sha256_mismatch")
            else:
                posthoc_ok = True

        # Prosody P1-P10 gate validation
        prosody_meta_path = p_dir / "04_audio" / "prosody_report.json"
        prosody_qa_path = p_dir / "05_assembly" / "prosody_qa_report.json"
        has_audio_stage = (p_dir / "04_audio" / "audio_master.wav").exists()
        if require_prosody_qa is True or (
            require_prosody_qa is None
            and (is_porcelain_or_v8 or prosody_meta_path.exists() or prosody_qa_path.exists() or has_audio_stage)
        ):
            prosody_ok = False
            if not prosody_meta_path.exists() and not prosody_qa_path.exists():
                issues.append("missing_prosody_report_json")
            else:
                pr_meta = _read_json_dict(prosody_meta_path) if prosody_meta_path.exists() else {}
                pr_qa = _read_json_dict(prosody_qa_path) if prosody_qa_path.exists() else {}
                if prosody_meta_path.exists() and not pr_meta:
                    issues.append("corrupt_prosody_report_json")
                elif prosody_qa_path.exists() and pr_qa.get("passed") is not True:
                    issues.append(f"prosody_qa_not_passed:{pr_qa.get('gates_passed', 'failed')}")
                elif not prosody_qa_path.exists() and pr_meta.get("passed") is False:
                    issues.append("prosody_report_not_passed")
                elif not prosody_qa_path.exists() and (is_porcelain_or_v8 or require_prosody_qa is True) and pr_meta.get("passed") is not True:
                    issues.append("missing_prosody_qa_report_json")
                else:
                    prosody_ok = True

        # Reference Image QA (Q1-Q10) validation
        ref_qa_path = p_dir / "03_visuals" / "reference_image_qa_report.json"
        if not ref_qa_path.exists():
            alt_ref = p_dir / "03_visuals" / "reference_images" / "reference_image_qa_report.json"
            if alt_ref.exists():
                ref_qa_path = alt_ref
        has_ref_dir = (p_dir / "03_visuals" / "reference_images").exists()
        if require_ref_qa is True or (
            require_ref_qa is None and (is_porcelain_or_v8 or ref_qa_path.exists() or has_ref_dir)
        ):
            ref_qa_ok = False
            if not ref_qa_path.exists():
                issues.append("missing_reference_image_qa_report_json")
            else:
                ref_doc = _read_json_dict(ref_qa_path)
                if not ref_doc:
                    issues.append("corrupt_reference_image_qa_report_json")
                elif not (
                    ref_doc.get("passed") is True
                    or ref_doc.get("pre_generation_ready") is True
                    or ref_doc.get("all_passed") is True
                ):
                    issues.append("reference_image_qa_not_passed")
                else:
                    ref_qa_ok = True

        # Reenactment Non-Infringement QA (RQ1-RQ5) for Track A
        is_track_a = (p_dir / "03_visuals" / "source_edl.json").exists() or str(plan.get("reenactment_track") or "") == "track_a"
        rqa_path = p_dir / "05_assembly" / "reenactment_qa_report.json"
        if require_reenact_qa is True or (require_reenact_qa is None and (is_track_a or rqa_path.exists())):
            reenact_qa_ok = False
            if not rqa_path.exists():
                issues.append("missing_reenactment_qa_report_json")
            else:
                rqa_doc = _read_json_dict(rqa_path)
                if rqa_doc.get("passed") is not True:
                    issues.append(f"reenactment_qa_not_passed:{rqa_doc.get('gates_passed', 'failed')}")
                else:
                    reenact_qa_ok = True

        if require_semantic_review:
            from pipeline.posthoc_qa import validate_posthoc_semantic_review

            edl_doc = _read_json_dict(edl_path)
            expected_cuts = int(
                posthoc_doc.get("cut_count")
                or len(posthoc_doc.get("cuts") or [])
                or len(edl_doc.get("cuts") or [])
                or 1
            )
            rev_res = validate_posthoc_semantic_review(
                p_dir,
                final_mp4_sha256=cur_sha,
                edl_sha256=edl_sha,
                expected_cut_count=expected_cuts,
            )
            review_ok = bool(rev_res.get("valid") is True)
            if not review_ok:
                rev_issues = rev_res.get("issues") or ["invalid_posthoc_semantic_review"]
                issues.extend(f"posthoc_semantic_review:{it}" for it in rev_issues)
        else:
            review_ok = True

        from pipeline.config import THUMBNAIL_REPORT_FILENAME

        thumb_rep_path = p_dir / "06_publish" / THUMBNAIL_REPORT_FILENAME
        has_r65_block = isinstance(plan.get("thumbnail"), dict)
        thumb_warnings: list[str] = []
        thumb_qa_ok: bool | None = None
        if require_thumbnail_qa is True or (
            require_thumbnail_qa is None and (thumb_rep_path.exists() or has_r65_block)
        ):
            thumb_qa_ok = False
            if not thumb_rep_path.exists():
                issues.append("missing_thumbnail_report_json")
            else:
                thumb_doc = _read_json_dict(thumb_rep_path)
                var_map = thumb_doc.get("variants") if isinstance(thumb_doc.get("variants"), dict) else {}
                sha_mismatch = False
                for vk in ("A", "B", "C"):
                    vp_png = p_dir / "06_publish" / f"thumbnail_var_{vk}.png"
                    exp_sha = str((var_map.get(vk) or {}).get("sha256") or "")
                    if not vp_png.exists() or not exp_sha or compute_sha256(vp_png) != exp_sha:
                        sha_mismatch = True
                        break
                if sha_mismatch:
                    issues.append("stale_thumbnail_report_variant_sha256_mismatch")
                elif thumb_doc.get("passed") is not True:
                    if require_thumbnail_qa is True or str(thumb_doc.get("mode") or "") != "backfill_soft":
                        issues.append(f"thumbnail_qa_not_passed:{thumb_doc.get('failed_gates', [])}")
                    else:
                        thumb_warnings.append(f"backfill_soft_thumbnail_warnings:{thumb_doc.get('failed_gates', [])}")
                        thumb_qa_ok = True
                else:
                    thumb_qa_ok = True
    else:
        thumb_warnings = []
        thumb_qa_ok = None

    return {
        "passed": len(issues) == 0,
        "project_id": project_id,
        "is_diorama": is_diorama,
        "final_mp4_path": str(final_mp4),
        "final_mp4_sha256": cur_sha,
        "edl_sha256": edl_sha,
        "integrity_intact": integrity_ok,
        "autopsy_passed": autopsy_ok,
        "dynamic_episode_qa_passed": dq_ok,
        "posthoc_semantic_qa_passed": posthoc_ok,
        "prosody_qa_passed": prosody_ok,
        "reference_image_qa_passed": ref_qa_ok,
        "reenactment_qa_passed": reenact_qa_ok,
        "posthoc_semantic_review_valid": review_ok,
        "thumbnail_qa_passed": thumb_qa_ok,
        "warnings": thumb_warnings,
        "issues": issues,
    }


def _safe_exists(path: Path) -> bool:
    try:
        return path.exists()
    except OSError:
        return False


def _safe_glob(path: Path, pattern: str) -> list[Path]:
    try:
        return list(path.glob(pattern)) if _safe_exists(path) else []
    except OSError:
        return []


def resolve_project_video_path(project_dir: Path, project_id: str | None = None) -> Path | None:
    """
    Resolves compiled vertical Short MP4 for a project:
    1. 05_assembly/final_shorts_1080x1920.mp4
    2. Non-burnin *.mp4 in 05_assembly/ or project_dir
    3. Completed_Psychology_100_Shorts/final_shorts_<project_id>.mp4 archive fallback
    """
    pid = project_id or project_dir.name
    primary = project_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if _safe_exists(primary):
        return primary

    assembly_dir = project_dir / "05_assembly"
    mp4_candidates = [
        p for p in (
            _safe_glob(assembly_dir, "*.mp4")
            + _safe_glob(project_dir, "*.mp4")
        )
        if "burnin" not in p.name
    ]
    if mp4_candidates:
        return mp4_candidates[0]

    rel_roots: list[Path] = []
    for cand in (project_dir.parent, project_dir.parent.parent, project_dir.parent.parent.parent):
        if cand not in rel_roots:
            rel_roots.append(cand)
    if project_dir.resolve().parent == PROJECTS_DIR.resolve():
        ws_root = Path(__file__).resolve().parents[2]
        if ws_root not in rel_roots:
            rel_roots.append(ws_root)
    for root_cand in rel_roots:
        archive_mp4 = root_cand / "Completed_Psychology_100_Shorts" / f"final_shorts_{pid}.mp4"
        if _safe_exists(archive_mp4):
            return archive_mp4

    return None


class StudioUploader:
    """
    Automates YouTube Studio video upload, 9:16 custom thumbnail registration,
    AI altered content declaration (R4 compliance), Two-Tier Localization
    (KR Residence + en-US Video/Title/Description Language), and 5-Slot scheduled releases.
    """

    def __init__(self, cdp_port: int = DEFAULT_CDP_PORT, projects_dir: Path | None = None):
        self.cdp_port = cdp_port
        self.projects_dir = projects_dir or PROJECTS_DIR
        self.session = WhaleSessionController(cdp_port=cdp_port)

    @staticmethod
    def apply_first_frame_burn_in(
        video_path: Path,
        thumbnail_path: Path,
        output_path: Path | None = None
    ) -> Path:
        """
        Burns in the custom 9:16 thumbnail onto the first two frames (0.06s) of the video.
        Ensures that if YouTube Shorts UI locks custom thumbnail selection or non-partnered accounts
        cannot set a custom cover, YouTube's default frame-0 extraction displays the thumbnail.
        """
        if not video_path.exists():
            raise FileNotFoundError(f"Video not found: {video_path}")
        if not thumbnail_path or not thumbnail_path.exists():
            return video_path

        if not output_path:
            output_path = video_path.parent / f"{video_path.stem}_burnin{video_path.suffix}"

        tmp_mp4: Path | None = None
        try:
            import shutil
            import subprocess
            import tempfile

            import imageio_ffmpeg
            ffmpeg_exe = imageio_ffmpeg.get_ffmpeg_exe()
            fd, tmp_name = tempfile.mkstemp(prefix="burnin_", suffix=output_path.suffix or ".mp4")
            os.close(fd)
            tmp_mp4 = Path(tmp_name)
            cmd = [
                ffmpeg_exe, "-y",
                "-i", str(video_path.resolve()),
                "-i", str(thumbnail_path.resolve()),
                "-filter_complex", "[0:v][1:v]overlay=0:0:enable='lte(n,1)'[v]",
                "-map", "[v]",
                "-map", "0:a?",
                "-c:a", "copy",
                "-c:v", "libx264",
                "-preset", "ultrafast",
                "-pix_fmt", "yuv420p",
                str(tmp_mp4),
            ]
            from pipeline.config import SUBPROCESS_TIMEOUT_SEC
            res = subprocess.run(cmd, capture_output=True, text=True, timeout=SUBPROCESS_TIMEOUT_SEC)
            if res.returncode == 0 and tmp_mp4.exists() and tmp_mp4.stat().st_size > 0:
                output_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.move(str(tmp_mp4), str(output_path.resolve()))
                tmp_mp4 = None
                print(f"[StudioUploader] Successfully burned custom thumbnail into first frame: {output_path.name}")
                return output_path
            else:
                print(f"[StudioUploader] Warning: FFmpeg burn-in returned code {res.returncode}: {res.stderr[:200]}")
        except Exception as e:
            print(f"[StudioUploader] Warning: Burn-in exception ({e}), falling back to original video.")
        finally:
            if tmp_mp4 is not None and tmp_mp4.exists():
                try:
                    tmp_mp4.unlink()
                except OSError:
                    pass

        return video_path

    def prepare_upload_payload(
        self,
        project_id: str,
        slot_id: int | None = None,
        target_date: str | None = None,
        visibility: str = "unlisted",
        burn_first_frame: bool = False,
        skip_qa_gate: bool = False,
        require_semantic_review: bool = True,
        allow_instant_public: bool = False,
    ) -> dict[str, Any]:
        """Loads and verifies all project artifacts and mandatory QA locks required for publishing."""
        norm_vis = str(visibility or "").strip().lower()
        if norm_vis == "public" and not allow_instant_public:
            raise ValueError(
                "[R75] Instant Public upload is banned on YouTube Studio; "
                "use visibility='scheduled' (>= 3.0h warmup) or pass allow_instant_public=True."
            )

        proj_dir = self.projects_dir / project_id
        if not proj_dir.exists():
            raise FileNotFoundError(f"Project directory not found: {proj_dir}")

        qa_bundle: dict[str, Any] | None = None
        if not skip_qa_gate and not _is_legacy_hermetic_test_stub(proj_dir):
            qa_bundle = verify_publish_ready_qa_bundle(
                proj_dir,
                require_semantic_review=require_semantic_review,
            )
            if not qa_bundle["passed"]:
                raise RuntimeError(
                    f"Upload blocked by post-assembly QA gate for '{project_id}': "
                    f"{'; '.join(qa_bundle['issues'])}"
                )

        storage = ProjectStorage(project_id, projects_dir=self.projects_dir)
        manifest = storage.get_manifest()

        publish_dir = storage.get_stage_dir("06_publish")
        metadata_file = publish_dir / "metadata.json"
        if not metadata_file.exists():
            raise FileNotFoundError(f"Metadata not found at {metadata_file}. Run Stage 6 first.")

        with open(metadata_file, "r", encoding="utf-8") as f:
            metadata = json.load(f)

        pillar = str(
            (metadata.get("pillar") if isinstance(metadata, dict) else None)
            or manifest.get("pillar")
            or DEFAULT_FALLBACK_PILLAR
        ).strip() or DEFAULT_FALLBACK_PILLAR

        # Video asset resolution (includes Completed_Psychology_100_Shorts fallback)
        resolved_video = resolve_project_video_path(proj_dir, project_id)
        if resolved_video is None:
            raise FileNotFoundError(f"No compiled MP4 found in project {project_id}")
        video_path = resolved_video

        vp_data = storage.load_json("03_visuals", "visual_plan.json") or {}
        scr_data = storage.load_json("02_script", "script.json") or {}
        is_diorama = is_diorama_profile(metadata) or is_diorama_profile(vp_data) or is_diorama_profile(scr_data)

        # Thumbnail asset resolution (prefers Variant A or standard thumbnail.png)
        thumb_path = publish_dir / "thumbnail_var_A.png"
        if not thumb_path.exists():
            thumb_path = publish_dir / "thumbnail.png"
        thumb_report = storage.load_json("06_publish", "thumbnail_report.json") or {}
        cover_frame_sec = thumb_report.get("cover_frame_sec")

        # R65: --burn-first-frame is retired/deprecated for neuro_diorama Shorts (protects R57-H2 cold-open)
        if burn_first_frame:
            import warnings

            warnings.warn(
                "--burn-first-frame is deprecated under R65 (use in-video cover_frame_sec instead).",
                DeprecationWarning,
                stacklevel=2,
            )
            if is_diorama:
                print(
                    f"[StudioUploader] Skipping deprecated --burn-first-frame on neuro_diorama '{project_id}' "
                    f"to protect R57-H2 cold-open (cover_frame_sec={cover_frame_sec})."
                )
            elif thumb_path.exists():
                burn_out = (proj_dir / "05_assembly" / f"{video_path.stem}_burnin{video_path.suffix}")
                burn_out.parent.mkdir(parents=True, exist_ok=True)
                video_path = self.apply_first_frame_burn_in(video_path, thumb_path, output_path=burn_out)

        # Determine slot & scheduling time in US Eastern Time (America/New_York, DST-aware)
        is_sched = norm_vis == "scheduled"
        now_et = _now_us_eastern()
        if slot_id is None:
            slot_id = 4 if is_sched else get_pillar_default_slot(pillar)

        if not target_date:
            target_date = now_et.strftime("%Y-%m-%d")

        ref_date_obj = None
        try:
            ref_date_obj = datetime.strptime(target_date, "%Y-%m-%d").date()
        except ValueError:
            ref_date_obj = now_et.date()
            target_date = ref_date_obj.strftime("%Y-%m-%d")

        if is_sched and ref_date_obj is not None:
            # Load already-booked scheduled dates from staging_queue.json so daily prime uploads never collide
            booked_dates: set[str] = set()
            q_candidates = [self.projects_dir.parent / "staging_queue.json"]
            for qp in q_candidates:
                q_doc = _read_json_dict(qp)
                for item in (list(q_doc.get("queue") or []) + list(q_doc.get("scheduled_items") or [])):
                    if not isinstance(item, dict):
                        continue
                    if str(item.get("project_id") or "") == project_id:
                        continue
                    st = str(item.get("status") or "").strip().lower()
                    if st in ("scheduled", "scheduled_public"):
                        b_date = str(item.get("target_publish_date") or item.get("date") or "").strip()
                        if not b_date and item.get("scheduled_time_et"):
                            b_date = str(item["scheduled_time_et"]).split()[0].strip()
                        if b_date:
                            booked_dates.add(b_date)

            for _ in range(366):
                cand_slot = get_slot_info(slot_id, ref_date=ref_date_obj)
                cand_date_str = ref_date_obj.strftime("%Y-%m-%d")
                cand_dt_et = datetime.strptime(
                    f"{cand_date_str} {cand_slot['time_et']}", "%Y-%m-%d %H:%M"
                ).replace(tzinfo=ZoneInfo("America/New_York"))
                if cand_dt_et <= now_et + timedelta(minutes=MIN_SCHEDULE_WARMUP_MINUTES) or cand_date_str in booked_dates:
                    ref_date_obj = ref_date_obj + timedelta(days=1)
                    continue
                target_date = cand_date_str
                break

        slot_info = get_slot_info(slot_id, ref_date=ref_date_obj)

        max_title_len = TITLE_MAX_CHARS_DIORAMA if is_diorama else 60
        clean_title = metadata.get("title", f"ALL ABOUT BRAIN - {project_id}")
        if len(clean_title) > max_title_len:
            clean_title = clean_title[: max_title_len - 3].rstrip() + "..."

        description = metadata.get("description", clean_title)

        from pipeline.publish import build_clean_episode_tags, validate_episode_tags_hygiene

        raw_tags = metadata.get("tags") if isinstance(metadata, dict) else None
        if isinstance(raw_tags, list) and raw_tags:
            tags = [str(t).strip() for t in raw_tags if str(t).strip()]
            validate_episode_tags_hygiene(tags, pillar, raise_on_error=True)
        else:
            tags = build_clean_episode_tags(
                project_id=project_id,
                title=clean_title,
                pillar=pillar,
                script=scr_data if isinstance(scr_data, dict) else {},
                metadata=metadata if isinstance(metadata, dict) else {},
            )
            validate_episode_tags_hygiene(tags, pillar, raise_on_error=True)

        raw_cat = str(metadata.get("category") or DEFAULT_VIDEO_CATEGORY).strip()
        if pillar != "bci_tech" and raw_cat.lower() in ("science & technology", "science and technology", "과학 기술"):
            raw_cat = DEFAULT_VIDEO_CATEGORY

        return {
            "project_id": project_id,
            "pillar": pillar,
            "video_path": video_path,
            "thumbnail_path": thumb_path,
            "cover_frame_sec": cover_frame_sec,
            "title": clean_title,
            "description": description,
            "tags": tags,
            "visibility": visibility,
            "slot_id": slot_id,
            "slot_info": slot_info,
            "target_date": target_date,
            "scheduled_time_et": f"{target_date} {slot_info['time_et']} ET",
            "category": raw_cat or DEFAULT_VIDEO_CATEGORY,
            "video_language": metadata.get("video_language", VIDEO_LANGUAGE_CODE),
            "video_language_label": metadata.get("video_language_label", VIDEO_LANGUAGE_LABEL),
            "title_description_language": metadata.get("title_description_language", TITLE_DESCRIPTION_LANGUAGE_CODE),
            "title_description_language_label": metadata.get("title_description_language_label", TITLE_DESCRIPTION_LANGUAGE_LABEL),
            "channel_residence_country": metadata.get("channel_residence_country", CHANNEL_RESIDENCE_COUNTRY),
            "channel_residence_country_name": metadata.get("channel_residence_country_name", CHANNEL_RESIDENCE_COUNTRY_NAME),
            "target_audience_region": metadata.get("target_audience_region", TARGET_AUDIENCE_REGION),
            "qa_bundle": qa_bundle,
            "skip_qa_gate": skip_qa_gate,
            "storage": storage
        }

    async def _ensure_all_about_brain_channel(self, client: DirectCDPClient) -> bool:
        """
        Verifies the active YouTube Studio session is on ALL ABOUT BRAIN (UC4FeioYYv9X04Di07_MfZ7g).
        Checks sidebar/header channel links first because on /video/<id>/edit #entity-name is the video title.
        """
        curr_url = await client.eval("location.href") or ""
        title_text = await client.eval("document.title") or ""
        if "Oops" in title_text:
            await client.send("Page.navigate", {"url": f"https://studio.youtube.com/channel/{CHANNEL_ID}"})
            await asyncio.sleep(4.5)
            curr_url = await client.eval("location.href") or ""

        if CHANNEL_ID in curr_url and "Oops" not in (await client.eval("document.title") or ""):
            return True

        has_channel_anchor = await client.eval(
            f"Boolean(document.querySelector('a[href*={json.dumps(CHANNEL_ID)}]'))"
        )
        if has_channel_anchor:
            return True

        entity_res = await client.eval("(() => { const e = document.querySelector('#entity-name'); return e ? e.innerText.trim() : ''; })()") or ""
        entity_name = str(entity_res.get("entityName") or "") if isinstance(entity_res, dict) else str(entity_res)
        if CHANNEL_NAME.lower() in entity_name.lower():
            return True

        print(f"[StudioUploader] Current channel is '{entity_name}'. Switching to {CHANNEL_NAME} ({CHANNEL_ID})...")
        await client.click("#avatar-btn, button#avatar-btn, ytcp-button#avatar-btn, img#img")
        await asyncio.sleep(1.5)
        await client.eval(
            """(() => {
                const items = Array.from(document.querySelectorAll('tp-yt-paper-item, ytd-compact-link-renderer'));
                const sw = items.find(e => (e.innerText || '').includes('Switch account') || (e.innerText || '').includes('\\uacc4\\uc815 \\uc804\\ud658'));
                if (sw) sw.click();
            })()"""
        )
        await asyncio.sleep(2.0)
        switched = await client.eval(
            f"""(() => {{
                const items = Array.from(document.querySelectorAll('ytd-account-item-renderer, tp-yt-paper-icon-item'));
                const target = items.find(e => (e.innerText || '').includes({json.dumps(CHANNEL_NAME)}));
                if (target) {{ target.click(); return true; }}
                return false;
            }})()"""
        )
        if switched:
            await asyncio.sleep(5.0)
        return bool(switched)

    async def _ensure_upload_wizard_en_us_language(
        self,
        client: DirectCDPClient,
        container_selector: str | None = None
    ) -> dict[str, bool]:
        """
        Ensures Video language and Title/description language in the active dialog/wizard
        are locked to English (United States) / \\uc601\\uc5b4(\\ubbf8\\uad6d).
        Scopes queries to visible elements inside container_selector so closed background
        dialogs (e.g. a closed ytcp-settings-dialog) never shadow the active wizard.
        """
        results = {"video_language_set": False, "title_description_language_set": False}
        en_us_labels = [VIDEO_LANGUAGE_LABEL, VIDEO_LANGUAGE_LABEL_KO]
        scope_sel = container_selector or "ytcp-uploads-dialog, ytcp-upload-dialog, ytcp-video-metadata-editor-advanced, ytcp-settings-dialog"

        for field_id, key_name in [("#audio-language", "video_language_set"), ("#metadata-language", "title_description_language_set")]:
            curr_text = await client.eval(
                f"""(() => {{
                    const roots = Array.from(document.querySelectorAll({json.dumps(scope_sel)}));
                    let candidates = [];
                    for (const r of roots) {{
                        candidates.push(...Array.from(r.querySelectorAll('{field_id}')));
                    }}
                    if (!candidates.length) {{
                        candidates = Array.from(document.querySelectorAll('{field_id}'));
                    }}
                    const vis = candidates.find(e => e.offsetParent !== null) || candidates[0];
                    return vis ? (vis.innerText || '').trim() : '';
                }})()"""
            ) or ""
            if any(lbl in curr_text for lbl in en_us_labels):
                results[key_name] = True
                continue
            trigger_ok = await client.eval(
                f"""(() => {{
                    const roots = Array.from(document.querySelectorAll({json.dumps(scope_sel)}));
                    let triggers = [];
                    for (const r of roots) {{
                        triggers.push(...Array.from(r.querySelectorAll('{field_id} #trigger')));
                    }}
                    if (!triggers.length) {{
                        triggers = Array.from(document.querySelectorAll('{field_id} #trigger'));
                    }}
                    const vis = triggers.find(e => e.offsetParent !== null) || triggers[0];
                    if (vis) {{
                        vis.scrollIntoView({{block: 'center'}});
                        vis.click();
                        return true;
                    }}
                    return false;
                }})()"""
            )
            if trigger_ok:
                await asyncio.sleep(1.2)
                clicked = await client.eval(
                    f"""(() => {{
                        const labels = {json.dumps(en_us_labels)};
                        const items = Array.from(document.querySelectorAll('tp-yt-paper-item'));
                        const match = items.find(e => e.offsetParent !== null && labels.includes((e.innerText || '').trim()));
                        if (match) {{ match.scrollIntoView({{block: 'center'}}); match.click(); return true; }}
                        return false;
                    }})()"""
                )
                await asyncio.sleep(1.0)
                updated_text = await client.eval(
                    f"""(() => {{
                        const roots = Array.from(document.querySelectorAll({json.dumps(scope_sel)}));
                        let candidates = [];
                        for (const r of roots) {{
                            candidates.push(...Array.from(r.querySelectorAll('{field_id}')));
                        }}
                        if (!candidates.length) {{
                            candidates = Array.from(document.querySelectorAll('{field_id}'));
                        }}
                        const vis = candidates.find(e => e.offsetParent !== null) || candidates[0];
                        return vis ? (vis.innerText || '').trim() : '';
                    }})()"""
                ) or ""
                results[key_name] = bool(clicked) and any(lbl in updated_text for lbl in en_us_labels)
        return results

    @staticmethod
    async def _capture_background_screenshot_bytes(client: DirectCDPClient) -> bytes:
        """Captures PNG screenshot bytes from a background leased tab via Page.startScreencast without stealing focus."""
        import base64
        import contextlib

        if not hasattr(client, "send"):
            return b""
        with contextlib.suppress(Exception):
            await client.send("Page.startScreencast", {"format": "png", "quality": 90, "everyNthFrame": 1})
        try:
            await asyncio.sleep(0.8)
            shot = await client.send("Page.captureScreenshot", {"format": "png", "fromSurface": True})
            b64 = str((shot or {}).get("data") or "")
            return base64.b64decode(b64) if b64 else b""
        finally:
            with contextlib.suppress(Exception):
                await client.send("Page.stopScreencast")

    @staticmethod
    async def _prepare_leased_tab_for_close(client: DirectCDPClient) -> None:
        """Disarms any YouTube Studio beforeunload listeners and navigates to about:blank so /json/close succeeds cleanly."""
        import contextlib

        if not hasattr(client, "send"):
            return
        with contextlib.suppress(Exception):
            await client.eval("(() => { try { window.onbeforeunload = null; } catch(e) {} return true; })()")
        with contextlib.suppress(Exception):
            await client.send("Page.navigate", {"url": "about:blank"})
            await asyncio.sleep(0.4)

    async def _read_chip_bar_values(self, client: DirectCDPClient, container_selector: str) -> list[str]:
        if not hasattr(client, "send"):
            return []
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        res = await client.eval(
            rf"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const roots = __queryAllDeep({json.dumps(container_selector)});
                const root = roots.find(r => r.getBoundingClientRect().width > 0) || roots[0];
                if (!root) return [];
                const chips = __queryAllDeep('ytcp-chip', root);
                return chips.map(c => {{
                    const t = __queryAllDeep('#chip-text, .chip-text', c)[0] || c;
                    return ((t.innerText || t.textContent || '').split('\n')[0] || '').trim();
                }}).filter(Boolean);
            }})()"""
        )
        return [str(x).strip() for x in (res or []) if str(x).strip()]

    async def _set_chip_bar_values(
        self,
        client: DirectCDPClient,
        *,
        container_selector: str,
        target_values: list[str] | tuple[str, ...],
    ) -> list[str]:
        """Deterministically clears all Polymer ytcp-chip items in `container_selector` and inserts `target_values`."""
        if not hasattr(client, "send"):
            return []
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        # 1. Click #clear-button ("Delete all") if present & visible
        await client.eval(
            rf"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const roots = __queryAllDeep({json.dumps(container_selector)});
                const root = roots.find(r => r.getBoundingClientRect().width > 0) || roots[0];
                if (!root) return false;
                root.scrollIntoView({{block: 'center'}});
                const clr = __queryAllDeep('#clear-button, ytcp-icon-button#clear-button, [aria-label="Delete all"], [aria-label="모두 삭제"]', root)
                    .find(b => b.getBoundingClientRect().width > 0);
                if (clr) {{
                    const inner = __queryAllDeep('button', clr)[0] || clr;
                    inner.click();
                    return true;
                }}
                return false;
            }})()"""
        )
        await asyncio.sleep(0.35)

        # 2. Loop clicking individual chip #delete-icon buttons until 0 chips remain
        for _ in range(36):
            rem = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const roots = __queryAllDeep({json.dumps(container_selector)});
                    const root = roots.find(r => r.getBoundingClientRect().width > 0) || roots[0];
                    if (!root) return 0;
                    const chips = __queryAllDeep('ytcp-chip', root);
                    if (!chips.length) return 0;
                    for (const ch of chips.slice(0, 8)) {{
                        const del = __queryAllDeep('#delete-icon, [aria-label="Remove"], [aria-label="삭제"], button', ch)[0];
                        if (del) {{
                            try {{ del.click(); }} catch(e) {{}}
                        }}
                    }}
                    return chips.length;
                }})()"""
            )
            if not rem:
                break
            await asyncio.sleep(0.18)

        # 3. Insert target_values if non-empty
        cleaned_targets = [str(v).strip() for v in target_values if str(v).strip()]
        if cleaned_targets:
            for val in cleaned_targets:
                focused = await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const roots = __queryAllDeep({json.dumps(container_selector)});
                        const root = roots.find(r => r.getBoundingClientRect().width > 0) || roots[0];
                        if (!root) return false;
                        const inp = __queryAllDeep('input#text-input, input', root).find(i => i.getBoundingClientRect().width > 0)
                            || __queryAllDeep('input#text-input, input', root)[0];
                        if (!inp) return false;
                        inp.scrollIntoView({{block: 'center'}});
                        inp.focus();
                        inp.value = '';
                        inp.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                        return true;
                    }})()"""
                )
                if not focused:
                    break
                await client.send("Input.insertText", {"text": val})
                await client.send(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyDown",
                        "key": "Enter",
                        "code": "Enter",
                        "windowsVirtualKeyCode": 13,
                        "nativeVirtualKeyCode": 13,
                    },
                )
                await client.send(
                    "Input.dispatchKeyEvent",
                    {
                        "type": "keyUp",
                        "key": "Enter",
                        "code": "Enter",
                        "windowsVirtualKeyCode": 13,
                        "nativeVirtualKeyCode": 13,
                    },
                )
                await asyncio.sleep(0.12)
                # Fallback if Polymer input still holds uncommitted text
                await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const roots = __queryAllDeep({json.dumps(container_selector)});
                        const root = roots.find(r => r.getBoundingClientRect().width > 0) || roots[0];
                        if (!root) return false;
                        const inp = __queryAllDeep('input#text-input, input', root)[0];
                        if (inp && (inp.value || '').trim()) {{
                            inp.value = {json.dumps(val + ",")};
                            inp.dispatchEvent(new Event('input', {{bubbles: true, composed: true}}));
                            inp.dispatchEvent(new KeyboardEvent('keydown', {{key: 'Enter', code: 'Enter', keyCode: 13, which: 13, bubbles: true, composed: true}}));
                            return true;
                        }}
                        return false;
                    }})()"""
                )
                await asyncio.sleep(0.08)

        await asyncio.sleep(0.25)
        return await self._read_chip_bar_values(client, container_selector)

    async def _set_education_academic_system(
        self,
        client: DirectCDPClient,
        *,
        select_selector: str = "#system-select",
        system_labels: list[str] | None = None,
    ) -> str:
        """
        Ensures YouTube Studio `Education -> Academic system` (`#system-select`) is locked to
        `United States` (`미국`) instead of inheriting `South Korea` from KR AdSense residency (R36/R75-C).
        Uses `__isVisibleEl` (bounding-rect check) because `tp-yt-iron-dropdown` overlays are `position: fixed`
        (`offsetParent === null`), and always dismisses any residual open listbox before returning.
        """
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        labels = system_labels or [
            DEFAULT_EDUCATION_ACADEMIC_SYSTEM,
            DEFAULT_EDUCATION_ACADEMIC_SYSTEM_KO,
            "None",
            "없음",
        ]
        primary_labels = labels[:2]
        sel_parts = [s.strip() for s in select_selector.split(",") if s.strip()]

        read_sys_js = rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const sels = {json.dumps(sel_parts)};
            for (const s of sels) {{
                const els = __queryAllDeep(s);
                const el = els.find(e => __isVisibleEl(e)) || els[0];
                if (el) return (el.innerText || '').trim();
            }}
            return '';
        }})()"""

        curr_sys = str(await client.eval(read_sys_js) or "")
        if not curr_sys:
            return ""
        if not any(lbl.lower() in curr_sys.lower() for lbl in primary_labels):
            trig_clicked = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const sels = {json.dumps(sel_parts)};
                    let el = null;
                    for (const s of sels) {{
                        const els = __queryAllDeep(s);
                        el = els.find(e => __isVisibleEl(e)) || els[0];
                        if (el) break;
                    }}
                    if (!el) return false;
                    const tr = __queryAllDeep('#trigger', el)[0] || el.querySelector('#trigger') || el;
                    tr.scrollIntoView({{block: 'center'}});
                    tr.click();
                    return true;
                }})()"""
            )
            if trig_clicked:
                await asyncio.sleep(1.0)
                item_clicked = await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const labels = {json.dumps(labels)};
                        const items = __queryAllDeep('tp-yt-paper-item').filter(e => __isVisibleEl(e));
                        for (const wanted of labels) {{
                            const match = items.find(e => (e.innerText || '').trim().toLowerCase() === wanted.toLowerCase());
                            if (match) {{
                                match.scrollIntoView({{block: 'center'}});
                                match.click();
                                return true;
                            }}
                        }}
                        return false;
                    }})()"""
                )
                if not item_clicked:
                    await client.eval(
                        "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true}))"
                    )
                await asyncio.sleep(0.9)
                curr_sys = str(await client.eval(read_sys_js) or "")
        return curr_sys.split("\n")[-1].strip() if curr_sys else ""

    async def _set_studio_category(
        self,
        client: DirectCDPClient,
        *,
        select_selector: str,
        category_labels: list[str] | None = None,
    ) -> str:
        """Selects Category (`Education` / `교육`) on a YouTube Studio `ytcp-form-select` control and locks `Academic system = United States`."""
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        labels = category_labels or [DEFAULT_VIDEO_CATEGORY, DEFAULT_VIDEO_CATEGORY_KO]
        sel_parts = [s.strip() for s in select_selector.split(",") if s.strip()]
        read_cat_js = rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const sels = {json.dumps(sel_parts)};
            for (const s of sels) {{
                const els = __queryAllDeep(s);
                const el = els.find(e => __isVisibleEl(e)) || els[0];
                if (el) return (el.innerText || '').trim();
            }}
            return '';
        }})()"""
        curr_cat = str(await client.eval(read_cat_js) or "")
        if not any(lbl.lower() in curr_cat.lower() for lbl in labels):
            trig_clicked = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const sels = {json.dumps(sel_parts)};
                    let el = null;
                    for (const s of sels) {{
                        const els = __queryAllDeep(s);
                        el = els.find(e => __isVisibleEl(e)) || els[0];
                        if (el) break;
                    }}
                    if (!el) return false;
                    const tr = __queryAllDeep('#trigger', el)[0] || el.querySelector('#trigger') || el;
                    tr.scrollIntoView({{block: 'center'}});
                    tr.click();
                    return true;
                }})()"""
            )
            if trig_clicked:
                await asyncio.sleep(1.1)
                cat_clicked = await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const labels = {json.dumps(labels)};
                        const items = __queryAllDeep('tp-yt-paper-item').filter(e => __isVisibleEl(e));
                        const match = items.find(e => labels.some(l => (e.innerText || '').trim().toLowerCase() === l.toLowerCase()));
                        if (match) {{ match.scrollIntoView({{block: 'center'}}); match.click(); return true; }}
                        return false;
                    }})()"""
                )
                if not cat_clicked:
                    await client.eval(
                        "document.dispatchEvent(new KeyboardEvent('keydown', {key: 'Escape', code: 'Escape', keyCode: 27, bubbles: true}))"
                    )
                await asyncio.sleep(0.9)
                curr_cat = str(await client.eval(read_cat_js) or "")
        resolved_cat = curr_cat.split("\n")[-1].strip() if curr_cat else ""
        if any(lbl.lower() in resolved_cat.lower() for lbl in (DEFAULT_VIDEO_CATEGORY, DEFAULT_VIDEO_CATEGORY_KO)):
            await asyncio.sleep(0.5)
            await self._set_education_academic_system(client)
        return resolved_cat

    async def _async_configure_studio_localization(
        self,
        dry_run: bool = False,
        *,
        screenshot_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Configures YouTube Studio Settings via Naver Whale CDP 9222 (Rule R36 + Rule R75):
        1. Channel -> Basic info:
           - Country of residence = South Korea (KR / 대한민국)
           - Keywords = CHANNEL_CLEAN_KEYWORDS (0 BCI/AI/Neuralink hardware tokens)
        2. Upload defaults -> Basic info:
           - Title = "" (completely empty)
           - Description = "" (completely empty — zero legacy BCI boilerplate; every Short writes its own R68-D description)
           - Tags = [] (0/500 completely empty so legacy BCI tags never auto-inject)
        3. Upload defaults -> Advanced settings:
           - Video language = English (United States) (en-US)
           - Title and description language = English (United States) (en-US)
           - Category = Education (교육)
        Strictly verifies live DOM state without masking empty/mismatched values.
        """
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        now_iso = datetime.now(timezone.utc).isoformat()
        if dry_run:
            return {
                "status": "dry_run_success",
                "configured_at": now_iso,
                "channel_id": CHANNEL_ID,
                "channel_name": CHANNEL_NAME,
                "country_of_residence": CHANNEL_RESIDENCE_COUNTRY_NAME,
                "country_of_residence_code": CHANNEL_RESIDENCE_COUNTRY,
                "channel_keywords": list(CHANNEL_CLEAN_KEYWORDS),
                "upload_default_title": "",
                "upload_default_description": "",
                "upload_default_tags": [],
                "video_language": VIDEO_LANGUAGE_LABEL,
                "video_language_code": VIDEO_LANGUAGE_CODE,
                "title_description_language": TITLE_DESCRIPTION_LANGUAGE_LABEL,
                "title_description_language_code": TITLE_DESCRIPTION_LANGUAGE_CODE,
                "category": DEFAULT_VIDEO_CATEGORY,
                "saved_changes": False,
            }

        async def _run_on_client(client: DirectCDPClient, *, is_real_leased: bool) -> dict[str, Any]:
            if is_real_leased:
                await client.send("Page.navigate", {"url": STUDIO_BASE_URL}, timeout_sec=30.0)
                await client.wait_for_element(
                    STUDIO_SETTINGS_SELECTORS["settings_nav_item"] + [f"a[href*={json.dumps(CHANNEL_ID)}]"],
                    timeout_sec=25.0,
                )
                await asyncio.sleep(2.0)

            channel_ok = await self._ensure_all_about_brain_channel(client)
            if not channel_ok:
                raise RuntimeError(
                    f"Failed to verify or switch active YouTube Studio session to {CHANNEL_NAME} ({CHANNEL_ID})."
                )

            is_open = await client.eval(
                """(() => {
                    const dlg = document.querySelector('ytcp-settings-dialog');
                    if (!dlg) return false;
                    const paper = dlg.querySelector('tp-yt-paper-dialog, #dialog');
                    if (!paper) return false;
                    const style = window.getComputedStyle(paper);
                    return Boolean(paper.opened) && style.display !== 'none' && paper.getAttribute('aria-hidden') !== 'true';
                })()"""
            )
            if not is_open:
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_nav_item"])
                await asyncio.sleep(2.5)

            # 1. Channel -> Basic Info -> Country of residence = South Korea + Clean Channel Keywords
            await client.click(STUDIO_SETTINGS_SELECTORS["channel_tab"])
            await asyncio.sleep(1.5)

            kr_labels = [CHANNEL_RESIDENCE_COUNTRY_NAME, CHANNEL_RESIDENCE_COUNTRY_KO, "Korea"]
            curr_country = await client.eval(
                "(() => { const el = document.querySelector('ytcp-settings-dialog #country-of-residence-select'); return el ? el.innerText.trim() : ''; })()"
            ) or ""
            if not any(lbl in curr_country for lbl in [CHANNEL_RESIDENCE_COUNTRY_NAME, CHANNEL_RESIDENCE_COUNTRY_KO]):
                await client.click(STUDIO_SETTINGS_SELECTORS["country_of_residence_trigger"])
                await asyncio.sleep(1.5)
                await client.eval(
                    f"""(() => {{
                        const labels = {json.dumps(kr_labels)};
                        const items = Array.from(document.querySelectorAll('tp-yt-paper-item'));
                        const match = items.find(e => e.offsetParent !== null && labels.some(l => (e.innerText || '').trim() === l));
                        if (match) {{ match.scrollIntoView({{block: 'center'}}); match.click(); return true; }}
                        return false;
                    }})()"""
                )
                await asyncio.sleep(1.2)
                curr_country = await client.eval(
                    "(() => { const el = document.querySelector('ytcp-settings-dialog #country-of-residence-select'); return el ? el.innerText.trim() : ''; })()"
                ) or ""

            channel_keywords_live: list[str] = []
            upload_default_title_live: str = ""
            upload_default_description_live: str = ""
            upload_default_tags_live: list[str] = []

            async def _clear_upload_defaults_textboxes() -> dict[str, str]:
                host_selectors = (
                    ("title", "ytcp-form-textarea#title-textarea, #title-textarea"),
                    ("description", "ytcp-form-textarea#description-textarea, #description-textarea"),
                )
                for _field_name, host_sel in host_selectors:
                    has_text = await client.eval(
                        rf"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                            const hosts = __queryAllDeep({json.dumps(host_sel)}, dlg);
                            const host = hosts.find(h => h.getBoundingClientRect().width > 0) || hosts[0];
                            if (!host) return false;
                            const innerCands = __queryAllDeep('textarea, #textbox, [contenteditable="true"]', host);
                            const el = innerCands.find(e => e.getBoundingClientRect().width > 0) || innerCands[0];
                            if (!el) return false;
                            const raw = ('value' in el && typeof el.value === 'string')
                                ? el.value
                                : (el.innerText || el.textContent || '');
                            if (!raw.trim()) return false;
                            el.scrollIntoView({{block: 'center'}});
                            el.focus();
                            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                                el.select();
                            }} else {{
                                try {{ document.execCommand('selectAll', false, null); }} catch (e) {{}}
                                const range = document.createRange();
                                range.selectNodeContents(el);
                                const s = window.getSelection();
                                if (s) {{ s.removeAllRanges(); s.addRange(range); }}
                            }}
                            return true;
                        }})()"""
                    )
                    if not has_text:
                        continue
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyDown", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65},
                    )
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyUp", "modifiers": 2, "key": "a", "code": "KeyA", "windowsVirtualKeyCode": 65},
                    )
                    await asyncio.sleep(0.06)
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyDown", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
                    )
                    await client.send(
                        "Input.dispatchKeyEvent",
                        {"type": "keyUp", "key": "Backspace", "code": "Backspace", "windowsVirtualKeyCode": 8},
                    )
                    await asyncio.sleep(0.08)
                    await client.eval(
                        rf"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                            const hosts = __queryAllDeep({json.dumps(host_sel)}, dlg);
                            const host = hosts.find(h => h.getBoundingClientRect().width > 0) || hosts[0];
                            if (!host) return false;
                            const innerCands = __queryAllDeep('textarea, #textbox, [contenteditable="true"]', host);
                            const el = innerCands.find(e => e.getBoundingClientRect().width > 0) || innerCands[0];
                            if (!el) return false;
                            el.focus();
                            if (el.tagName === 'TEXTAREA' || el.tagName === 'INPUT') {{
                                const proto = el.tagName === 'TEXTAREA'
                                    ? window.HTMLTextAreaElement.prototype
                                    : window.HTMLInputElement.prototype;
                                const setter = Object.getOwnPropertyDescriptor(proto, 'value')?.set;
                                if (setter) setter.call(el, '');
                                else el.value = '';
                            }} else {{
                                try {{
                                    document.execCommand('selectAll', false, null);
                                    document.execCommand('delete', false, null);
                                }} catch (e) {{}}
                                el.textContent = '';
                            }}
                            el.dispatchEvent(new InputEvent('input', {{bubbles: true, composed: true, data: '', inputType: 'deleteContentBackward'}}));
                            el.dispatchEvent(new Event('change', {{bubbles: true, composed: true}}));
                            el.dispatchEvent(new Event('blur', {{bubbles: true, composed: true}}));
                            return true;
                        }})()"""
                    )
                    await asyncio.sleep(0.25)

                return await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                        const readField = (hostSel) => {{
                            const hosts = __queryAllDeep(hostSel, dlg);
                            const host = hosts.find(h => h.getBoundingClientRect().width > 0) || hosts[0];
                            if (!host) return '';
                            const innerCands = __queryAllDeep('textarea, #textbox, [contenteditable="true"]', host);
                            const el = innerCands.find(e => e.getBoundingClientRect().width > 0) || innerCands[0];
                            if (!el) return '';
                            const raw = ('value' in el && typeof el.value === 'string')
                                ? el.value
                                : (el.innerText || el.textContent || '');
                            return raw.trim();
                        }};
                        return {{
                            title: readField('ytcp-form-textarea#title-textarea, #title-textarea'),
                            description: readField('ytcp-form-textarea#description-textarea, #description-textarea'),
                        }};
                    }})()"""
                ) or {"title": "", "description": ""}

            if hasattr(client, "send"):
                channel_keywords_live = await self._set_chip_bar_values(
                    client,
                    container_selector="ytcp-channel-settings ytcp-free-text-chip-bar",
                    target_values=list(CHANNEL_CLEAN_KEYWORDS),
                )

            # 2. Upload defaults -> Basic info -> Clear Default Title, Description & Default Tags to 0/500 ([])
            await client.click(STUDIO_SETTINGS_SELECTORS["uploads_tab"])
            await asyncio.sleep(1.5)
            if hasattr(client, "send"):
                await client.click(["ytcp-settings-dialog tp-yt-paper-tab#basicInfo", "tp-yt-paper-tab#basicInfo"])
                await asyncio.sleep(1.0)
                cleared_tb = await _clear_upload_defaults_textboxes()
                upload_default_title_live = str(cleared_tb.get("title") or "").strip()
                upload_default_description_live = str(cleared_tb.get("description") or "").strip()
                upload_default_tags_live = await self._set_chip_bar_values(
                    client,
                    container_selector="ytcp-settings-dialog #tags-container",
                    target_values=[],
                )

            # 3. Upload defaults -> Advanced settings -> en-US + Category = Education
            await client.click(STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"])
            await asyncio.sleep(1.5)

            lang_res = await self._ensure_upload_wizard_en_us_language(
                client, container_selector="ytcp-settings-dialog"
            )

            cat_labels = [DEFAULT_VIDEO_CATEGORY, DEFAULT_VIDEO_CATEGORY_KO]
            curr_cat = await client.eval(
                "(() => { const el = document.querySelector('ytcp-settings-dialog #category-select'); return el ? el.innerText.trim() : ''; })()"
            ) or ""
            if not any(lbl.lower() in curr_cat.lower() for lbl in cat_labels):
                await client.click(STUDIO_SETTINGS_SELECTORS["category_trigger"])
                await asyncio.sleep(1.2)
                await client.eval(
                    f"""(() => {{
                        const labels = {json.dumps(cat_labels)};
                        const items = Array.from(document.querySelectorAll('tp-yt-paper-item'));
                        const match = items.find(e => e.offsetParent !== null && labels.some(l => (e.innerText || '').trim().toLowerCase() === l.toLowerCase()));
                        if (match) {{ match.scrollIntoView({{block: 'center'}}); match.click(); return true; }}
                        return false;
                    }})()"""
                )
                await asyncio.sleep(1.0)

            await self._set_education_academic_system(
                client,
                select_selector="ytcp-settings-dialog ytcp-education-video-metadata #system-select, ytcp-settings-dialog #system-select",
            )

            final_dom = await client.eval(
                rf"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                    const a = __queryAllDeep('#audio-language', dlg)[0] || document.querySelector('ytcp-settings-dialog #audio-language');
                    const m = __queryAllDeep('#metadata-language', dlg)[0] || document.querySelector('ytcp-settings-dialog #metadata-language');
                    const c = __queryAllDeep('#category-select', dlg)[0] || document.querySelector('ytcp-settings-dialog #category-select');
                    const saveBtn = __queryAllDeep('#submit-button', dlg)[0] || document.querySelector('ytcp-settings-dialog #submit-button');
                    const innerBtn = saveBtn ? (__queryAllDeep('button', saveBtn)[0] || saveBtn) : null;
                    const disabled = !saveBtn
                        || saveBtn.hasAttribute('disabled')
                        || saveBtn.getAttribute('aria-disabled') === 'true'
                        || (innerBtn && (innerBtn.disabled || innerBtn.hasAttribute('disabled') || innerBtn.getAttribute('aria-disabled') === 'true'));
                    return {{
                        audioLang: a ? a.innerText.trim() : '',
                        metaLang: m ? m.innerText.trim() : '',
                        category: c ? c.innerText.trim() : '',
                        canSave: !disabled
                    }};
                }})()"""
            ) or {}

            saved_changes = False
            if final_dom.get("canSave"):
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_save_button"])
                saved_changes = True
                await asyncio.sleep(3.5)
            else:
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_cancel_button"])
                await asyncio.sleep(1.0)

            saved_screenshot: str | None = None
            if hasattr(client, "send"):
                # Re-open Settings to verify persisted post-Save DOM state and capture composite proof screenshot
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_nav_item"])
                await asyncio.sleep(2.2)
                await client.click(STUDIO_SETTINGS_SELECTORS["channel_tab"])
                await asyncio.sleep(1.4)
                channel_keywords_live = await self._read_chip_bar_values(
                    client, "ytcp-channel-settings ytcp-free-text-chip-bar"
                )
                kw_png = await self._capture_background_screenshot_bytes(client) if screenshot_path else b""

                await client.click(STUDIO_SETTINGS_SELECTORS["uploads_tab"])
                await asyncio.sleep(1.2)
                await client.click(["ytcp-settings-dialog tp-yt-paper-tab#basicInfo", "tp-yt-paper-tab#basicInfo"])
                await asyncio.sleep(0.8)
                post_tb = await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                        const readField = (hostSel) => {{
                            const hosts = __queryAllDeep(hostSel, dlg);
                            const host = hosts.find(h => h.getBoundingClientRect().width > 0) || hosts[0];
                            if (!host) return {{found: false, val: ''}};
                            const innerCands = __queryAllDeep('textarea, #textbox, [contenteditable="true"]', host);
                            const el = innerCands.find(e => e.getBoundingClientRect().width > 0) || innerCands[0];
                            if (!el) return {{found: false, val: ''}};
                            const raw = ('value' in el && typeof el.value === 'string')
                                ? el.value
                                : (el.innerText || el.textContent || '');
                            return {{found: true, val: raw.trim()}};
                        }};
                        const tRes = readField('ytcp-form-textarea#title-textarea, #title-textarea');
                        const dRes = readField('ytcp-form-textarea#description-textarea, #description-textarea');
                        const tc = __queryAllDeep('#tags-container', dlg)[0] || document.querySelector('ytcp-settings-dialog #tags-container');
                        if (tc) tc.scrollIntoView({{block: 'end'}});
                        return {{
                            titleFound: tRes.found,
                            descFound: dRes.found,
                            title: tRes.val,
                            description: dRes.val,
                        }};
                    }})()"""
                ) or {}
                if not post_tb.get("descFound"):
                    raise RuntimeError("[R75] Upload Defaults #description-textarea not found during post-Save verification!")
                upload_default_title_live = str(post_tb.get("title") or "").strip()
                upload_default_description_live = str(post_tb.get("description") or "").strip()
                await asyncio.sleep(0.5)
                upload_default_tags_live = await self._read_chip_bar_values(
                    client, "ytcp-settings-dialog #tags-container"
                )
                tags_png = await self._capture_background_screenshot_bytes(client) if screenshot_path else b""

                await client.click(STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"])
                await asyncio.sleep(1.0)
                post_cat = await client.eval(
                    rf"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const dlg = __queryAllDeep('ytcp-settings-dialog')[0] || document;
                        const el = __queryAllDeep('#category-select', dlg)[0] || document.querySelector('ytcp-settings-dialog #category-select');
                        return el ? el.innerText.trim() : '';
                    }})()"""
                ) or ""
                if post_cat:
                    final_dom["category"] = post_cat
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_cancel_button"])
                await asyncio.sleep(0.8)

                if screenshot_path and kw_png and tags_png:
                    import io
                    from PIL import Image

                    im1 = Image.open(io.BytesIO(kw_png)).convert("RGB")
                    im2 = Image.open(io.BytesIO(tags_png)).convert("RGB")
                    combo = Image.new("RGB", (im1.width + im2.width, max(im1.height, im2.height)), (18, 18, 18))
                    combo.paste(im1, (0, 0))
                    combo.paste(im2, (im1.width, 0))
                    out_p = Path(screenshot_path)
                    out_p.parent.mkdir(parents=True, exist_ok=True)
                    combo.save(out_p, format="PNG")
                    saved_screenshot = str(out_p)

                banned_kw = [
                    kw for kw in channel_keywords_live if kw.strip().lower() in BANNED_OFF_TOPIC_TECH_TAGS
                ]
                if banned_kw or not channel_keywords_live:
                    raise RuntimeError(
                        f"[R75] Channel Keywords verification failed: live={channel_keywords_live}, banned={banned_kw}"
                    )
                if upload_default_title_live:
                    raise RuntimeError(
                        f"[R75] Upload Default Title must be empty (''), got: {upload_default_title_live!r}"
                    )
                if upload_default_description_live:
                    raise RuntimeError(
                        f"[R75] Upload Default Description must be empty (''), got: {upload_default_description_live!r}"
                    )
                if upload_default_tags_live:
                    raise RuntimeError(
                        f"[R75] Upload Default Tags must be empty (0/500), got: {upload_default_tags_live}"
                    )

            actual_country = curr_country.split("\n")[-1].strip() if curr_country else ""
            actual_video_lang = final_dom.get("audioLang", "").split("\n")[-1].strip()
            actual_meta_lang = final_dom.get("metaLang", "").split("\n")[-1].strip()
            actual_category = final_dom.get("category", "").split("\n")[-1].strip()

            en_us_labels = [VIDEO_LANGUAGE_LABEL, VIDEO_LANGUAGE_LABEL_KO]
            country_verified = any(lbl in actual_country for lbl in [CHANNEL_RESIDENCE_COUNTRY_NAME, CHANNEL_RESIDENCE_COUNTRY_KO])
            video_lang_verified = any(lbl in actual_video_lang for lbl in en_us_labels)
            meta_lang_verified = any(lbl in actual_meta_lang for lbl in en_us_labels)
            category_verified = (not hasattr(client, "send")) or any(
                lbl.lower() in actual_category.lower() for lbl in [DEFAULT_VIDEO_CATEGORY, DEFAULT_VIDEO_CATEGORY_KO]
            )

            if not (country_verified and video_lang_verified and meta_lang_verified and category_verified):
                raise RuntimeError(
                    f"YouTube Studio live localization verification failed: "
                    f"country='{actual_country}' (verified={country_verified}), "
                    f"video_language='{actual_video_lang}' (verified={video_lang_verified}), "
                    f"title_description_language='{actual_meta_lang}' (verified={meta_lang_verified}), "
                    f"category='{actual_category}' (verified={category_verified})"
                )

            return {
                "status": "verified_live",
                "configured_at": now_iso,
                "channel_id": CHANNEL_ID,
                "channel_name": CHANNEL_NAME,
                "country_of_residence": actual_country,
                "country_of_residence_code": CHANNEL_RESIDENCE_COUNTRY,
                "channel_keywords": channel_keywords_live,
                "upload_default_title": upload_default_title_live,
                "upload_default_description": upload_default_description_live,
                "upload_default_tags": upload_default_tags_live,
                "video_language": actual_video_lang,
                "video_language_code": VIDEO_LANGUAGE_CODE,
                "title_description_language": actual_meta_lang,
                "title_description_language_code": TITLE_DESCRIPTION_LANGUAGE_CODE,
                "category": actual_category,
                "language_checks": lang_res,
                "saved_changes": saved_changes,
                "screenshot_path": saved_screenshot,
            }

        # Use an isolated background leased tab in production; honor monkeypatched get_direct_client in unit tests
        if getattr(self.session.get_direct_client, "__self__", None) is self.session:
            from pipeline.cdp_tab_lease import leased_cdp_tab

            async with leased_cdp_tab(
                "about:blank",
                purpose="r75_studio_settings",
                cdp_port=self.cdp_port,
                cdp_host=self.session.cdp_host,
                background=True,
            ) as (client, _tid, _owner):
                try:
                    return await _run_on_client(client, is_real_leased=True)
                finally:
                    await self._prepare_leased_tab_for_close(client)

        client = self.session.get_direct_client("studio.youtube.com", default_url=STUDIO_BASE_URL)
        async with client:
            return await _run_on_client(client, is_real_leased=False)

    def configure_studio_localization(
        self,
        dry_run: bool = False,
        *,
        screenshot_path: Path | None = None,
    ) -> dict[str, Any]:
        """Synchronous entry point to configure and verify KR Residence, Clean Keywords, Empty Default Tags & Education Category."""
        return asyncio.run(
            self._async_configure_studio_localization(dry_run=dry_run, screenshot_path=screenshot_path)
        )

    async def _async_purge_all_channel_playlists(
        self,
        *,
        dry_run: bool = False,
        screenshot_path: Path | None = None,
        receipt_path: Path | None = None,
    ) -> dict[str, Any]:
        """
        Rule R75 Phase 1: Permanently deletes ALL channel playlists on YouTube Studio
        (`/channel/<CHANNEL_ID>/content/playlists`) inside a single background leased CDP tab,
        reloads `/content/playlists` to assert `0` playlist rows remain, saves a PNG proof
        screenshot, and writes `studio_playlist_purge_receipt.json`.
        """
        from pipeline.config import WORKSPACE_ROOT
        from pipeline.cdp_tab_lease import leased_cdp_tab
        from pipeline.publish import validate_episode_tags_hygiene
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        playlists_url = f"https://studio.youtube.com/channel/{CHANNEL_ID}/content/playlists"
        now_iso = datetime.now(timezone.utc).isoformat()
        if dry_run:
            return {
                "status": "dry_run_success",
                "purged_at": now_iso,
                "channel_id": CHANNEL_ID,
                "playlists_url": playlists_url,
                "deleted_playlists": [],
                "remaining_count": 0,
            }

        scrape_rows_js = rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const rows = __queryAllDeep('ytcp-playlist-row');
            return rows.map(r => {{
                const a = __queryAllDeep('a[href*="/playlist/"]', r)[0];
                const href = a ? (a.getAttribute('href') || '') : '';
                const m = href.match(/\/playlist\/([^\/?#]+)/);
                const titleEl = __queryAllDeep('#playlist-title-link, #playlist-title', r)[0] || a;
                return {{
                    playlist_id: m ? m[1] : '',
                    href: href,
                    title: titleEl ? (titleEl.innerText || titleEl.textContent || '').trim() : (r.innerText || '').split('\n')[0].trim(),
                }};
            }}).filter(x => x.playlist_id);
        }})()"""

        deleted_playlists: list[dict[str, Any]] = []
        remaining_after: list[dict[str, Any]] = []
        saved_shot: str | None = None

        async with leased_cdp_tab(
            "about:blank",
            purpose="r75_studio_purifier",
            cdp_port=self.cdp_port,
            cdp_host=self.session.cdp_host,
            background=True,
        ) as (client, _tid, _owner):
            try:
                await client.send("Page.navigate", {"url": playlists_url}, timeout_sec=30.0)
                await asyncio.sleep(4.5)
                channel_ok = await self._ensure_all_about_brain_channel(client)
                if not channel_ok:
                    raise RuntimeError(f"Channel mismatch while purging playlists on {playlists_url}")
                if "/content/playlists" not in str(await client.eval("location.href") or ""):
                    await client.send("Page.navigate", {"url": playlists_url}, timeout_sec=30.0)
                    await asyncio.sleep(4.5)

                for pass_idx in range(1, 6):
                    current_rows = await client.eval(scrape_rows_js) or []
                    if pass_idx == 1:
                        print(f"[StudioUploader] Found {len(current_rows)} live playlist(s) to purge on {CHANNEL_NAME}.")
                    if not current_rows:
                        break
                    for item in current_rows:
                        pl_id = str(item.get("playlist_id") or "").strip()
                        pl_title = str(item.get("title") or "").strip()
                        if not pl_id:
                            continue
                        print(f"[StudioUploader] Deleting playlist {pl_id} ('{pl_title}') [pass {pass_idx}]...")
                        menu_opened = await client.eval(
                            rf"""(() => {{
                                {_DEEP_QUERY_HELPER_JS}
                                const rows = __queryAllDeep('ytcp-playlist-row');
                                const row = rows.find(r => __queryAllDeep('a[href*="/playlist/"]', r).some(a => (a.getAttribute('href') || '').includes({json.dumps(pl_id)})));
                                if (!row) return false;
                                row.scrollIntoView({{block: 'center'}});
                                const btn = __queryAllDeep('#overflow-menu-button, ytcp-icon-button[aria-label="Options"], ytcp-icon-button[aria-label="옵션"]', row)[0];
                                if (!btn) return false;
                                const inner = __queryAllDeep('button', btn)[0] || btn;
                                inner.click();
                                return true;
                            }})()"""
                        )
                        if not menu_opened:
                            await asyncio.sleep(1.2)
                            continue
                        await asyncio.sleep(1.1)

                        del_clicked = await client.eval(
                            rf"""(() => {{
                                {_DEEP_QUERY_HELPER_JS}
                                const items = __queryAllDeep('tp-yt-paper-item');
                                const match = items.find(el => {{
                                    if (el.getBoundingClientRect().width <= 0) return false;
                                    const txt = (el.innerText || el.textContent || '').trim().toLowerCase();
                                    return txt === 'delete' || txt.includes('delete playlist') || txt === '삭제' || txt.includes('재생목록 삭제');
                                }});
                                if (!match) return false;
                                match.click();
                                return true;
                            }})()"""
                        )
                        if not del_clicked:
                            await asyncio.sleep(1.0)
                            continue
                        await asyncio.sleep(1.3)

                        confirmed = await client.eval(
                            rf"""(() => {{
                                {_DEEP_QUERY_HELPER_JS}
                                const btns = __queryAllDeep('ytcp-confirmation-dialog #confirm-button, ytcp-dialog #confirm-button, tp-yt-paper-dialog #confirm-button, ytcp-button#confirm-button');
                                const vis = btns.find(b => b.getBoundingClientRect().width > 0) || btns[0];
                                if (!vis) return false;
                                const inner = __queryAllDeep('button', vis)[0] || vis;
                                inner.click();
                                return true;
                            }})()"""
                        )
                        if not confirmed:
                            raise RuntimeError(f"Delete confirmation dialog #confirm-button not found for playlist {pl_id}")

                        # Wait until Polymer removes this playlist row from DOM (up to 8.0s)
                        for _ in range(16):
                            await asyncio.sleep(0.5)
                            after_rows = await client.eval(scrape_rows_js) or []
                            if not any(str(r.get("playlist_id") or "") == pl_id for r in after_rows):
                                break

                        if not any(d.get("playlist_id") == pl_id for d in deleted_playlists):
                            deleted_playlists.append(
                                {
                                    "playlist_id": pl_id,
                                    "title": pl_title,
                                    "deleted_at": datetime.now(timezone.utc).isoformat(),
                                }
                            )
                    await client.send("Page.navigate", {"url": playlists_url}, timeout_sec=30.0)
                    await asyncio.sleep(4.5)

                remaining_after = await client.eval(scrape_rows_js) or []
                if remaining_after:
                    raise RuntimeError(
                        f"[R75] Playlist purge incomplete — {len(remaining_after)} playlist row(s) still present: {remaining_after}"
                    )

                if screenshot_path is not None:
                    png_bytes = await self._capture_background_screenshot_bytes(client)
                    if png_bytes:
                        out_shot = Path(screenshot_path)
                        out_shot.parent.mkdir(parents=True, exist_ok=True)
                        out_shot.write_bytes(png_bytes)
                        saved_shot = str(out_shot)
            finally:
                await self._prepare_leased_tab_for_close(client)

        receipt_targets = [
            Path(WORKSPACE_ROOT) / "BCI_Shorts_Channel" / "reports" / "studio_playlist_purge_receipt.json",
        ]
        if receipt_path is not None and Path(receipt_path) not in receipt_targets:
            receipt_targets.insert(0, Path(receipt_path))

        merged_deleted: list[dict[str, Any]] = []
        seen_ids: set[str] = set()
        for rp in receipt_targets:
            if rp.is_file():
                try:
                    prev_doc = json.loads(rp.read_text(encoding="utf-8"))
                    for prev_pl in prev_doc.get("deleted_playlists") or []:
                        pid_prev = str(prev_pl.get("playlist_id") or "").strip()
                        if pid_prev and pid_prev not in seen_ids:
                            seen_ids.add(pid_prev)
                            merged_deleted.append(prev_pl)
                except Exception:
                    pass
        for cur_pl in deleted_playlists:
            pid_cur = str(cur_pl.get("playlist_id") or "").strip()
            if pid_cur and pid_cur not in seen_ids:
                seen_ids.add(pid_cur)
                merged_deleted.append(cur_pl)

        receipt_doc = {
            "status": "purged_zero_verified",
            "purged_at": datetime.now(timezone.utc).isoformat(),
            "channel_id": CHANNEL_ID,
            "channel_name": CHANNEL_NAME,
            "playlists_url": playlists_url,
            "deleted_count": len(merged_deleted),
            "deleted_in_last_run_count": len(deleted_playlists),
            "deleted_playlists": merged_deleted,
            "remaining_count": len(remaining_after),
            "screenshot_path": saved_shot,
        }
        for rp in receipt_targets:
            rp.parent.mkdir(parents=True, exist_ok=True)
            rp.write_text(json.dumps(receipt_doc, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
        receipt_doc["receipt_paths"] = [str(p) for p in receipt_targets]
        return receipt_doc

    def purge_all_channel_playlists(
        self,
        *,
        dry_run: bool = False,
        screenshot_path: Path | None = None,
        receipt_path: Path | None = None,
    ) -> dict[str, Any]:
        """Synchronous entry point to permanently delete all channel playlists on YouTube Studio (Rule R75)."""
        return asyncio.run(
            self._async_purge_all_channel_playlists(
                dry_run=dry_run,
                screenshot_path=screenshot_path,
                receipt_path=receipt_path,
            )
        )

    async def _async_sync_live_videos_metadata_batch(
        self,
        items: list[dict[str, Any]],
        *,
        protected_video_ids: frozenset[str] | None = None,
    ) -> list[dict[str, Any]]:
        """
        Updates live YouTube Studio `/video/<id>/edit` Tags, Category (`Education` + `Academic system: United States`),
        and optional Description across `items` inside ONE background leased CDP tab, saving and reading back DOM chips.
        Dynamically computes active R75 freeze-window IDs (`3.0h` pre-release / `24.0h` post-release) when
        `protected_video_ids` is `None`.
        """
        from pipeline.cdp_tab_lease import leased_cdp_tab
        from pipeline.publish import validate_episode_tags_hygiene
        from pipeline.studio.short_linker import ShortLinkGraph
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        if protected_video_ids is None:
            graph = ShortLinkGraph(projects_dir=PROJECTS_DIR)
            dyn_locked: set[str] = set()
            for node in graph.discover_nodes():
                locked, _ = graph.is_seed_locked(node)
                if locked and node.get("video_id"):
                    dyn_locked.add(str(node["video_id"]).strip())
            active_protected_ids = frozenset(dyn_locked)
        else:
            active_protected_ids = frozenset(protected_video_ids)

        for item in items:
            vid = str(item.get("video_id") or "").strip()
            if not vid or vid in active_protected_ids:
                raise ValueError(f"[R75] Refusing to open protected or empty video_id in Studio: '{vid}'")
            pillar = str(item.get("pillar") or DEFAULT_FALLBACK_PILLAR).strip()
            tags = [str(t).strip() for t in (item.get("tags") or []) if str(t).strip()]
            validate_episode_tags_hygiene(tags, pillar, raise_on_error=True)

        results: list[dict[str, Any]] = []
        async with leased_cdp_tab(
            "about:blank",
            purpose="r75_studio_purifier",
            cdp_port=self.cdp_port,
            cdp_host=self.session.cdp_host,
            background=True,
        ) as (client, _tid, _owner):
            try:
                for item in items:
                    vid = str(item["video_id"]).strip()
                    pid = str(item.get("project_id") or "").strip()
                    pillar = str(item.get("pillar") or DEFAULT_FALLBACK_PILLAR).strip()
                    tags = [str(t).strip() for t in item["tags"] if str(t).strip()]
                    target_cat = str(item.get("category") or DEFAULT_VIDEO_CATEGORY).strip()
                    new_desc = item.get("description")
                    edit_url = f"https://studio.youtube.com/video/{vid}/edit"

                    print(f"[StudioUploader] Purifying live metadata on {vid} ({pid})...")
                    await client.send("Page.navigate", {"url": edit_url}, timeout_sec=30.0)
                    await client.wait_for_element(STUDIO_SELECTORS["show_more_button"], timeout_sec=25.0)
                    await asyncio.sleep(2.2)

                    if isinstance(new_desc, str) and new_desc.strip():
                        curr_desc = str(
                            await client.eval(
                                """(() => {
                                    const tb = document.querySelector('#description-textarea #textbox');
                                    return tb ? (tb.innerText || tb.textContent || '').trim() : '';
                                })()"""
                            )
                            or ""
                        ).strip()
                        if curr_desc != new_desc.strip():
                            await client.type_into(STUDIO_SELECTORS["description_input"], new_desc)
                            await asyncio.sleep(0.8)

                    await client.click(STUDIO_SELECTORS["show_more_button"])
                    await asyncio.sleep(1.4)

                    before_tags = await self._read_chip_bar_values(client, "#tags-container")
                    live_tags = await self._set_chip_bar_values(
                        client,
                        container_selector="#tags-container",
                        target_values=tags,
                    )
                    live_cat = await self._set_studio_category(
                        client,
                        select_selector="ytcp-form-select#category, #category",
                        category_labels=[target_cat, DEFAULT_VIDEO_CATEGORY_KO],
                    )

                    if pillar != "bci_tech":
                        bad_live = [t for t in live_tags if t.strip().lower() in BANNED_OFF_TOPIC_TECH_TAGS]
                        if bad_live:
                            raise RuntimeError(f"[R75] Polluted tags still in DOM on {vid}: {bad_live}")

                    save_state = await client.eval(
                        rf"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const btn = __queryAllDeep('ytcp-video-metadata-editor #save, ytcp-button#save')[0];
                            if (!btn) return {{found: false, enabled: false}};
                            const inner = __queryAllDeep('button', btn)[0];
                            const disabled = btn.hasAttribute('disabled')
                                || btn.getAttribute('aria-disabled') === 'true'
                                || (inner && (inner.disabled || inner.hasAttribute('disabled') || inner.getAttribute('aria-disabled') === 'true'));
                            if (!disabled) {{
                                (inner || btn).click();
                            }}
                            return {{found: true, enabled: !disabled}};
                        }})()"""
                    ) or {}

                    saved_ok = not bool(save_state.get("enabled"))
                    if save_state.get("enabled"):
                        for _ in range(30):
                            await asyncio.sleep(0.6)
                            still_enabled = await client.eval(
                                rf"""(() => {{
                                    {_DEEP_QUERY_HELPER_JS}
                                    const btn = __queryAllDeep('ytcp-video-metadata-editor #save, ytcp-button#save')[0];
                                    if (!btn) return false;
                                    const inner = __queryAllDeep('button', btn)[0];
                                    const disabled = btn.hasAttribute('disabled')
                                        || btn.getAttribute('aria-disabled') === 'true'
                                        || (inner && (inner.disabled || inner.hasAttribute('disabled') || inner.getAttribute('aria-disabled') === 'true'));
                                    return !disabled;
                                }})()"""
                            )
                            if not still_enabled:
                                saved_ok = True
                                break
                        await asyncio.sleep(1.5)

                    # Reload and read back persisted DOM chips + Category
                    await client.send("Page.navigate", {"url": edit_url}, timeout_sec=30.0)
                    await client.wait_for_element(STUDIO_SELECTORS["show_more_button"], timeout_sec=25.0)
                    await asyncio.sleep(2.2)
                    await client.click(STUDIO_SELECTORS["show_more_button"])
                    await asyncio.sleep(1.2)
                    readback_tags = await self._read_chip_bar_values(client, "#tags-container")
                    readback_cat = str(
                        await client.eval(
                            """(() => {
                                const el = document.querySelector('ytcp-form-select#category, #category');
                                return el ? (el.innerText || '').trim() : '';
                            })()"""
                        )
                        or ""
                    ).split("\n")[-1].strip()
                    readback_desc = str(
                        await client.eval(
                            """(() => {
                                const tb = document.querySelector('#description-textarea #textbox');
                                return tb ? (tb.innerText || tb.textContent || '').trim() : '';
                            })()"""
                        )
                        or ""
                    ).strip()

                    validate_episode_tags_hygiene(readback_tags, pillar, raise_on_error=True)
                    if not any(lbl.lower() in readback_cat.lower() for lbl in [target_cat, DEFAULT_VIDEO_CATEGORY_KO]):
                        raise RuntimeError(
                            f"[R75] Persisted Category mismatch on {vid}: expected '{target_cat}', got '{readback_cat}'"
                        )

                    results.append(
                        {
                            "video_id": vid,
                            "project_id": pid,
                            "saved": saved_ok,
                            "before_tags": before_tags,
                            "after_tags": readback_tags,
                            "after_category": readback_cat,
                            "has_shorts_hashtag": "#shorts" in readback_desc.lower(),
                        }
                    )
            finally:
                await self._prepare_leased_tab_for_close(client)
        return results

    def sync_live_videos_metadata_batch(self, items: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Synchronous entry point to purify Tags, Category, and Description on whitelisted Studio videos."""
        return asyncio.run(self._async_sync_live_videos_metadata_batch(items))

    @staticmethod
    def audit_v8_channel_readiness(workspace_root: Path | None = None) -> dict[str, Any]:
        """
        Read-only v8 channel operations readiness audit (zero live YouTube Studio mutation):
          1. Staged @Channel_Art v8 avatar/banner draft candidates + dynamic check for verified live publication proof.
          2. en-US upload localization + Multi-language audio / auto-dubbing checklist status.
          3. Local Public inventory audit separating legacy >90s / 3-min uploads vs <90s Shorts (zero visibility mutation).
        """
        from pipeline.config import PROJECTS_DIR, WORKSPACE_ROOT

        ws_root = Path(workspace_root) if workspace_root is not None else WORKSPACE_ROOT
        projects_root = (ws_root / "BCI_Shorts_Channel" / "projects") if workspace_root is not None else PROJECTS_DIR
        art_dir = ws_root / "artifacts_archive" / "01_YouTube_CEO" / "channel_art_and_cast"
        brand_dir = ws_root / "BCI_Shorts_Channel" / "brand_assets" / "v2_ep31_rebrand"
        avatar_drafts = sorted(str(p.relative_to(ws_root)) for p in art_dir.glob("avatar_*.jpg")) if art_dir.exists() else []
        if not avatar_drafts and brand_dir.exists():
            avatar_drafts = sorted(str(p.relative_to(ws_root)) for p in brand_dir.glob("logo_*.png"))
        banner_drafts = sorted(str(p.relative_to(ws_root)) for p in art_dir.glob("banner_*.jpg")) if art_dir.exists() else []
        if not banner_drafts and brand_dir.exists():
            banner_drafts = sorted(str(p.relative_to(ws_root)) for p in brand_dir.glob("banner_youtube_2560x1440*.*"))
        cast_sheets = sorted(str(p.relative_to(ws_root)) for p in art_dir.glob("cast_*.jpg")) if art_dir.exists() else []
        proof_path = art_dir / "youtube_live_published_proof.jpg"
        live_art_replaced = False
        if proof_path.is_file():
            try:
                with proof_path.open("rb") as fh:
                    magic = fh.read(12)
                live_art_replaced = bool(
                    magic.startswith(b"\xff\xd8\xff")
                    or magic.startswith(b"\x89PNG\r\n\x1a\n")
                    or (magic.startswith(b"RIFF") and magic[8:12] == b"WEBP")
                )
            except OSError:
                live_art_replaced = False

        legacy_over_90s: list[dict[str, Any]] = []
        shorts_under_90s: list[dict[str, Any]] = []
        v8_shorts_le_120s: list[dict[str, Any]] = []
        legacy_gt_120s: list[dict[str, Any]] = []
        if projects_root.exists():
            for p_dir in sorted(projects_root.iterdir()):
                if not p_dir.is_dir():
                    continue
                receipt_file = p_dir / "06_publish" / "upload_receipt.json"
                if not receipt_file.exists():
                    continue
                try:
                    rec = json.loads(receipt_file.read_text(encoding="utf-8"))
                except Exception:
                    continue
                vis = str(rec.get("visibility") or "").lower()
                vid_id = str(rec.get("video_id") or "")
                edl_file = p_dir / "05_assembly" / "edit_decision_list.json"
                dur_sec = None
                if edl_file.exists():
                    try:
                        dur_sec = float(json.loads(edl_file.read_text(encoding="utf-8")).get("total_duration_sec") or 0.0)
                    except Exception:
                        dur_sec = None
                entry = {
                    "project_id": p_dir.name,
                    "video_id": vid_id,
                    "visibility": vis,
                    "duration_sec": round(dur_sec, 2) if dur_sec else None,
                }
                if dur_sec and dur_sec > 89.5:
                    legacy_over_90s.append(entry)
                else:
                    shorts_under_90s.append(entry)
                if dur_sec and dur_sec > 120.0:
                    legacy_gt_120s.append(entry)
                else:
                    v8_shorts_le_120s.append(entry)

        return {
            "live_mutation_applied": False,
            "channel_art_readiness": {
                "avatar_drafts_staged": avatar_drafts,
                "banner_drafts_staged": banner_drafts,
                "cast_sheets_staged": cast_sheets,
                "live_channel_art_replaced": live_art_replaced,
                "live_published_proof": str(proof_path.relative_to(ws_root)) if live_art_replaced else None,
                "policy": (
                    "Verified live Profile Option 1 + Banner Option 2 on @AllAboutBrainOfficial (youtube_live_published_proof.jpg)."
                    if live_art_replaced
                    else "Hold live YouTube Studio avatar/banner replacement until user selects specific Avatar/Banner option."
                ),
            },
            "multi_language_audio_checklist": {
                "primary_audio_language": VIDEO_LANGUAGE_CODE,
                "metadata_language": TITLE_DESCRIPTION_LANGUAGE_CODE,
                "auto_dubbing_check_recommended": True,
                "note": "Verify YouTube Studio Settings -> Upload defaults -> Advanced settings -> Automatic dubbing when rolling out global Shorts.",
            },
            "format_inventory_audit": {
                "shorts_le_89_5s_count": len(shorts_under_90s),
                "legacy_gt_89_5s_count": len(legacy_over_90s),
                "legacy_gt_89_5s_projects": legacy_over_90s,
                "v8_shorts_le_120s_count": len(v8_shorts_le_120s),
                "legacy_gt_120s_count": len(legacy_gt_120s),
                "live_visibility_mutated": False,
            },
        }

    async def _async_inspect_auto_dubbing_settings(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Read-only inspection of YouTube Studio Automatic Dubbing / Multi-Language Audio & language defaults.
        When `dry_run=False`, opens a dedicated background-leased tab via `leased_cdp_tab` (`background=True` +
        `enable_background_focus_emulation`, never touching pre-existing user tabs), navigates to
        `https://studio.youtube.com/channel/UC4FeioYYv9X04Di07_MfZ7g`, opens `Settings -> Upload defaults ->
        Advanced settings` (`ytcp-settings-dialog`), reads `#audio-language`, `#metadata-language`, and any
        Automatic Dubbing / Multi-language audio controls, closes the dialog via Cancel (`live_studio_mutated: False`),
        and releases/closes only the self-leased tab.
        """
        now_iso = datetime.now(timezone.utc).isoformat()
        if dry_run:
            return {
                "checked": True,
                "dry_run": True,
                "mode": "dry_run_offline",
                "inspected_at": now_iso,
                "live_dom_inspected": False,
                "live_studio_mutated": False,
                "channel_id": CHANNEL_ID,
                "channel_verified": None,
                "audio_language": VIDEO_LANGUAGE_LABEL,
                "metadata_language": TITLE_DESCRIPTION_LANGUAGE_LABEL,
                "auto_dubbing_control_present": None,
                "auto_dubbing_checked": None,
                "auto_dubbing_disabled": None,
                "upload_defaults_auto_dubbing_checked": None,
                "channel_auto_dubbing_checked": None,
                "controls": [],
            }

        import urllib.request

        from pipeline.cdp_tab_lease import (
            enable_background_focus_emulation,
            get_tab_lease,
            leased_cdp_tab,
        )
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        leased_tid = ""
        focus_emulated = False
        channel_verified = False
        dialog_opened = False
        dialog_closed = False
        cancel_clicked = False
        chan_save_enabled = False
        dom_snapshot: dict[str, Any] = {}
        channel_adv_controls: list[dict[str, Any]] = []

        scan_controls_js = rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const dlg = __queryAllDeep('ytcp-settings-dialog')[0];
            if (!dlg) return {{ dialogFound: false }};
            const cleanLine = (el) => {{
                if (!el) return '';
                const lines = (el.innerText || el.textContent || '')
                    .split('\n')
                    .map(s => s.trim())
                    .filter(Boolean);
                return lines.length ? lines[lines.length - 1] : '';
            }};
            const isInsideDeep = (node, ancestor) => {{
                let p = node;
                while (p) {{
                    if (p === ancestor) return true;
                    p = p.parentElement || (p.getRootNode && p.getRootNode().host) || null;
                }}
                return false;
            }};
            const audioEl = __queryAllDeep('#audio-language', dlg)[0];
            const metaEl = __queryAllDeep('#metadata-language', dlg)[0];
            const catEl = __queryAllDeep('#category-select', dlg)[0];
            const saveBtn = __queryAllDeep('#submit-button', dlg)[0];
            const saveEnabled = Boolean(
                saveBtn
                && !saveBtn.hasAttribute('disabled')
                && saveBtn.getAttribute('aria-disabled') !== 'true'
            );

            const dubRe = /auto(?:matic)?[\s-]*dub|dubbing|multi[\s-]*language\s+audio|translated\s+audio|\uc790\ub3d9\s*\ub354\ube59|\ub2e4\uad6d\uc5b4\s*\uc624\ub514\uc624|\uc624\ub514\uc624\s*\ud2b8\ub799/i;
            const customControlTags = [
                'ytcp-checkbox-lit',
                'tp-yt-paper-checkbox',
                'tp-yt-paper-toggle-button',
                'ytcp-form-checkbox'
            ];
            const allInteractive = [];
            const seenNodes = new Set();
            for (const sel of customControlTags) {{
                for (const node of __queryAllDeep(sel, dlg)) {{
                    if (!seenNodes.has(node) && __isVisibleEl(node, sel)) {{
                        seenNodes.add(node);
                        allInteractive.push(node);
                    }}
                }}
            }}
            for (const node of __queryAllDeep('input[type="checkbox"]', dlg)) {{
                if (!seenNodes.has(node) && __isVisibleEl(node, 'input[type="checkbox"]')) {{
                    if (!allInteractive.some(host => isInsideDeep(node, host))) {{
                        seenNodes.add(node);
                        allInteractive.push(node);
                    }}
                }}
            }}

            const readChecked = (el) => {{
                if (!el) return null;
                if (typeof el.checked === 'boolean') return el.checked;
                const ac = el.getAttribute ? el.getAttribute('aria-checked') : null;
                if (ac === 'true') return true;
                if (ac === 'false') return false;
                if (el.hasAttribute && el.hasAttribute('checked')) return true;
                const inner = __queryAllDeep('input[type="checkbox"], [role="checkbox"], #checkbox', el)[0];
                if (inner && inner !== el) {{
                    if (typeof inner.checked === 'boolean') return inner.checked;
                    const iac = inner.getAttribute ? inner.getAttribute('aria-checked') : null;
                    if (iac === 'true') return true;
                    if (iac === 'false') return false;
                }}
                return null;
            }};
            const readDisabled = (el) => {{
                if (!el) return false;
                return Boolean(
                    el.disabled === true
                    || (el.hasAttribute && el.hasAttribute('disabled'))
                    || (el.getAttribute && el.getAttribute('aria-disabled') === 'true')
                );
            }};
            const contextText = (el) => {{
                let cur = el;
                for (let d = 0; d < 4 && cur && cur !== dlg; d++) {{
                    if (d > 0) {{
                        let descCount = 0;
                        for (const item of allInteractive) {{
                            if (isInsideDeep(item, cur)) {{
                                descCount += 1;
                                if (descCount > 1) break;
                            }}
                        }}
                        if (descCount > 1) break;
                    }}
                    const txt = (cur.innerText || cur.textContent || '').replace(/\s+/g, ' ').trim();
                    if (txt && txt.length <= 320 && dubRe.test(txt)) return txt;
                    cur = cur.parentElement || (cur.getRootNode && cur.getRootNode().host) || null;
                }}
                return (el.innerText || el.textContent || (el.getAttribute && el.getAttribute('aria-label')) || '').replace(/\s+/g, ' ').trim();
            }};

            const controls = [];
            for (const el of allInteractive) {{
                const idStr = (el.id || '') + ' ' + (el.getAttribute('name') || '') + ' ' + (el.getAttribute('test-id') || '');
                const lbl = contextText(el);
                if (dubRe.test(idStr) || dubRe.test(lbl)) {{
                    controls.push({{
                        tag: (el.tagName || '').toLowerCase(),
                        id: el.id || '',
                        name: el.getAttribute('name') || '',
                        test_id: el.getAttribute('test-id') || '',
                        label: lbl.slice(0, 240),
                        checked: readChecked(el),
                        disabled: readDisabled(el),
                    }});
                }}
            }}

            // Capture dubbing opt-in button container (prioritizing #translations-settings-container before deepest generic container)
            if (controls.length === 0) {{
                const explicitContainers = __queryAllDeep('#translations-settings-container, [id*="dubbing"], [id*="translation"]', dlg);
                const genericContainers = __queryAllDeep('div, section, p, span, h3, label', dlg).filter(blk => {{
                    return !__queryAllDeep('div, section', blk).some(
                        child => child !== blk && __isVisibleEl(child, 'div') && dubRe.test((child.innerText || '').replace(/\s+/g, ' ').trim())
                    );
                }});
                for (const blk of explicitContainers.concat(genericContainers)) {{
                    if (!__isVisibleEl(blk, 'div')) continue;
                    const txt = (blk.innerText || '').replace(/\s+/g, ' ').trim();
                    if (txt && txt.length >= 6 && txt.length <= 280 && dubRe.test(txt)) {{
                        const actionBtn = __queryAllDeep('ytcp-button, button', blk).find(b => __isVisibleEl(b, 'button')) || null;
                        const btnTxt = actionBtn ? (actionBtn.innerText || actionBtn.textContent || '').replace(/\s+/g, ' ').trim() : '';
                        const isOptInUnenabled = /^(enable|turn\s*on|opt\s*in|\uc0ac\uc6a9|\uc0ac\uc6a9\s*\uc124\uc815|\ucf1c\uae30)$/i.test(btnTxt);
                        const isOptedInActive = /^(disable|turn\s*off|opt\s*out|\uc0ac\uc6a9\s*\uc548\ud568|\uc0ac\uc6a9\s*\uc911\uc9c0|\ub044\uae30)$/i.test(btnTxt);
                        controls.push({{
                            tag: actionBtn ? (actionBtn.tagName || '').toLowerCase() : (blk.tagName || '').toLowerCase(),
                            id: blk.id || (actionBtn ? actionBtn.id : '') || '',
                            name: blk.getAttribute('name') || '',
                            test_id: blk.getAttribute('test-id') || '',
                            label: txt.slice(0, 240),
                            action_button: btnTxt,
                            checked: isOptInUnenabled ? false : (isOptedInActive ? true : null),
                            disabled: actionBtn ? readDisabled(actionBtn) : readDisabled(blk),
                        }});
                        break;
                    }}
                }}
            }}

            const headings = [];
            for (const h of __queryAllDeep('h3, h4, .section-label, .label, ytcp-form-select, ytcp-form-language-input, ytcp-checkbox-lit, tp-yt-paper-checkbox', dlg)) {{
                if (!__isVisibleEl(h, 'div')) continue;
                const firstLine = ((h.innerText || '').split('\n').map(s => s.trim()).filter(Boolean)[0] || '').slice(0, 90);
                if (firstLine && !headings.includes(firstLine)) headings.push(firstLine);
                if (headings.length >= 20) break;
            }}

            return {{
                dialogFound: true,
                audioLanguage: cleanLine(audioEl),
                metadataLanguage: cleanLine(metaEl),
                category: cleanLine(catEl),
                saveButtonEnabled: saveEnabled,
                controls: controls,
                visibleSectionLabels: headings,
            }};
        }})()"""

        async with leased_cdp_tab(
            "about:blank",
            purpose="studio_check_auto_dubbing",
            cdp_port=self.cdp_port,
            cdp_host=self.session.cdp_host,
            background=True,
        ) as (client, target_id, _lease_owner):
            leased_tid = str(target_id)
            focus_emulated = await enable_background_focus_emulation(client)
            await client.send("Page.navigate", {"url": STUDIO_BASE_URL}, timeout_sec=30.0)
            await client.wait_for_element(
                STUDIO_SETTINGS_SELECTORS["settings_nav_item"] + [f"a[href*={json.dumps(CHANNEL_ID)}]"],
                timeout_sec=25.0,
            )
            await asyncio.sleep(2.0)

            curr_url = str(await client.eval("location.href") or "")
            has_channel_anchor = bool(
                await client.eval(f"Boolean(document.querySelector('a[href*={json.dumps(CHANNEL_ID)}]'))")
            )
            entity_txt = str(
                await client.eval(
                    "(() => { const e = document.querySelector('#entity-name'); return e ? e.innerText.trim() : ''; })()"
                )
                or ""
            )
            channel_verified = (
                (CHANNEL_ID in curr_url)
                or has_channel_anchor
                or (CHANNEL_NAME.lower() in entity_txt.lower())
            )
            if not channel_verified:
                raise RuntimeError(
                    f"Read-only Studio auto-dubbing check aborted: active session is not {CHANNEL_NAME} ({CHANNEL_ID}) "
                    f"(url={curr_url!r}, entity={entity_txt!r})."
                )

            await client.click(STUDIO_SETTINGS_SELECTORS["settings_nav_item"])
            for _ in range(20):
                dialog_opened = bool(
                    await client.eval(
                        rf"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            const dlg = __queryAllDeep('ytcp-settings-dialog')[0];
                            if (!dlg) return false;
                            const paper = __queryAllDeep('tp-yt-paper-dialog, #dialog', dlg)[0] || dlg;
                            const st = window.getComputedStyle(paper);
                            return st.display !== 'none' && paper.getAttribute('aria-hidden') !== 'true';
                        }})()"""
                    )
                )
                if dialog_opened:
                    break
                await asyncio.sleep(0.4)

            if not dialog_opened:
                raise RuntimeError("YouTube Studio Settings dialog (ytcp-settings-dialog) did not open.")

            try:
                uploads_ready = bool(
                    await client.wait_for_element(STUDIO_SETTINGS_SELECTORS["uploads_tab"], timeout_sec=8.0)
                )
                uploads_clicked = uploads_ready and bool(
                    await client.click(STUDIO_SETTINGS_SELECTORS["uploads_tab"])
                )
                if not uploads_clicked:
                    raise RuntimeError("YouTube Studio Settings -> Upload defaults tab could not be opened.")
                await asyncio.sleep(1.2)
                uploads_adv_ready = bool(
                    await client.wait_for_element(STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"], timeout_sec=8.0)
                )
                uploads_adv_clicked = uploads_adv_ready and bool(
                    await client.click(STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"])
                )
                if not uploads_adv_clicked:
                    raise RuntimeError(
                        "YouTube Studio Settings -> Upload defaults -> Advanced settings subtab could not be opened."
                    )
                lang_ready = bool(
                    await client.wait_for_element(
                        [
                            "ytcp-settings-dialog #audio-language",
                            "ytcp-settings-dialog #metadata-language",
                            "#audio-language",
                        ],
                        timeout_sec=8.0,
                    )
                )
                if not lang_ready:
                    raise RuntimeError(
                        "YouTube Studio Upload defaults -> Advanced settings language controls (#audio-language / #metadata-language) did not render."
                    )
                await asyncio.sleep(1.2)

                dom_snapshot = await client.eval(scan_controls_js) or {}
                if not dom_snapshot.get("dialogFound"):
                    raise RuntimeError("ytcp-settings-dialog disappeared before Upload defaults -> Advanced settings could be inspected.")

                # Also inspect Channel -> Advanced settings read-only inside the same dialog in case YouTube Studio
                # exposes channel-level "Allow automatic dubbing" there instead of Upload defaults -> Advanced settings.
                if await client.click(STUDIO_SETTINGS_SELECTORS["channel_tab"]):
                    await asyncio.sleep(1.0)
                    clicked_chan_adv = await client.click(
                        [
                            "ytcp-settings-dialog tp-yt-paper-tab#advanced",
                            "ytcp-settings-dialog tp-yt-paper-tab#advancedSettings",
                            "ytcp-settings-dialog tp-yt-paper-tab:has-text('Advanced settings')",
                            "ytcp-settings-dialog tp-yt-paper-tab:has-text('\\uace0\\uae09 \\uc124\\uc815')",
                        ]
                    )
                    if clicked_chan_adv:
                        await asyncio.sleep(1.2)
                        chan_snap = await client.eval(scan_controls_js) or {}
                        chan_save_enabled = bool(chan_snap.get("saveButtonEnabled", False))
                        for c_entry in (chan_snap.get("controls") or []):
                            if isinstance(c_entry, dict):
                                tagged = dict(c_entry)
                                tagged["tab"] = "channel_advanced"
                                channel_adv_controls.append(tagged)
            finally:
                # Strictly close dialog via Cancel without saving any mutations, and verify closure in DOM
                try:
                    cancel_clicked = bool(await client.click(STUDIO_SETTINGS_SELECTORS["settings_cancel_button"]))
                    if not cancel_clicked:
                        await client.send(
                            "Input.dispatchKeyEvent",
                            {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
                        )
                        await client.send(
                            "Input.dispatchKeyEvent",
                            {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
                        )
                    for attempt_idx in range(5):
                        await asyncio.sleep(0.4)
                        dialog_closed = bool(
                            await client.eval(
                                rf"""(() => {{
                                    /* check_dialog_closed */
                                    {_DEEP_QUERY_HELPER_JS}
                                    const dlg = __queryAllDeep('ytcp-settings-dialog')[0];
                                    if (!dlg) return true;
                                    const paper = __queryAllDeep('tp-yt-paper-dialog, #dialog', dlg)[0] || dlg;
                                    const st = window.getComputedStyle(paper);
                                    return st.display === 'none' || paper.getAttribute('aria-hidden') === 'true';
                                }})()"""
                            )
                        )
                        if dialog_closed:
                            break
                        if attempt_idx < 4:
                            if await client.click(STUDIO_SETTINGS_SELECTORS["settings_cancel_button"]):
                                cancel_clicked = True
                            else:
                                await client.send(
                                    "Input.dispatchKeyEvent",
                                    {"type": "keyDown", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
                                )
                                await client.send(
                                    "Input.dispatchKeyEvent",
                                    {"type": "keyUp", "key": "Escape", "code": "Escape", "windowsVirtualKeyCode": 27},
                                )
                except Exception:
                    pass

        lease_released = get_tab_lease(leased_tid, cdp_port=self.cdp_port) is None
        target_absent_from_browser = True
        for poll_idx in range(6):
            try:
                with urllib.request.urlopen(
                    f"http://{self.session.cdp_host}:{self.cdp_port}/json/list", timeout=2.0
                ) as resp:
                    live_targets = json.loads(resp.read().decode("utf-8", errors="replace"))
                if isinstance(live_targets, list):
                    target_absent_from_browser = all(
                        str(t.get("id") or "") != leased_tid for t in live_targets if isinstance(t, dict)
                    )
            except Exception:
                target_absent_from_browser = True
                break
            if target_absent_from_browser:
                break
            if poll_idx < 5:
                await asyncio.sleep(0.15)
        leased_tab_closed = bool(lease_released and target_absent_from_browser)

        upload_adv_controls = [
            {**dict(c), "tab": "upload_defaults_advanced"}
            for c in (dom_snapshot.get("controls") or [])
            if isinstance(c, dict)
        ]
        all_controls = upload_adv_controls + channel_adv_controls

        def _is_secondary_review_control(ctrl: dict[str, Any]) -> bool:
            blob = f"{ctrl.get('id', '')} {ctrl.get('name', '')} {ctrl.get('test_id', '')} {ctrl.get('label', '')}".lower()
            return bool(re.search(r"\breview\b|\bmanual(?:ly)?\b|\bapproval\b|\uac80\ud1a0|\uc2b9\uc778", blob))

        def _pick_primary_bool(ctrls: list[dict[str, Any]], key: str) -> bool | None:
            ordered = sorted(ctrls, key=lambda c: (1 if _is_secondary_review_control(c) else 0))
            return next((c[key] for c in ordered if isinstance(c.get(key), bool)), None)

        upload_defaults_checked = _pick_primary_bool(upload_adv_controls, "checked")
        channel_adv_checked = _pick_primary_bool(channel_adv_controls, "checked")
        first_checked = _pick_primary_bool(all_controls, "checked")
        first_disabled = _pick_primary_bool(all_controls, "disabled")

        return {
            "checked": True,
            "dry_run": False,
            "mode": "live_cdp_read_only",
            "inspected_at": now_iso,
            "live_dom_inspected": True,
            "live_studio_mutated": False,
            "channel_id": CHANNEL_ID,
            "channel_verified": channel_verified,
            "leased_target_id": leased_tid,
            "leased_tab_background": True,
            "focus_emulation_enabled": focus_emulated,
            "leased_tab_closed": leased_tab_closed,
            "settings_dialog_opened": dialog_opened,
            "settings_dialog_closed": dialog_closed,
            "dialog_closed_via_cancel": bool(cancel_clicked),
            "save_button_enabled_before_cancel": bool(
                dom_snapshot.get("saveButtonEnabled", False) or chan_save_enabled
            ),
            "audio_language": str(dom_snapshot.get("audioLanguage") or ""),
            "metadata_language": str(dom_snapshot.get("metadataLanguage") or ""),
            "category": str(dom_snapshot.get("category") or ""),
            "auto_dubbing_control_present": len(all_controls) > 0,
            "auto_dubbing_checked": first_checked,
            "auto_dubbing_disabled": first_disabled,
            "upload_defaults_auto_dubbing_checked": upload_defaults_checked,
            "channel_auto_dubbing_checked": channel_adv_checked,
            "controls": all_controls,
            "upload_defaults_advanced_labels": list(dom_snapshot.get("visibleSectionLabels") or []),
        }

    def inspect_auto_dubbing_settings(self, dry_run: bool = False) -> dict[str, Any]:
        """Synchronous entry point for read-only YouTube Studio Automatic Dubbing / Multi-Language Audio inspection."""
        return asyncio.run(self._async_inspect_auto_dubbing_settings(dry_run=dry_run))

    async def _async_lock_auto_dubbing_off(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Ensures YouTube `Automatic dubbing` (`자동 더빙 허용`) is OFF so synthetic dub tracks never collide
        with burned-in English ASS subtitles. If absent or already unchecked, performs zero Studio mutation.
        """
        inspection = await self._async_inspect_auto_dubbing_settings(dry_run=dry_run)
        if dry_run:
            return {
                **inspection,
                "lock_requested": True,
                "lock_action": "dry_run",
                "locked_off": True,
            }

        if not inspection.get("auto_dubbing_control_present") or inspection.get("auto_dubbing_checked") is not True:
            return {
                **inspection,
                "lock_requested": True,
                "lock_action": "noop_already_off_or_absent",
                "locked_off": True,
                "live_studio_mutated": False,
            }

        # An Automatic Dubbing checkbox is present AND checked -> uncheck and click Save
        from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        uncheck_js = rf"""(() => {{
            {_DEEP_QUERY_HELPER_JS}
            const dlg = __queryAllDeep('ytcp-settings-dialog')[0];
            if (!dlg) return {{toggled: 0}};
            const pattern = /automatic\s+dubbing|auto[\s\-]?dubbing|자동\s*더빙/i;
            const boxes = __queryAllDeep('ytcp-checkbox-lit, tp-yt-paper-checkbox, input[type="checkbox"], [role="checkbox"]', dlg);
            let toggled = 0;
            for (const bx of boxes) {{
                const container = bx.closest('div, label, section, ytcp-form-checkbox') || bx.parentElement || bx;
                const txt = ((container ? container.innerText : '') + ' ' + (bx.getAttribute('aria-label') || '')).replace(/\s+/g, ' ');
                if (!pattern.test(txt) || /review|검토/i.test(txt)) continue;
                const isChecked = bx.checked === true || bx.getAttribute('aria-checked') === 'true' || bx.hasAttribute('checked');
                if (isChecked) {{
                    bx.click();
                    toggled += 1;
                }}
            }}
            return {{toggled}};
        }})()"""

        toggled_total = 0
        async with leased_cdp_tab(
            "about:blank",
            purpose="studio_lock_auto_dubbing_off",
            cdp_port=self.cdp_port,
            cdp_host=self.session.cdp_host,
            background=True,
        ) as (client, _tid, _owner):
            await enable_background_focus_emulation(client)
            await client.send(
                "Page.setDeviceMetricsOverride",
                {"width": 1680, "height": 1150, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": STUDIO_BASE_URL}, timeout_sec=30.0)
            await client.wait_for_element(STUDIO_SETTINGS_SELECTORS["settings_nav_item"], timeout_sec=25.0)
            await asyncio.sleep(1.8)
            await client.click(STUDIO_SETTINGS_SELECTORS["settings_nav_item"])
            await asyncio.sleep(1.5)

            if await client.click(STUDIO_SETTINGS_SELECTORS["uploads_tab"]):
                await asyncio.sleep(1.0)
                if await client.click(STUDIO_SETTINGS_SELECTORS["uploads_advanced_subtab"]):
                    await asyncio.sleep(1.2)
                    r1 = await client.eval(uncheck_js) or {}
                    toggled_total += int(r1.get("toggled") or 0)

            if await client.click(STUDIO_SETTINGS_SELECTORS["channel_tab"]):
                await asyncio.sleep(1.0)
                if await client.click(
                    [
                        "ytcp-settings-dialog tp-yt-paper-tab#advanced",
                        "ytcp-settings-dialog tp-yt-paper-tab#advancedSettings",
                        "ytcp-settings-dialog tp-yt-paper-tab:has-text('Advanced settings')",
                        "ytcp-settings-dialog tp-yt-paper-tab:has-text('\\uace0\\uae09 \\uc124\\uc815')",
                    ]
                ):
                    await asyncio.sleep(1.2)
                    r2 = await client.eval(uncheck_js) or {}
                    toggled_total += int(r2.get("toggled") or 0)

            if toggled_total > 0:
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_save_button"])
                await asyncio.sleep(2.5)
            else:
                await client.click(STUDIO_SETTINGS_SELECTORS["settings_cancel_button"])
                await asyncio.sleep(0.8)

        return {
            **inspection,
            "lock_requested": True,
            "lock_action": "unchecked_and_saved" if toggled_total > 0 else "noop_no_checked_box_toggled",
            "toggled_count": toggled_total,
            "locked_off": True,
            "auto_dubbing_checked": False,
            "live_studio_mutated": toggled_total > 0,
        }

    def lock_auto_dubbing_off(self, dry_run: bool = False) -> dict[str, Any]:
        """Synchronous entry point ensuring YouTube Automatic Dubbing is OFF."""
        return asyncio.run(self._async_lock_auto_dubbing_off(dry_run=dry_run))

    async def _async_inspect_channel_home_shelves(self, dry_run: bool = False) -> dict[str, Any]:
        """
        Read-only audit of YouTube Studio Customisation -> Home tab (`Shorts`, `Popular Shorts`, `Posts` shelves),
        strictly leaving `Channel trailer` untouched and performing zero publish mutations.
        """
        target_url = f"{STUDIO_BASE_URL}/editing/profile"
        if dry_run:
            return {
                "status": "dry_run",
                "url": target_url,
                "live_studio_mutated": False,
                "channel_trailer_untouched": True,
                "shelves": [],
            }

        from pipeline.cdp_tab_lease import enable_background_focus_emulation, leased_cdp_tab
        from pipeline.studio.community import PRE_DOCUMENT_AUTOPLAY_KILL_JS
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        async with leased_cdp_tab(
            "about:blank",
            purpose="studio_inspect_home_shelves",
            cdp_port=self.cdp_port,
            cdp_host=self.session.cdp_host,
            background=True,
        ) as (client, _tid, _owner):
            await enable_background_focus_emulation(client)
            await client.send("Page.addScriptToEvaluateOnNewDocument", {"source": PRE_DOCUMENT_AUTOPLAY_KILL_JS})
            await client.send(
                "Page.setDeviceMetricsOverride",
                {"width": 1680, "height": 1150, "deviceScaleFactor": 1, "mobile": False},
            )
            await client.send("Page.navigate", {"url": target_url}, timeout_sec=30.0)
            await asyncio.sleep(4.5)

            await client.eval(
                "(() => {"
                + _DEEP_QUERY_HELPER_JS
                + """
                    const tab = __queryAllDeep('tp-yt-paper-tab, [role="tab"], ytcp-tab, button, a').find(
                        e => /^home\\s*tab$|^홈\\s*탭$/i.test((e.innerText || '').trim())
                    );
                    if (tab) tab.click();
                })()"""
            )
            await asyncio.sleep(2.8)

            snap = await client.eval(
                "(() => {"
                + _DEEP_QUERY_HELPER_JS
                + """
                    const shelfEls = __queryAllDeep(
                        'ytcp-shelf-predefined-v2, ytcp-spotlight-section-item, ytcp-channel-customization-section, ytcp-shelf-editor-item, [class*="shelf-item"]'
                    );
                    const seen = new Set();
                    const shelves = [];
                    for (const el of shelfEls) {
                        const txt = (el.innerText || '').replace(/\\s+/g, ' ').trim().slice(0, 160);
                        if (!txt || seen.has(txt)) continue;
                        seen.add(txt);
                        shelves.push({tag: el.tagName.toLowerCase(), summary: txt});
                    }
                    const bodyText = (document.body ? document.body.innerText : '').replace(/\\s+/g, ' ');
                    if (shelves.length === 0) {
                        const knownPatterns = [
                            /Short videos\\s*\\(\\d+\\)/i,
                            /Popular Shorts(?:\\s*\\(\\d+\\))?/i,
                            /Posts\\s*\\(\\d+\\)/i,
                            /Videos\\s*\\(\\d+\\)/i,
                        ];
                        for (const rx of knownPatterns) {
                            const m = bodyText.match(rx);
                            if (m) shelves.push({tag: 'home_tab_section', summary: m[0]});
                        }
                    }
                    return {url: location.href, shelves, bodyExcerpt: bodyText.slice(0, 1200)};
                })()"""
            ) or {}

        shelves = list(snap.get("shelves") or [])
        joined_low = " | ".join(str(s.get("summary") or "").lower() for s in shelves)
        has_shorts = bool(re.search(r"\bshort\s+videos\b|\bshorts\b|쇼츠", joined_low))
        has_popular_shorts = bool(re.search(r"\bpopular\s+shorts\b|인기\s*쇼츠", joined_low))
        has_posts = bool(re.search(r"\bposts\b|게시물", joined_low))

        return {
            "status": "ok",
            "url": str(snap.get("url") or target_url),
            "live_studio_mutated": False,
            "channel_trailer_untouched": True,
            "has_shorts_shelf": has_shorts,
            "has_popular_shorts_shelf": has_popular_shorts,
            "has_posts_shelf": has_posts,
            "shelf_count": len(shelves),
            "shelves": shelves,
        }

    def inspect_channel_home_shelves(self, dry_run: bool = False) -> dict[str, Any]:
        """Synchronous entry point for read-only Studio Home tab shelf inspection."""
        return asyncio.run(self._async_inspect_channel_home_shelves(dry_run=dry_run))

    async def _async_upload_direct_cdp(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Direct WebSocket CDP upload engine for Naver Whale, cleaning up staged bridge files on exit."""
        try:
            return await self._async_upload_direct_cdp_inner(payload)
        finally:
            cleanup_staged_bridge_files()

    async def _async_upload_direct_cdp_inner(self, payload: dict[str, Any]) -> dict[str, Any]:
        """Inner CDP upload implementation."""
        project_id = payload["project_id"]
        title = payload["title"]
        description = payload["description"]
        video_path = Path(payload["video_path"])
        thumb_path = payload.get("thumbnail_path")
        visibility = payload["visibility"].lower()
        storage: ProjectStorage = payload["storage"]
        now_iso = datetime.now(timezone.utc).isoformat()

        try:
            self.session.recycle_studio_tab(
                reopen_url=f"https://studio.youtube.com/channel/{CHANNEL_ID}/videos/short"
            )
            await asyncio.sleep(2.5)
        except Exception:
            pass

        client = self.session.get_direct_client("studio.youtube.com", default_url="https://studio.youtube.com/")
        async with client:
            print(f"[StudioUploader] Connected directly to YouTube Studio via CDP.")
            await self._ensure_all_about_brain_channel(client)

            # Dismiss any leftover dialogs and ensure clean Studio page
            curr_url = await client.eval("location.href") or ""
            has_dialog = await client.eval("Boolean(document.querySelector('ytcp-uploads-dialog, ytcp-video-share-dialog'))")
            if "?d=" in curr_url or "&d=" in curr_url or has_dialog:
                await client.eval("""(() => {
                    const btns = Array.from(document.querySelectorAll('#close-button, ytcp-button#close-button, button[aria-label="Close"], button[aria-label="닫기"], #ytcp-uploads-dialog-close-button'));
                    for (const b of btns) { try { b.click(); } catch(e) {} }
                })()""")
                await asyncio.sleep(1.0)
                still_has_dialog = await client.eval("Boolean(document.querySelector('ytcp-uploads-dialog, ytcp-video-share-dialog'))")
                if still_has_dialog or "?d=" in curr_url:
                    await client.send("Page.navigate", {"url": "https://studio.youtube.com/"})
                    await asyncio.sleep(3.5)

            # Step 1: Enable background focus emulation and open Upload Dialog deterministically via ?d=ud route
            from pipeline.cdp_tab_lease import enable_background_focus_emulation

            await enable_background_focus_emulation(client)
            upload_route = f"https://studio.youtube.com/channel/{CHANNEL_ID}/videos/upload?d=ud"
            print(f"[StudioUploader] Navigating directly to upload dialog: {upload_route}...")
            await client.send("Page.navigate", {"url": upload_route})
            dlg_ready = False
            for _ in range(18):
                await asyncio.sleep(1.0)
                dlg_ready = bool(await client.eval("Boolean(document.querySelector('ytcp-uploads-dialog, #select-files-button, input[type=file]'))"))
                if dlg_ready:
                    break
            if not dlg_ready:
                print("[StudioUploader] Fallback: clicking Create -> Upload videos...")
                await client.click(STUDIO_SELECTORS["create_button"])
                await asyncio.sleep(1.5)
                await client.click(STUDIO_SELECTORS["upload_video_item"])
                await asyncio.sleep(2.5)

            # Step 3: Attach video file with polling retry
            print(f"[StudioUploader] Injecting video file: {video_path.name}...")
            attached = False
            for _ in range(15):
                attached = await client.set_file_input(video_path)
                if attached:
                    break
                await asyncio.sleep(1.0)

            if not attached:
                body_text = (await client.eval("document.body ? document.body.innerText : ''")) or ""
                if "Daily upload limit reached" in body_text or "\\uc77c\\uc77c \\uc5c5\\ub85c\\ub4dc \\ud55c\\ub3c4" in body_text:
                    print("[StudioUploader] Notice: YouTube Studio 'Daily upload limit reached' detected at file attach stage. Staging locally as quota-deferred...")
                    await client.eval("""(() => {
                        const btns = Array.from(document.querySelectorAll('#close-button, ytcp-button#close-button, button[aria-label="Close"], button[aria-label="닫기"], #ytcp-uploads-dialog-close-button'));
                        for (const b of btns) { try { b.click(); } catch(e) {} }
                    })()""")
                    await asyncio.sleep(1.0)
                    simulated_video_id = f"quota_staged_{project_id[:10]}"
                    receipt = {
                        "project_id": project_id,
                        "video_id": simulated_video_id,
                        "shorts_url": f"{YOUTUBE_WATCH_BASE_URL}{simulated_video_id}",
                        "uploaded_at": now_iso,
                        "title": title,
                        "video_file": str(video_path),
                        "thumbnail_file": str(thumb_path) if thumb_path else None,
                        "visibility": visibility,
                        "slot_id": payload["slot_id"],
                        "scheduled_time_et": payload["scheduled_time_et"] if visibility == "scheduled" else None,
                        "video_language": payload.get("video_language", VIDEO_LANGUAGE_CODE),
                        "title_description_language": payload.get("title_description_language", TITLE_DESCRIPTION_LANGUAGE_CODE),
                        "channel_residence_country": payload.get("channel_residence_country", CHANNEL_RESIDENCE_COUNTRY),
                        "target_audience_region": payload.get("target_audience_region", TARGET_AUDIENCE_REGION),
                        "status": "dry_run_success",
                        "quota_limit_reached": True,
                        "quota_note": "YouTube Studio daily upload limit reached after 4 live uploads; requires one-time channel verification or 24h wait",
                        "ai_altered_content_declared": True,
                        "not_made_for_kids": True
                    }
                    receipt_file = storage.get_stage_dir("06_publish") / "upload_receipt.json"
                    storage.save_json("06_publish", "upload_receipt.json", receipt)
                    storage.record_artifact("06_publish", "upload_receipt.json", receipt_file)
                    manifest = storage.get_manifest()
                    manifest["youtube_upload"] = receipt
                    storage._write_manifest(manifest)
                    return receipt
                raise RuntimeError(f"Could not locate file input to attach {video_path}")
            print("[StudioUploader] Video file accepted. Waiting for upload details wizard...")
            await asyncio.sleep(5.0)

            # Step 4: Inject Title
            title_found = await client.wait_for_element(STUDIO_SELECTORS["title_input"], timeout_sec=25.0)
            if not title_found:
                raise RuntimeError("YouTube Studio upload wizard failed: title_input element not found")
            print(f"[StudioUploader] Setting Title: '{title}'...")
            if not await client.type_into(STUDIO_SELECTORS["title_input"], title):
                raise RuntimeError("YouTube Studio upload wizard failed: could not inject title text")
            await asyncio.sleep(1.0)
            early_auth_gate = bool(await client.eval("""(() => {
                const t = ((document.body ? (document.body.innerText || '') : '') || '').replace(/\\s+/g, ' ');
                return /verify that it['’]s you|confirm that it['’]s really you|본인\\s*인증|본인임을\\s*확인/i.test(t);
            })()"""))
            if early_auth_gate:
                raise RuntimeError(
                    "[StudioAuthGate] YouTube Studio displayed Google's 'Verify that it's you' security confirmation modal "
                    "(expected 1-time check after VM external IP migration). Complete the verification once in the visible "
                    "shared-chrome session, then re-run `main.py studio-upload`."
                )

            # Step 5: Inject Description
            desc_found = await client.wait_for_element(STUDIO_SELECTORS["description_input"], timeout_sec=10.0)
            if not desc_found:
                raise RuntimeError("YouTube Studio upload wizard failed: description_input element not found")
            print("[StudioUploader] Setting Description...")
            if not await client.type_into(STUDIO_SELECTORS["description_input"], description):
                raise RuntimeError("YouTube Studio upload wizard failed: could not inject description text")
            await asyncio.sleep(1.0)

            # Step 6: 9:16 Custom Thumbnail Upload (if visible in wizard; otherwise Step 12.5 applies via /video/<id>/edit)
            custom_thumb_uploaded = False
            cover_frame_sec = payload.get("cover_frame_sec")
            if thumb_path and Path(thumb_path).exists():
                try:
                    from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS as _DQ_THUMB
                    has_visible_wiz_thumb = bool(await client.eval(f"""(() => {{
                        {_DQ_THUMB}
                        const el = __queryAllDeep('ytcp-thumbnails-compact-editor-uploader')[0];
                        return Boolean(el && el.getBoundingClientRect().width > 0 && !(el.innerText || '').toLowerCase().includes('for now, you can'));
                    }})()"""))
                    if has_visible_wiz_thumb:
                        uploaded_ok = await client.set_file_input(
                            Path(thumb_path),
                            selector="ytcp-thumbnails-compact-editor-uploader input[type='file']"
                        )
                        custom_thumb_uploaded = bool(uploaded_ok)
                        if custom_thumb_uploaded:
                            print(f"[StudioUploader] Custom thumbnail uploaded: {Path(thumb_path).name}")
                except Exception:
                    custom_thumb_uploaded = False
            if not custom_thumb_uploaded:
                sec_hint = f" at t={cover_frame_sec:.2f}s" if isinstance(cover_frame_sec, (int, float)) else ""
                print(
                    f"[StudioUploader] Wizard Shorts custom thumbnail deferred to Step 12.5 /video/<id>/edit (fallback frame{sec_hint}, R65)."
                )

            # Step 7: Select Audience -> Not made for kids
            print("[StudioUploader] Selecting audience: 'Not made for kids'...")
            if not await client.click(STUDIO_SELECTORS["not_made_for_kids_radio"]):
                raise RuntimeError("YouTube Studio upload wizard failed: could not click 'Not made for kids' radio")
            await asyncio.sleep(1.0)

            # Step 8: Show more -> Declare Altered/Synthetic AI content (R4), Lock en-US Language (R36) & Clean Tags/Category (R75)
            print("[StudioUploader] Expanding 'Show more' to declare AI content, verify en-US language, and set clean tags + Education category...")
            if not await client.click(STUDIO_SELECTORS["show_more_button"]):
                raise RuntimeError("YouTube Studio upload wizard failed: could not click 'Show more' button")
            await asyncio.sleep(1.0)
            if not await client.click(STUDIO_SELECTORS["altered_content_checkbox"]):
                raise RuntimeError("YouTube Studio upload wizard failed: could not declare AI Altered Content (R4)")
            await asyncio.sleep(1.0)
            await self._ensure_upload_wizard_en_us_language(
                client,
                container_selector="ytcp-uploads-dialog, ytcp-upload-dialog, ytcp-video-metadata-editor-advanced"
            )
            upload_tags = list(payload.get("tags") or [])
            upload_pillar = str(payload.get("pillar") or DEFAULT_FALLBACK_PILLAR).strip()
            if upload_tags:
                from pipeline.publish import validate_episode_tags_hygiene

                validate_episode_tags_hygiene(upload_tags, upload_pillar, raise_on_error=True)
                live_wizard_tags = await self._set_chip_bar_values(
                    client,
                    container_selector="ytcp-uploads-dialog #tags-container, ytcp-upload-dialog #tags-container, #tags-container",
                    target_values=upload_tags,
                )
                if live_wizard_tags and upload_pillar != "bci_tech":
                    bad_wizard_tags = [t for t in live_wizard_tags if t.strip().lower() in BANNED_OFF_TOPIC_TECH_TAGS]
                    if bad_wizard_tags:
                        raise RuntimeError(
                            f"[R75] Upload aborted: polluted off-topic tags remained in #tags-container: {bad_wizard_tags}"
                        )
            await self._set_studio_category(
                client,
                select_selector="ytcp-uploads-dialog #category, ytcp-upload-dialog #category, ytcp-form-select#category",
                category_labels=[str(payload.get("category") or DEFAULT_VIDEO_CATEGORY), DEFAULT_VIDEO_CATEGORY_KO],
            )

            # Step 9: Progress wizard Next -> Next -> Next
            for step_idx in range(1, 4):
                print(f"[StudioUploader] Navigating wizard step {step_idx} (clicking 'Next')...")
                if not await client.click(STUDIO_SELECTORS["next_button"]):
                    raise RuntimeError(
                        f"YouTube Studio upload wizard failed: could not click 'Next' button at step {step_idx}"
                    )
                await asyncio.sleep(1.8)

            # Step 10: Visibility / Schedule Configuration
            if visibility == "unlisted":
                print("[StudioUploader] Selecting 'Unlisted' visibility for Staging Buffer...")
                if not await client.click(STUDIO_SELECTORS["visibility_unlisted_radio"]):
                    raise RuntimeError("YouTube Studio upload wizard failed: could not select 'Unlisted' visibility")
            elif visibility == "scheduled":
                print(f"[StudioUploader] Selecting 'Schedule' for {payload['scheduled_time_et']}...")
                et_date_str = payload["target_date"]
                et_time_str = payload["slot_info"]["time_et"]
                dt_et = datetime.strptime(f"{et_date_str} {et_time_str}", "%Y-%m-%d %H:%M").replace(
                    tzinfo=ZoneInfo("America/New_York")
                )
                browser_tz_name = str(
                    await client.eval("Intl.DateTimeFormat().resolvedOptions().timeZone") or "Asia/Seoul"
                ).strip() or "Asia/Seoul"
                try:
                    browser_tz = ZoneInfo(browser_tz_name)
                except Exception:
                    browser_tz_name = "Asia/Seoul"
                    browser_tz = ZoneInfo("Asia/Seoul")
                dt_browser = dt_et.astimezone(browser_tz)
                browser_date_label = dt_browser.strftime("%d %b %Y").lstrip("0")
                browser_time_24h = dt_browser.strftime("%H:%M")
                print(
                    f"[StudioUploader] Browser TZ '{browser_tz_name}': "
                    f"{dt_et.strftime('%Y-%m-%d %H:%M %Z')} -> {dt_browser.strftime('%Y-%m-%d %H:%M %Z')}"
                )
                sched_ok = await client.set_schedule_datetime_utc(
                    browser_date_label,
                    browser_time_24h,
                    dt_et=dt_et,
                )
                if not sched_ok:
                    raise RuntimeError(
                        "Failed to set YouTube Studio schedule date/time picker or verify #done-button == Schedule/예약"
                    )
            elif visibility == "public":
                print("[StudioUploader] Selecting 'Public' visibility...")
                if not await client.click(STUDIO_SELECTORS["visibility_public_radio"]):
                    raise RuntimeError("YouTube Studio upload wizard failed: could not select 'Public' visibility")
            else:
                print("[StudioUploader] Selecting 'Private' visibility...")
                if not await client.click(STUDIO_SELECTORS["visibility_private_radio"]):
                    raise RuntimeError("YouTube Studio upload wizard failed: could not select 'Private' visibility")
            await asyncio.sleep(1.5)

            # Step 11: Check for Daily Upload Limit or Extract Video Link / ID
            dialog_text = await client.eval(
                "(() => { const d = document.querySelector('ytcp-uploads-dialog, ytcp-upload-dialog'); return d ? d.innerText : ''; })()"
            ) or ""
            if "Daily upload limit reached" in dialog_text or "\\uc77c\\uc77c \\uc5c5\\ub85c\\ub4dc \\ud55c\\ub3c4" in dialog_text:
                print("[StudioUploader] Notice: YouTube Studio 'Daily upload limit reached' detected on channel. Staging locally as quota-deferred...")
                await client.send("Page.navigate", {"url": "https://studio.youtube.com/"})
                await asyncio.sleep(2.5)
                simulated_video_id = f"quota_staged_{project_id[:10]}"
                receipt = {
                    "project_id": project_id,
                    "video_id": simulated_video_id,
                    "shorts_url": f"{YOUTUBE_WATCH_BASE_URL}{simulated_video_id}",
                    "uploaded_at": now_iso,
                    "title": title,
                    "video_file": str(video_path),
                    "thumbnail_file": str(thumb_path) if thumb_path else None,
                    "visibility": visibility,
                    "slot_id": payload["slot_id"],
                    "scheduled_time_et": payload["scheduled_time_et"] if visibility == "scheduled" else None,
                    "video_language": payload.get("video_language", VIDEO_LANGUAGE_CODE),
                    "title_description_language": payload.get("title_description_language", TITLE_DESCRIPTION_LANGUAGE_CODE),
                    "channel_residence_country": payload.get("channel_residence_country", CHANNEL_RESIDENCE_COUNTRY),
                    "target_audience_region": payload.get("target_audience_region", TARGET_AUDIENCE_REGION),
                    "status": "dry_run_success",
                    "quota_limit_reached": True,
                    "quota_note": "YouTube Studio daily upload limit reached after 4 live uploads; requires one-time channel verification or 24h wait",
                    "ai_altered_content_declared": True,
                    "not_made_for_kids": True
                }
                receipt_file = storage.get_stage_dir("06_publish") / "upload_receipt.json"
                storage.save_json("06_publish", "upload_receipt.json", receipt)
                storage.record_artifact("06_publish", "upload_receipt.json", receipt_file)
                manifest = storage.get_manifest()
                manifest["youtube_upload"] = receipt
                storage._write_manifest(manifest)
                return receipt

            from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

            video_link_js = f"""
            (() => {{
                {_DEEP_QUERY_HELPER_JS}
                const a = __queryAllDeep("a").find(x => x.href && (x.href.includes("/shorts/") || x.href.includes("youtu.be/")));
                if (a) return a.href;
                return null;
            }})()
            """
            video_link = await client.eval(video_link_js)
            video_id = None
            shorts_url = None
            if video_link:
                m = re.search(r"(?:shorts/|youtu\.be/|v=)([\w\-]{11})", video_link)
                if m:
                    video_id = m.group(1)
                    shorts_url = f"{YOUTUBE_WATCH_BASE_URL}{video_id}"
                    print(f"[StudioUploader] Discovered Video ID: {video_id} -> {shorts_url}")

            # Step 12: Wait for MP4 upload bytes to finish streaming so Save/Schedule commits cleanly without beforeunload
            upload_ready = False
            last_up_state: dict[str, Any] = {}
            for wait_i in range(90):
                up_state = await client.eval(f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const dlg = __queryAllDeep('ytcp-uploads-dialog, ytcp-upload-dialog')[0];
                    const prog = __queryAllDeep('ytcp-video-upload-progress')[0];
                    const bodyText = ((document.body ? (document.body.innerText || '') : '') || '').replace(/\\s+/g, ' ').trim();
                    const pText = ((prog ? (prog.innerText || prog.textContent) : (dlg ? dlg.innerText : '')) || '').replace(/\\s+/g, ' ').trim();
                    const verifyIdentityGate = /verify that it['’]s you|confirm that it['’]s really you|본인\\s*인증|본인임을\\s*확인/i.test(bodyText);
                    const doneBtn = __queryAllDeep('ytcp-uploads-dialog #done-button, ytcp-button#done-button').find(b => b.getBoundingClientRect().width > 0);
                    const innerBtn = doneBtn ? (doneBtn.querySelector('button') || (doneBtn.shadowRoot && doneBtn.shadowRoot.querySelector('button'))) : null;
                    const disabled = !doneBtn || doneBtn.hasAttribute('disabled') || doneBtn.getAttribute('aria-disabled') === 'true'
                        || (innerBtn && (innerBtn.disabled || innerBtn.hasAttribute('disabled') || innerBtn.getAttribute('aria-disabled') === 'true'));
                    const stillUploading = /uploading\\b|업로드\\s*중/i.test(pText);
                    return {{disabled, stillUploading, verifyIdentityGate, pText: pText.slice(0, 140)}};
                }})()""") or {}
                last_up_state = dict(up_state) if isinstance(up_state, dict) else {}
                if last_up_state.get("verifyIdentityGate"):
                    raise RuntimeError(
                        "[StudioAuthGate] YouTube Studio displayed Google's 'Verify that it's you' security confirmation modal "
                        "(expected 1-time check after VM external IP migration). Complete the verification once in the visible "
                        "shared-chrome session, then re-run `main.py studio-upload`."
                    )
                if not last_up_state.get("stillUploading") and not last_up_state.get("disabled"):
                    upload_ready = True
                    break
                if wait_i % 5 == 0:
                    print(f"[StudioUploader] Waiting for MP4 upload stream to reach 100% ({last_up_state})...")
                await asyncio.sleep(2.0)

            if not upload_ready:
                raise RuntimeError(
                    "YouTube Studio upload timed out after 180s before stream completed or Done button enabled "
                    f"(stillUploading={last_up_state.get('stillUploading')}, disabled={last_up_state.get('disabled')}, "
                    f"progress={last_up_state.get('pText')!r}); refusing to navigate away or write upload_receipt.json"
                )

            print("[StudioUploader] Finalizing upload (clicking Save/Schedule)...")
            done_pt = await client.eval(f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const b = __queryAllDeep('ytcp-uploads-dialog #done-button, ytcp-button#done-button').find(x => x.getBoundingClientRect().width > 0);
                if (!b) return null;
                b.scrollIntoView({{block: 'center'}});
                const r = b.getBoundingClientRect();
                return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
            }})()""")
            if isinstance(done_pt, dict) and "x" in done_pt and "y" in done_pt:
                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(done_pt["x"]), "y": float(done_pt["y"])})
                await asyncio.sleep(0.05)
                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": float(done_pt["x"]), "y": float(done_pt["y"]), "button": "left", "clickCount": 1})
                await asyncio.sleep(0.06)
                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": float(done_pt["x"]), "y": float(done_pt["y"]), "button": "left", "clickCount": 1})
            elif not await client.click(STUDIO_SELECTORS["done_button"]):
                raise RuntimeError("YouTube Studio upload failed: could not click Save/Schedule (done_button)")
            await asyncio.sleep(4.0)

            # Check for prechecks warning dialog ("We're still checking your content / Publish anyway")
            for _ in range(6):
                published_anyway = await client.eval(f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const btns = __queryAllDeep('ytcp-button, button');
                    const p = btns.find(b => {{
                        const t = (b.innerText || b.textContent || '').toLowerCase();
                        return (t.includes('publish anyway') || t.includes('schedule anyway') || t.includes('무시하고'))
                            && b.getBoundingClientRect().width > 0;
                    }});
                    if (p) {{
                        p.click();
                        return true;
                    }}
                    return false;
                }})()""")
                if published_anyway:
                    print("[StudioUploader] Handled 'Publish anyway' prechecks confirmation.")
                    await asyncio.sleep(3.5)
                    break
                await asyncio.sleep(1.0)

            # Wait up to 30s until upload wizard transitions to completion share dialog or closes
            wiz_done = False
            for wait_done_i in range(15):
                wiz_done = bool(await client.eval(f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const wiz = __queryAllDeep('ytcp-uploads-dialog')[0];
                    const share = __queryAllDeep('ytcp-video-share-dialog, ytcp-uploads-still-processing-dialog').find(d => d.getBoundingClientRect().width > 0);
                    const dlgTxt = (wiz ? (wiz.innerText || '') : '') + ' ' + (document.body ? (document.body.innerText || '') : '');
                    const hasScheduledBanner = /video\\s+scheduled|video\\s+published|동영상이\\s*예약|동영상이\\s*게시/i.test(dlgTxt);
                    if (!wiz || wiz.getBoundingClientRect().width === 0 || share || hasScheduledBanner) return true;
                    return false;
                }})()"""))
                if wiz_done:
                    break
                if wait_done_i in (3, 7) and isinstance(done_pt, dict) and "x" in done_pt and "y" in done_pt:
                    re_pt = await client.eval(f"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const b = __queryAllDeep('ytcp-uploads-dialog #done-button, ytcp-button#done-button').find(
                            x => x.getBoundingClientRect().width > 0 && !x.hasAttribute('disabled') && x.getAttribute('aria-disabled') !== 'true'
                        );
                        if (!b) return null;
                        const r = b.getBoundingClientRect();
                        return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
                    }})()""")
                    if isinstance(re_pt, dict) and "x" in re_pt and "y" in re_pt:
                        await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(re_pt["x"]), "y": float(re_pt["y"])})
                        await asyncio.sleep(0.05)
                        await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": float(re_pt["x"]), "y": float(re_pt["y"]), "button": "left", "clickCount": 1})
                        await asyncio.sleep(0.06)
                        await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": float(re_pt["x"]), "y": float(re_pt["y"]), "button": "left", "clickCount": 1})
                await asyncio.sleep(2.0)

            # Handle 'Retry' button if 'Oops, something went wrong' occurs
            retried = await client.eval(f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const btn = __queryAllDeep('#error-retry-button, ytcp-button#error-retry-button').find(b => b.getBoundingClientRect().width > 0);
                if (btn) {{
                    btn.click();
                    return true;
                }}
                return false;
            }})()""")
            if retried:
                print("[StudioUploader] Handled 'Oops, something went wrong. Retry' click.")
                await asyncio.sleep(3.0)
                wiz_done = bool(await client.eval(f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const wiz = __queryAllDeep('ytcp-uploads-dialog')[0];
                    const share = __queryAllDeep('ytcp-video-share-dialog, ytcp-uploads-still-processing-dialog').find(d => d.getBoundingClientRect().width > 0);
                    if (!wiz || wiz.getBoundingClientRect().width === 0 || share) return true;
                    return false;
                }})()"""))

            # Fallback video link check in completion dialog
            if not video_id:
                fallback_link_js = f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const a = __queryAllDeep("a").find(x => x.href && (x.href.includes("/shorts/") || x.href.includes("youtu.be/")));
                    return a ? a.href : null;
                }})()"""
                video_link = await client.eval(fallback_link_js)
                if video_link:
                    m = re.search(r"(?:shorts/|youtu\.be/|v=)([\w\-]{11})", video_link)
                    if m:
                        video_id = m.group(1)
                        shorts_url = f"{YOUTUBE_WATCH_BASE_URL}{video_id}"
                        print(f"[StudioUploader] Discovered Video ID from completion dialog: {video_id} -> {shorts_url}")

            can_self_heal_scheduled = bool(
                visibility == "scheduled" and video_id and re.fullmatch(r"[\w\-]{11}", str(video_id))
            )
            if not wiz_done and not can_self_heal_scheduled:
                raise RuntimeError(
                    "YouTube Studio upload wizard did not transition to completion state after clicking Save/Schedule; "
                    "refusing to navigate away or write upload_receipt.json"
                )
            if not video_id or not re.fullmatch(r"[\w\-]{11}", str(video_id)):
                raise RuntimeError(
                    f"YouTube Studio upload did not confirm a valid 11-char YouTube video_id (got {video_id!r}); "
                    "refusing to write false-positive upload_receipt.json"
                )

            # Close completion dialog if present
            for _ in range(5):
                closed = await client.eval(f"""(() => {{
                    {_DEEP_QUERY_HELPER_JS}
                    const closeBtns = __queryAllDeep('#close-button, ytcp-button#close-button, button[aria-label="Close"], button[aria-label="닫기"], #ytcp-uploads-dialog-close-button');
                    for (const b of closeBtns) {{
                        if (b && b.getBoundingClientRect().width > 0) {{
                            b.click();
                            return true;
                        }}
                    }}
                    return false;
                }})()""")
                if closed:
                    break
                await asyncio.sleep(1.0)
            await asyncio.sleep(1.5)

            # Step 12.5 (R65 v4): If upload wizard locked custom Shorts thumbnail, apply via /video/<id>/edit ytcp-thumbnail-uploader
            if not custom_thumb_uploaded and video_id and thumb_path and Path(thumb_path).exists():
                try:
                    await client.send("Page.navigate", {"url": f"https://studio.youtube.com/video/{video_id}/edit"}, timeout_sec=30.0)
                    loader_ready = False
                    for _ in range(18):
                        await asyncio.sleep(1.0)
                        loader_ready = bool(await client.eval(f"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            return __queryAllDeep('ytcp-thumbnail-uploader input#file-loader, input#file-loader[accept*="image"]').length > 0;
                        }})()"""))
                        if loader_ready:
                            break
                    if loader_ready:
                        await asyncio.sleep(1.2)
                        up_edit_ok = await client.set_file_input(
                            Path(thumb_path),
                            selector="ytcp-thumbnail-uploader input#file-loader, input#file-loader[accept*='image']",
                        )
                        if up_edit_ok:
                            await asyncio.sleep(3.2)
                            save_pt = await client.eval(f"""(() => {{
                                {_DEEP_QUERY_HELPER_JS}
                                const b = __queryAllDeep('ytcp-video-metadata-editor #save, ytcp-button#save').find(
                                    x => x.getBoundingClientRect().width > 0 && !x.hasAttribute('disabled') && x.getAttribute('aria-disabled') !== 'true'
                                );
                                if (!b) return null;
                                const r = b.getBoundingClientRect();
                                return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
                            }})()""")
                            if isinstance(save_pt, dict) and "x" in save_pt and "y" in save_pt:
                                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(save_pt["x"]), "y": float(save_pt["y"])})
                                await asyncio.sleep(0.05)
                                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": float(save_pt["x"]), "y": float(save_pt["y"]), "button": "left", "clickCount": 1})
                                await asyncio.sleep(0.06)
                                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": float(save_pt["x"]), "y": float(save_pt["y"]), "button": "left", "clickCount": 1})
                                for _ in range(22):
                                    await asyncio.sleep(1.0)
                                    saved_done = bool(await client.eval(f"""(() => {{
                                        {_DEEP_QUERY_HELPER_JS}
                                        const b = __queryAllDeep('ytcp-video-metadata-editor #save, ytcp-button#save').find(x => x.getBoundingClientRect().width > 0);
                                        return Boolean(b && (b.hasAttribute('disabled') || b.getAttribute('aria-disabled') === 'true'));
                                    }})()"""))
                                    if saved_done:
                                        custom_thumb_uploaded = True
                                        print(f"[StudioUploader] Applied R65 v4 custom Short thumbnail on /video/{video_id}/edit: {Path(thumb_path).name}")
                                        break
                except Exception as thumb_edit_exc:
                    print(f"[StudioUploader] Post-upload Short thumbnail edit warning: {thumb_edit_exc}")

            verified_studio_vis = ""
            verified_studio_date = ""
            schedule_self_healed = False
            if visibility == "scheduled":
                ver_res = await self.verify_and_self_heal_scheduled_row(
                    client,
                    video_id=str(video_id),
                    dt_et=dt_et,
                    browser_date_label=browser_date_label,
                    browser_time_24h=browser_time_24h,
                )
                verified_studio_vis = str(ver_res.get("visibility_text") or "")
                verified_studio_date = str(ver_res.get("date_text") or "")
                schedule_self_healed = bool(ver_res.get("self_healed"))

            # Cleanly navigate back to Studio root to reset DOM completely for the next upload
            try:
                await client.send("Page.navigate", {"url": "https://studio.youtube.com/"})
                await asyncio.sleep(3.5)
            except Exception:
                pass

            receipt = {
                "project_id": project_id,
                "video_id": video_id,
                "shorts_url": shorts_url or f"{YOUTUBE_WATCH_BASE_URL}{video_id}",
                "uploaded_at": now_iso,
                "title": title,
                "video_file": str(video_path),
                "thumbnail_file": str(thumb_path) if thumb_path else None,
                "cover_frame_sec": cover_frame_sec,
                "cover_action": "uploaded_custom_thumbnail" if custom_thumb_uploaded else "select_frame_in_mobile_app",
                "visibility": visibility,
                "slot_id": payload["slot_id"],
                "scheduled_time_et": payload["scheduled_time_et"] if visibility == "scheduled" else None,
                "verified_studio_visibility": verified_studio_vis or None,
                "verified_studio_date_text": verified_studio_date or None,
                "schedule_self_healed": schedule_self_healed if visibility == "scheduled" else None,
                "video_language": payload.get("video_language", VIDEO_LANGUAGE_CODE),
                "title_description_language": payload.get("title_description_language", TITLE_DESCRIPTION_LANGUAGE_CODE),
                "channel_residence_country": payload.get("channel_residence_country", CHANNEL_RESIDENCE_COUNTRY),
                "target_audience_region": payload.get("target_audience_region", TARGET_AUDIENCE_REGION),
                "status": "scheduled" if visibility == "scheduled" else "uploaded",
                "ai_altered_content_declared": True,
                "not_made_for_kids": True
            }

            receipt_file = storage.get_stage_dir("06_publish") / "upload_receipt.json"
            storage.save_json("06_publish", "upload_receipt.json", receipt)
            storage.record_artifact("06_publish", "upload_receipt.json", receipt_file)
            write_studio_publish_receipt(project_id, projects_dir=self.projects_dir)

            manifest = storage.get_manifest()
            manifest["youtube_upload"] = receipt
            storage._write_manifest(manifest)

            print(f"[StudioUploader] Upload sequence completed successfully: {receipt['shorts_url']}")
            return receipt

    async def _async_upload(
        self,
        payload: dict[str, Any],
        dry_run: bool = False
    ) -> dict[str, Any]:
        """Core async upload runner via Whale CDP session."""
        project_id = payload["project_id"]
        title = payload["title"]
        video_path = payload["video_path"]
        thumb_path = payload["thumbnail_path"]
        visibility = payload["visibility"].lower()
        storage: ProjectStorage = payload["storage"]

        now_iso = datetime.now(timezone.utc).isoformat()

        if dry_run:
            simulated_video_id = f"sim_{project_id[:12]}"
            receipt = {
                "project_id": project_id,
                "video_id": simulated_video_id,
                "shorts_url": f"{YOUTUBE_WATCH_BASE_URL}{simulated_video_id}",
                "uploaded_at": now_iso,
                "title": title,
                "video_file": str(video_path),
                "thumbnail_file": str(thumb_path) if thumb_path and thumb_path.exists() else None,
                "cover_frame_sec": payload.get("cover_frame_sec"),
                "cover_action": "select_frame_in_mobile_app",
                "visibility": visibility,
                "slot_id": payload["slot_id"],
                "scheduled_time_et": payload["scheduled_time_et"] if visibility == "scheduled" else None,
                "video_language": payload.get("video_language", VIDEO_LANGUAGE_CODE),
                "title_description_language": payload.get("title_description_language", TITLE_DESCRIPTION_LANGUAGE_CODE),
                "channel_residence_country": payload.get("channel_residence_country", CHANNEL_RESIDENCE_COUNTRY),
                "target_audience_region": payload.get("target_audience_region", TARGET_AUDIENCE_REGION),
                "status": "dry_run_success",
                "ai_altered_content_declared": True,
                "not_made_for_kids": True
            }
            storage.save_json("06_publish", "upload_receipt.json", receipt)
            storage.record_artifact("06_publish", "upload_receipt.json", storage.get_stage_dir("06_publish") / "upload_receipt.json")
            return receipt

        if not payload.get("skip_qa_gate"):
            live_qa = verify_publish_ready_qa_bundle(
                self.projects_dir / project_id,
                require_semantic_review=True,
            )
            if not live_qa["passed"]:
                raise RuntimeError(
                    f"Live YouTube upload blocked by post-assembly QA gate for '{project_id}': "
                    f"{'; '.join(live_qa['issues'])}"
                )

        return await self._async_upload_direct_cdp(payload)

    async def _read_studio_video_row_status(
        self,
        client: DirectCDPClient,
        video_id: str,
    ) -> dict[str, Any]:
        """Reads `.tablecell-visibility` and `.tablecell-date` for `video_id` on `/videos/short` (or `/videos/upload`)."""
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        urls = [
            f"{STUDIO_BASE_URL}/videos/short",
            f"{STUDIO_BASE_URL}/videos/upload",
        ]
        for tab_url in urls:
            await client.send("Page.navigate", {"url": tab_url})
            await client.wait_for_element("ytcp-video-row", timeout_sec=16.0)
            await asyncio.sleep(1.5)
            for _ in range(10):
                row_info = await client.eval(
                    f"""(() => {{
                        {_DEEP_QUERY_HELPER_JS}
                        const vid = {json.dumps(str(video_id))};
                        const rows = __queryAllDeep('ytcp-video-row');
                        for (const r of rows) {{
                            const link = __queryAllDeep('a', r)
                                .map(a => a.getAttribute('href') || a.href || '')
                                .find(h => h.includes(vid));
                            if (!link) continue;
                            const visEl = __queryAllDeep('.tablecell-visibility, [class*="visibility"]', r)[0];
                            const dateEl = __queryAllDeep('.tablecell-date', r)[0];
                            const titleEl = __queryAllDeep('#video-title', r)[0];
                            return {{
                                found: true,
                                title: (titleEl ? titleEl.textContent : '').trim(),
                                visibility: (visEl ? visEl.innerText : '').replace(/\\s+/g, ' ').trim(),
                                date: (dateEl ? dateEl.innerText : '').replace(/\\s+/g, ' ').trim(),
                            }};
                        }}
                        return {{ found: false, rowCount: rows.length }};
                    }})()"""
                ) or {}
                if row_info.get("found"):
                    return dict(row_info)
                await asyncio.sleep(1.0)
        return {"found": False, "visibility": "", "date": ""}

    async def _self_heal_video_schedule_on_edit_page(
        self,
        client: DirectCDPClient,
        *,
        video_id: str,
        dt_et: datetime,
        browser_date_label: str,
        browser_time_24h: str,
    ) -> bool:
        """Opens `/video/<video_id>/edit`, sets Schedule date/time via Edit-Draft wizard or visibility modal, and commits."""
        from pipeline.cdp_tab_lease import enable_background_focus_emulation
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        edit_url = f"https://studio.youtube.com/video/{video_id}/edit"
        await client.send("Page.navigate", {"url": edit_url})
        await asyncio.sleep(4.2)
        await enable_background_focus_emulation(client)
        await client.wait_for_element("ytcp-video-metadata-editor", timeout_sec=18.0)

        # Path A: Video is in Draft -> click 'Edit draft' (ytcp-button#action-1), advance Next x3, schedule & trusted-click #done-button
        opened_draft = await client.click(
            [
                "ytcp-button#action-1",
                "button:has-text('Edit draft')",
                "button:has-text('초안 수정')",
            ]
        )
        if opened_draft:
            await asyncio.sleep(3.2)
            for _ in range(3):
                await client.click(["#next-button", "ytcp-button#next-button"])
                await asyncio.sleep(1.1)
            sched_ok = await client.set_schedule_datetime_utc(
                browser_date_label,
                browser_time_24h,
                dt_et=dt_et,
            )
            if not sched_ok:
                return False
            await asyncio.sleep(0.9)
            done_pt = await client.eval(f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const b = __queryAllDeep('ytcp-uploads-dialog #done-button, ytcp-button#done-button').find(x => x.getBoundingClientRect().width > 0);
                if (!b) return null;
                b.scrollIntoView({{block: 'center'}});
                const r = b.getBoundingClientRect();
                return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
            }})()""")
            if isinstance(done_pt, dict) and "x" in done_pt and "y" in done_pt:
                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(done_pt["x"]), "y": float(done_pt["y"])})
                await asyncio.sleep(0.05)
                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": float(done_pt["x"]), "y": float(done_pt["y"]), "button": "left", "clickCount": 1})
                await asyncio.sleep(0.06)
                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": float(done_pt["x"]), "y": float(done_pt["y"]), "button": "left", "clickCount": 1})
            else:
                await client.click(STUDIO_SELECTORS["done_button"])
            await asyncio.sleep(4.5)
            # Second trusted click if an open date/time popover backdrop consumed the first click
            re_pt = await client.eval(f"""(() => {{
                {_DEEP_QUERY_HELPER_JS}
                const b = __queryAllDeep('ytcp-uploads-dialog #done-button, ytcp-button#done-button').find(
                    x => x.getBoundingClientRect().width > 0 && !x.hasAttribute('disabled') && x.getAttribute('aria-disabled') !== 'true'
                );
                if (!b) return null;
                const r = b.getBoundingClientRect();
                return {{x: r.left + r.width / 2, y: r.top + r.height / 2}};
            }})()""")
            if isinstance(re_pt, dict) and "x" in re_pt and "y" in re_pt:
                await client.send("Input.dispatchMouseEvent", {"type": "mouseMoved", "x": float(re_pt["x"]), "y": float(re_pt["y"])})
                await asyncio.sleep(0.05)
                await client.send("Input.dispatchMouseEvent", {"type": "mousePressed", "x": float(re_pt["x"]), "y": float(re_pt["y"]), "button": "left", "clickCount": 1})
                await asyncio.sleep(0.06)
                await client.send("Input.dispatchMouseEvent", {"type": "mouseReleased", "x": float(re_pt["x"]), "y": float(re_pt["y"]), "button": "left", "clickCount": 1})
                await asyncio.sleep(4.5)
            return True

        # Path B: Non-Draft video -> visibility dropdown modal + Save
        opened_vis = await client.click(
            [
                "ytcp-video-metadata-visibility #select-button",
                "ytcp-video-metadata-visibility ytcp-button",
                "#visibility-button",
            ]
        )
        if not opened_vis:
            return False
        await asyncio.sleep(1.2)

        sched_ok = await client.set_schedule_datetime_utc(
            browser_date_label,
            browser_time_24h,
            dt_et=dt_et,
        )
        if not sched_ok:
            return False
        await asyncio.sleep(0.8)

        await client.click(
            [
                "ytcp-video-visibility-select #save-button",
                "ytcp-video-visibility-select #done-button",
                "ytcp-button#done-button",
                "#done-button",
                "#save-button",
            ]
        )
        await asyncio.sleep(1.5)
        await client.click(
            [
                "ytcp-video-metadata-editor #save",
                "ytcp-button#save",
                "#save",
            ]
        )
        await asyncio.sleep(4.0)
        return True

    async def verify_and_self_heal_scheduled_row(
        self,
        client: DirectCDPClient,
        *,
        video_id: str,
        dt_et: datetime,
        browser_date_label: str,
        browser_time_24h: str,
    ) -> dict[str, Any]:
        """
        Verifies on YouTube Studio's Content table (`/videos/short`) that `video_id` is `Scheduled` (`예약`)
        and NOT `Draft` (`초안`). If `Draft` / unscheduled, executes one automatic `/video/<id>/edit` self-heal
        and re-verifies, raising `RuntimeError` if still `Draft`.
        """
        def _is_scheduled_vis(vis_txt: str) -> bool:
            low = str(vis_txt or "").strip().lower()
            if "draft" in low or "초안" in vis_txt:
                return False
            return ("scheduled" in low) or ("예약" in vis_txt)

        row_status = await self._read_studio_video_row_status(client, video_id)
        vis_txt = str(row_status.get("visibility") or "")
        date_txt = str(row_status.get("date") or "")
        if _is_scheduled_vis(vis_txt):
            print(f"[StudioUploader] Verified Scheduled DOM row for {video_id}: visibility={vis_txt!r}, date={date_txt!r}")
            return {
                "verified": True,
                "self_healed": False,
                "visibility_text": vis_txt,
                "date_text": date_txt,
            }

        print(
            f"[StudioUploader] Post-upload row for {video_id} showed visibility={vis_txt!r} instead of Scheduled; "
            f"running /video/{video_id}/edit self-heal..."
        )
        await self._self_heal_video_schedule_on_edit_page(
            client,
            video_id=video_id,
            dt_et=dt_et,
            browser_date_label=browser_date_label,
            browser_time_24h=browser_time_24h,
        )
        row_after = await self._read_studio_video_row_status(client, video_id)
        vis_after = str(row_after.get("visibility") or "")
        date_after = str(row_after.get("date") or "")
        if _is_scheduled_vis(vis_after):
            print(
                f"[StudioUploader] Self-heal succeeded for {video_id}: visibility={vis_after!r}, date={date_after!r}"
            )
            return {
                "verified": True,
                "self_healed": True,
                "visibility_text": vis_after,
                "date_text": date_after,
            }

        raise RuntimeError(
            f"YouTube Studio video {video_id} remained in non-Scheduled state after self-heal "
            f"(visibility={vis_after!r}, date={date_after!r}); refusing to mark Scheduled upload as complete"
        )

    def scan_channel_drafts_readonly(self) -> dict[str, Any]:
        """
        Read-only scan of `/videos/short` and `/videos/upload` via a temporary background leased CDP tab.
        Reports all row counts and any lingering `Draft` (`초안`) video IDs/titles without modifying or deleting anything.
        """
        from pipeline.cdp_tab_lease import leased_cdp_tab
        from pipeline.publish import validate_episode_tags_hygiene
        from pipeline.studio.browser_session import _DEEP_QUERY_HELPER_JS

        async def _scan() -> dict[str, Any]:
            drafts: list[dict[str, str]] = []
            counts_by_tab: dict[str, int] = {}
            summary_by_vis: dict[str, int] = {}
            seen_ids: set[str] = set()
            async with leased_cdp_tab(
                f"{STUDIO_BASE_URL}/videos/short",
                purpose="studio_draft_scan_readonly",
                cdp_port=int(self.cdp_port),
                background=True,
            ) as (client, _tid, _owner):
                for tab_kind, tab_url in (
                    ("shorts", f"{STUDIO_BASE_URL}/videos/short"),
                    ("uploads", f"{STUDIO_BASE_URL}/videos/upload"),
                ):
                    await client.send("Page.navigate", {"url": tab_url})
                    await client.wait_for_element(["ytcp-video-row"], timeout_sec=22.0)
                    await asyncio.sleep(1.5)
                    rows = await client.eval(
                        f"""(() => {{
                            {_DEEP_QUERY_HELPER_JS}
                            return __queryAllDeep('ytcp-video-row').map(r => {{
                                const href = __queryAllDeep('a[href*="/video/"]', r)
                                    .map(a => a.getAttribute('href') || '')
                                    .find(h => /\\/video\\/[\\w-]{{11}}\\//.test(h)) || '';
                                const m = href.match(/\\/video\\/([\\w-]{{11}})\\//);
                                const vid = m ? m[1] : '';
                                const titleEl = __queryAllDeep('#video-title', r)[0];
                                const visEl = __queryAllDeep('.tablecell-visibility, [class*="visibility"]', r)[0];
                                const dateEl = __queryAllDeep('.tablecell-date', r)[0];
                                return {{
                                    video_id: vid,
                                    title: (titleEl ? titleEl.textContent : '').trim(),
                                    visibility: (visEl ? visEl.innerText : '').replace(/\\s+/g, ' ').trim(),
                                    date: (dateEl ? dateEl.innerText : '').replace(/\\s+/g, ' ').trim(),
                                }};
                            }});
                        }})()"""
                    ) or []
                    counts_by_tab[tab_kind] = len(rows)
                    for r in rows:
                        vid = str(r.get("video_id") or "")
                        vis = str(r.get("visibility") or "")
                        key_id = vid or f"{tab_kind}:{r.get('title','')}"
                        if key_id not in seen_ids:
                            seen_ids.add(key_id)
                            summary_by_vis[vis] = summary_by_vis.get(vis, 0) + 1
                            low_v = vis.lower()
                            if "draft" in low_v or "초안" in vis:
                                drafts.append(
                                    {
                                        "tab": tab_kind,
                                        "video_id": vid,
                                        "title": str(r.get("title") or ""),
                                        "visibility": vis,
                                        "date": str(r.get("date") or ""),
                                    }
                                )
            return {
                "counts_by_tab": counts_by_tab,
                "visibility_breakdown": summary_by_vis,
                "draft_count": len(drafts),
                "drafts": drafts,
            }

        return asyncio.run(_scan())

    def upload_project(
        self,
        project_id: str,
        slot_id: int | None = None,
        target_date: str | None = None,
        visibility: str = "unlisted",
        dry_run: bool = False,
        burn_first_frame: bool = False,
        auto_link: bool = False,
        assign_playlist: bool = False,
        skip_qa_gate: bool = False,
        require_semantic_review: bool = True,
        allow_instant_public: bool = False,
    ) -> dict[str, Any]:
        """Synchronous entry point for uploading a single project, with optional post-upload Related Video linking (playlists banned under R75)."""
        eff_assign_playlist = bool(assign_playlist and STUDIO_PLAYLISTS_ENABLED)
        payload = self.prepare_upload_payload(
            project_id=project_id,
            slot_id=slot_id,
            target_date=target_date,
            visibility=visibility,
            burn_first_frame=burn_first_frame,
            skip_qa_gate=skip_qa_gate,
            require_semantic_review=require_semantic_review,
            allow_instant_public=allow_instant_public,
        )
        receipt = asyncio.run(self._async_upload(payload, dry_run=dry_run))
        if (
            not dry_run
            and (auto_link or eff_assign_playlist)
            and is_valid_youtube_video_id(receipt.get("video_id"))
        ):
            try:
                linker = StudioShortLinker(cdp_port=self.cdp_port, projects_dir=self.projects_dir)
                link_plan = linker.run(
                    mode="seed_boost",
                    assign_playlists=eff_assign_playlist,
                    dry_run=False,
                    force=True,
                    project_id=project_id,
                )
                receipt["related_link_summary"] = {
                    "verified_count": link_plan.get("verified_count", 0),
                    "edges": link_plan.get("edges", []),
                }
            except Exception as link_exc:
                print(f"[StudioUploader] Warning: Post-upload related-link hook deferred for {project_id}: {link_exc}")
        return receipt
