"""
ALL ABOUT BRAIN — 16:9 4K (`3840x2160 @ 24fps`, `-14.0 LUFS`) CTV Long-Form Assembler (`pipeline/longform_assembler.py`).

Upscales native `16:9` Google Flow clips to `3840x2160` (`Lanczos` + subtle unsharp mask for crisp living-room Smart TV
playback), inserts `LONGFORM_CHAPTER_FADE_SEC` (`0.45s`) acoustic/visual chapter valleys for clean mid-roll ad placement,
normalizes stereo audio to `LONGFORM_TARGET_LUFS` (`-14.0 LUFS`), and generates 4K `A/B/C` thumbnails for YouTube
`Test & Compare`.
"""

from __future__ import annotations

import json
import shutil
import subprocess
from pathlib import Path
from typing import Any

import cv2

from pipeline.config import (
    LONGFORM_CHAPTER_FADE_SEC,
    LONGFORM_TARGET_LUFS,
    LONGFORM_VIDEO_FPS,
    LONGFORM_VIDEO_HEIGHT,
    LONGFORM_VIDEO_WIDTH,
    PROJECTS_DIR,
)
from pipeline.thumbnail_studio import render_longform_4k_thumbnails


def _resolve_ffmpeg_bin() -> str:
    sys_ff = shutil.which("ffmpeg")
    if sys_ff:
        return sys_ff
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


def assemble_longform_4k_episode(
    project_id_or_dir: str | Path,
    hook_text: str = "THE HIDDEN CIRCUIT",
) -> dict[str, Any]:
    p_dir = Path(project_id_or_dir) if Path(project_id_or_dir).is_dir() else (Path(PROJECTS_DIR) / str(project_id_or_dir))
    vis_dir = p_dir / "03_visuals" / "flow_native_clips"
    aud_wav = p_dir / "04_audio" / "audio_master.wav"
    asm_dir = p_dir / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)

    clips = sorted(vis_dir.glob("clip_*.mp4"), key=lambda p: int("".join(filter(str.isdigit, p.stem)) or "0"))
    if not clips:
        raise FileNotFoundError(f"No native 16:9 clips found in {vis_dir}")
    if not aud_wav.exists():
        raise FileNotFoundError(f"Missing master narration track: {aud_wav}")

    import wave

    aud_dur_sec = 0.0
    try:
        with wave.open(str(aud_wav), "rb") as wf:
            aud_dur_sec = wf.getnframes() / float(max(wf.getframerate(), 1))
    except Exception:
        aud_dur_sec = 0.0

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
        except Exception:
            pass
    if len(chapter_start_indices) == 1 and len(clips) >= 12:
        for idx_c in range(10, len(clips), 10):
            chapter_start_indices.add(idx_c)

    clip_durs: list[float] = []
    for c_mp4 in clips:
        cap = cv2.VideoCapture(str(c_mp4))
        fps_c = float(cap.get(cv2.CAP_PROP_FPS) or LONGFORM_VIDEO_FPS)
        fc_c = float(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
        cap.release()
        clip_durs.append((fc_c / fps_c) if (fps_c > 0 and fc_c > 0) else 0.0)
    total_vid_sec = sum(clip_durs)
    tail_pad_sec = max(0.0, aud_dur_sec + 0.35 - total_vid_sec) if aud_dur_sec > 0 else 0.0

    ffmpeg_bin = _resolve_ffmpeg_bin()
    seg_dir = asm_dir / "_longform_4k_segments"
    seg_dir.mkdir(parents=True, exist_ok=True)
    concat_lines: list[str] = []
    sample_frames = []

    for idx, c_mp4 in enumerate(clips):
        seg_out = seg_dir / f"seg_{idx + 1:03d}.mp4"
        vf_parts = [
            f"scale={LONGFORM_VIDEO_WIDTH}:{LONGFORM_VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos",
            f"crop={LONGFORM_VIDEO_WIDTH}:{LONGFORM_VIDEO_HEIGHT}",
            "unsharp=5:5:0.45:3:3:0.0",
            f"fps={LONGFORM_VIDEO_FPS}",
        ]
        if idx in chapter_start_indices:
            vf_parts.append(f"fade=t=in:st=0:d={LONGFORM_CHAPTER_FADE_SEC:.2f}")
        if idx == len(clips) - 1 and tail_pad_sec > 0.02:
            vf_parts.append(f"tpad=stop_mode=clone:stop_duration={tail_pad_sec:.3f}")
        vf = ",".join(vf_parts)
        subprocess.run(
            [
                ffmpeg_bin,
                "-y",
                "-i",
                str(c_mp4),
                "-an",
                "-vf",
                vf,
                "-c:v",
                "libx264",
                "-preset",
                "fast",
                "-crf",
                "18",
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
    out_mp4 = asm_dir / "final_longform_3840x2160.mp4"

    mux_cmd = [
        ffmpeg_bin,
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
        f"loudnorm=I={LONGFORM_TARGET_LUFS}:TP=-1.5:LRA=9",
        "-c:v",
        "copy",
        "-c:a",
        "aac",
        "-b:a",
        "192k",
    ]
    if aud_dur_sec > 0:
        mux_cmd.extend(["-t", f"{aud_dur_sec + 0.35:.3f}"])
    mux_cmd.extend(["-movflags", "+faststart", str(out_mp4)])
    subprocess.run(mux_cmd, check=True, capture_output=True)

    cap_out = cv2.VideoCapture(str(out_mp4))
    out_fps = float(cap_out.get(cv2.CAP_PROP_FPS) or LONGFORM_VIDEO_FPS)
    out_fc = float(cap_out.get(cv2.CAP_PROP_FRAME_COUNT) or 0.0)
    cap_out.release()
    final_dur = round((out_fc / out_fps) if (out_fps > 0 and out_fc > 0) else max(total_vid_sec, aud_dur_sec), 2)

    thumb_rep = render_longform_4k_thumbnails(p_dir, sample_frames, hook=hook_text)
    rep = {
        "passed": out_mp4.exists() and out_mp4.stat().st_size > 0,
        "project_id": p_dir.name,
        "final_mp4": str(out_mp4),
        "duration_sec": final_dur,
        "resolution": [LONGFORM_VIDEO_WIDTH, LONGFORM_VIDEO_HEIGHT],
        "fps": LONGFORM_VIDEO_FPS,
        "target_lufs": LONGFORM_TARGET_LUFS,
        "clip_count": len(clips),
        "chapter_starts": sorted(chapter_start_indices),
        "thumbnails": thumb_rep,
    }
    (asm_dir / "longform_assembly_report.json").write_text(
        json.dumps(rep, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return rep
