"""
ALL ABOUT BRAIN — Standalone 16:9 (`1920x1080 @ 24fps`, `-14.0 LUFS`) Full HD Long-Form Assembler
(`pipeline/longform_assembler.py`).

100% isolated from `9:16` Shorts `diorama_assembler.py`.
Scales native `16:9` Google Flow clips cleanly to `1920x1080` (`Lanczos` + subtle clarity unsharp, `H.264 High -level:v 4.2 -crf 18`),
starts bright immediately at `t=0.0s` (zero black fade on frame 0; gentle `0.45s` transitions only on `idx > 0` chapter boundaries),
supports `split_hstack` (`960x1080` + `3px` `#FFFFFF` divider), burns in `04_audio/subtitles.ass` (`Default` + lower-left `DocCitationCard`),
and generates `< 2 MB` `1920x1080` `A/B/C` thumbnails.
"""

from __future__ import annotations

import json
import shutil
import subprocess
import tempfile
import wave
from pathlib import Path
from typing import Any

import cv2

from pipeline.config import (
    DIORAMA_MUX_TRUE_PEAK_LIMITER,
    FONT_CONDENSED_BLACK_PATH,
    LONGFORM_CHAPTER_FADE_SEC,
    LONGFORM_FINAL_MP4_FILENAME,
    LONGFORM_H264_CRF,
    LONGFORM_H264_LEVEL,
    LONGFORM_H264_PROFILE,
    LONGFORM_SPLIT_DIVIDER_PX,
    LONGFORM_TARGET_LUFS,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PROJECTS_DIR,
)
from pipeline.diorama_assembler import ensure_bundled_condensed_font
from pipeline.longform_prompt_builder import resolve_longform_project_dir
from pipeline.thumbnail_studio import render_longform_4k_thumbnails


def _resolve_ffmpeg_bin() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def _probe_clip_dur(mp4_path: Path) -> float:
    cap = cv2.VideoCapture(str(mp4_path))
    fps_c = float(cap.get(cv2.CAP_PROP_FPS) or LONGFORM_VIDEO_FPS)
    fc_c = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap.release()
    return (fc_c / fps_c) if (fps_c > 0 and fc_c > 0) else 0.0


def assemble_longform_episode(
    project_id_or_dir: str | Path,
    hook_text: str = "THE HIDDEN CIRCUIT",
) -> dict[str, Any]:
    p_dir = resolve_longform_project_dir(project_id_or_dir, create=False)
    vis_dir = p_dir / "03_visuals" / "flow_native_clips"
    aud_wav = p_dir / "04_audio" / "audio_master.wav"
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    pros_path = p_dir / "04_audio" / "prosody_report.json"
    asm_dir = p_dir / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)

    clips = sorted(vis_dir.glob("clip_*.mp4"), key=lambda p: int("".join(filter(str.isdigit, p.stem)) or "0"))
    if not clips:
        raise FileNotFoundError(f"No native 16:9 clips found in {vis_dir}")
    if not aud_wav.exists():
        raise FileNotFoundError(f"Missing master narration track: {aud_wav}")

    aud_dur_sec = 0.0
    try:
        with wave.open(str(aud_wav), "rb") as wf:
            aud_dur_sec = wf.getnframes() / float(max(wf.getframerate(), 1))
    except Exception:
        aud_dur_sec = 0.0

    vp_doc: dict[str, Any] = {}
    chapter_start_indices: set[int] = {0}
    vp_path = p_dir / "03_visuals" / "visual_plan.json"
    if vp_path.exists():
        try:
            vp_doc = json.loads(vp_path.read_text(encoding="utf-8"))
            prev_act = None
            for idx_c, c_spec in enumerate(vp_doc.get("clips") or []):
                cur_act = c_spec.get("chapter") or c_spec.get("act")
                if bool(c_spec.get("chapter_break")) or (cur_act is not None and prev_act is not None and cur_act != prev_act):
                    chapter_start_indices.add(idx_c)
                if cur_act is not None:
                    prev_act = cur_act
            if hook_text == "THE HIDDEN CIRCUIT":
                plan_hook = str((vp_doc.get("thumbnail") or {}).get("hook_text") or "").strip()
                if plan_hook:
                    hook_text = plan_hook
        except Exception:
            pass
    if len(chapter_start_indices) == 1 and len(clips) >= 12:
        for idx_c in range(10, len(clips), 10):
            chapter_start_indices.add(idx_c)

    plan_clips = list(vp_doc.get("clips") or [])
    raw_durs = [_probe_clip_dur(c) for c in clips]
    seg_target_durs: list[float] = []
    for idx, rd in enumerate(raw_durs):
        if idx < len(plan_clips) and float(plan_clips[idx].get("target_duration_sec") or 0.0) > 0:
            seg_target_durs.append(float(plan_clips[idx]["target_duration_sec"]))
        else:
            seg_target_durs.append(rd)

    total_vid_sec = sum(seg_target_durs)
    tail_pad_sec = max(0.0, aud_dur_sec + 0.15 - total_vid_sec) if aud_dur_sec > 0 else 0.0

    ffmpeg_bin = _resolve_ffmpeg_bin()
    seg_dir = asm_dir / "_longform_1080p_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    concat_lines: list[str] = []
    sample_frames = []

    for idx, c_mp4 in enumerate(clips):
        seg_out = seg_dir / f"seg_{idx + 1:03d}.mp4"
        c_spec = plan_clips[idx] if idx < len(plan_clips) else {}
        t_dur = seg_target_durs[idx] + (tail_pad_sec if idx == len(clips) - 1 else 0.0)
        raw_d = max(0.1, raw_durs[idx])
        extra_clone = max(0.0, t_dur + 0.08 - raw_d)

        is_split = (
            c_spec.get("split_mode") == "split_hstack"
            and c_spec.get("secondary_clip_path")
            and (p_dir / str(c_spec["secondary_clip_path"])).exists()
        )
        if is_split:
            sec_mp4 = p_dir / str(c_spec["secondary_clip_path"])
            sec_d = max(0.1, _probe_clip_dur(sec_mp4))
            extra_l = max(0.0, t_dur + 0.08 - raw_d)
            extra_r = max(0.0, t_dur + 0.08 - sec_d)
            tpad_l = f",tpad=stop_mode=clone:stop_duration={extra_l:.3f}" if extra_l > 0.02 else ""
            tpad_r = f",tpad=stop_mode=clone:stop_duration={extra_r:.3f}" if extra_r > 0.02 else ""
            fade_tail = (
                f",fade=t=in:st=0:d={LONGFORM_CHAPTER_FADE_SEC:.2f}"
                if (idx > 0 and idx in chapter_start_indices)
                else ""
            )
            half_w = (LONGFORM_VIDEO_WIDTH - LONGFORM_SPLIT_DIVIDER_PX) // 2
            rem_w = LONGFORM_VIDEO_WIDTH - LONGFORM_SPLIT_DIVIDER_PX - half_w
            fc_filter = (
                f"[0:v]scale={half_w}:{LONGFORM_VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={half_w}:{LONGFORM_VIDEO_HEIGHT},fps={LONGFORM_VIDEO_FPS}{tpad_l}[left];"
                f"[1:v]scale={rem_w}:{LONGFORM_VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"crop={rem_w}:{LONGFORM_VIDEO_HEIGHT},fps={LONGFORM_VIDEO_FPS}{tpad_r}[right];"
                f"color=c=white:s={LONGFORM_SPLIT_DIVIDER_PX}x{LONGFORM_VIDEO_HEIGHT}:r={LONGFORM_VIDEO_FPS}:d={t_dur + 0.25:.3f}[div];"
                f"[left][div][right]hstack=inputs=3,trim=duration={t_dur:.3f},setpts=PTS-STARTPTS{fade_tail}[vout]"
            )
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(c_mp4),
                    "-i",
                    str(sec_mp4),
                    "-an",
                    "-filter_complex",
                    fc_filter,
                    "-map",
                    "[vout]",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "superfast",
                    "-crf",
                    "14",
                    "-r",
                    str(LONGFORM_VIDEO_FPS),
                    "-video_track_timescale",
                    str(LONGFORM_VIDEO_FPS * 1000),
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_out),
                ],
                check=True,
                capture_output=True,
            )
        else:
            vf_parts = [
                f"scale={LONGFORM_VIDEO_WIDTH}:{LONGFORM_VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos",
                f"crop={LONGFORM_VIDEO_WIDTH}:{LONGFORM_VIDEO_HEIGHT}",
                "unsharp=5:5:0.35:3:3:0.0",
                f"fps={LONGFORM_VIDEO_FPS}",
            ]
            if extra_clone > 0.02:
                vf_parts.append(f"tpad=stop_mode=clone:stop_duration={extra_clone:.3f}")
            if t_dur > 0.1:
                vf_parts.append(f"trim=duration={t_dur:.3f}")
                vf_parts.append("setpts=PTS-STARTPTS")
            # Bright start at t=0.0s (idx == 0 NEVER fades from black; only idx > 0 chapter transitions fade gently)
            if idx > 0 and idx in chapter_start_indices:
                vf_parts.append(f"fade=t=in:st=0:d={LONGFORM_CHAPTER_FADE_SEC:.2f}")
            vf = ",".join(vf_parts)
            subprocess.run(
                [
                    ffmpeg_bin,
                    "-nostdin",
                    "-hide_banner",
                    "-loglevel",
                    "error",
                    "-y",
                    "-i",
                    str(c_mp4),
                    "-an",
                    "-vf",
                    vf,
                    "-c:v",
                    "libx264",
                    "-preset",
                    "superfast",
                    "-crf",
                    "14",
                    "-r",
                    str(LONGFORM_VIDEO_FPS),
                    "-video_track_timescale",
                    str(LONGFORM_VIDEO_FPS * 1000),
                    "-pix_fmt",
                    "yuv420p",
                    str(seg_out),
                ],
                check=True,
                capture_output=True,
            )
        concat_lines.append(f"file '{seg_out.resolve()}'")
        if len(sample_frames) < 3:
            cap = cv2.VideoCapture(str(c_mp4))
            ok, frm = cap.read()
            cap.release()
            if ok and frm is not None:
                sample_frames.append(frm)

    concat_txt = seg_dir / "concat.txt"
    concat_txt.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
    out_mp4 = asm_dir / LONGFORM_FINAL_MP4_FILENAME

    af_mux = (
        DIORAMA_MUX_TRUE_PEAK_LIMITER
        if pros_path.exists()
        else f"loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9,{DIORAMA_MUX_TRUE_PEAK_LIMITER}"
    )

    with tempfile.TemporaryDirectory(prefix="aab_lf_mux_") as td:
        mux_cmd = [
            ffmpeg_bin,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-f",
            "concat",
            "-safe",
            "0",
            "-i",
            str(concat_txt),
            "-i",
            str(aud_wav),
            "-af",
            af_mux,
        ]
        if ass_path.exists():
            font_path = ensure_bundled_condensed_font(FONT_CONDENSED_BLACK_PATH)
            tmp_ass = Path(td) / "subtitles.ass"
            tmp_fonts = Path(td) / "fonts"
            tmp_fonts.mkdir(parents=True, exist_ok=True)
            shutil.copy2(ass_path, tmp_ass)
            shutil.copy2(font_path, tmp_fonts / font_path.name)
            vf_mux = f"fps={LONGFORM_VIDEO_FPS},ass=filename='{tmp_ass.as_posix()}':fontsdir='{tmp_fonts.as_posix()}'"
        else:
            vf_mux = f"fps={LONGFORM_VIDEO_FPS}"

        mux_cmd.extend(
            [
                "-vf",
                vf_mux,
                "-c:v",
                "libx264",
                "-profile:v",
                LONGFORM_H264_PROFILE,
                "-level:v",
                LONGFORM_H264_LEVEL,
                "-preset",
                "fast",
                "-crf",
                str(LONGFORM_H264_CRF),
                "-r",
                str(LONGFORM_VIDEO_FPS),
                "-video_track_timescale",
                str(LONGFORM_VIDEO_FPS * 1000),
                "-pix_fmt",
                "yuv420p",
                "-c:a",
                "aac",
                "-b:a",
                "192k",
            ]
        )
        if aud_dur_sec > 0:
            mux_cmd.extend(["-t", f"{aud_dur_sec + 0.12:.3f}"])
        mux_cmd.extend(["-movflags", "+faststart", str(out_mp4)])
        subprocess.run(mux_cmd, check=True, capture_output=True)

    cap_out = cv2.VideoCapture(str(out_mp4))
    out_fps = float(cap_out.get(cv2.CAP_PROP_FPS) or LONGFORM_VIDEO_FPS)
    out_fc = float(cap_out.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap_out.release()
    final_dur = round((out_fc / out_fps) if (out_fps > 0 and out_fc > 0) else max(total_vid_sec, aud_dur_sec), 2)

    ref_frames: list[Any] = []
    ref_dir = p_dir / "03_visuals" / "reference_images"
    if ref_dir.is_dir():
        ref_pngs = sorted(ref_dir.glob("*.png"))
        if len(ref_pngs) >= 3:
            brain_pngs = [p for p in ref_pngs if "brain" in p.stem]
            room_pngs = [p for p in ref_pngs if "brain" not in p.stem]
            for rp in (brain_pngs[:1] + room_pngs[:2] + ref_pngs)[:3]:
                im = cv2.imread(str(rp))
                if im is not None:
                    ref_frames.append(im)

    thumb_rep = render_longform_4k_thumbnails(p_dir, ref_frames or sample_frames, hook=hook_text)
    rep = {
        "passed": out_mp4.exists() and out_mp4.stat().st_size > 0,
        "project_id": p_dir.name,
        "final_mp4": str(out_mp4),
        "duration_sec": final_dur,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "target_lufs": LONGFORM_TARGET_LUFS,
        "subtitles_burned_in": ass_path.exists(),
        "clip_count": len(clips),
        "chapter_starts": sorted(chapter_start_indices),
        "thumbnails": thumb_rep,
    }
    (asm_dir / "longform_assembly_report.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return rep


# Backward-compatible symbol name
assemble_longform_4k_episode = assemble_longform_episode
