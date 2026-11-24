"""ALL ABOUT BRAIN — 30fps Optical-Flow Segment Renderer & Multi-Stage Assembler (`assembler.py`)."""

from __future__ import annotations
from pipeline import config as _cfg
from pipeline.assembler_subtitles import *
from pipeline.assembler_audio import *
from pipeline.assembler_edl import *
from pipeline.assembler_subtitles import _KEYWORD_BEAT_SPLIT_RE, _V7_DEFAULT_CAM_CYCLE, _V8_POWER_TOKENS, _V8_STOPWORDS, _clip_duration, _ffmpeg, _format_ass_ts, _frame_boundary_ass_sec, _parse_ass_time, _sanitize_ass_multiline, _sanitize_ass_single_line, _write_mono_wav, ensure_bundled_condensed_font, generate_diorama_ass_subtitles, probe_ass_font_resolution
from pipeline.assembler_audio import _measure_true_peak_dbtp, _synthesize_documentary_pulse_bgm, _synthesize_expressive_v8_ambience_and_foley, _synthesize_stereo_orchestral_bgm, _synthesize_v8_foley_oneshot, _write_stereo_wav, generate_diorama_audio_master
from pipeline.assembler_edl import _compute_max_clip_reuse, _normalize_v7_anatomy_badge_text, _resolve_diorama_clip_files, _resolve_v7_clip_camera, _resolve_v7_cut_anatomy_label, _select_v7_source_window, _sentence_act_map, build_crosscut_edl, build_dual_harvest_edl_windows, build_v7_dynamic_edl, compute_locked_edl_cut_frame_requirements, compute_script_freshness_digests, enforce_combined_r88a_r89_edl_contract, load_diorama_script_sentences, lock_audio_durations_onto_visual_plan, resolve_overlay_window_conflicts, resolve_spatial_metric_stamps, split_sentences_at_keyword_beats, verify_script_audio_freshness, verify_state_swap_hist_corr

def _compute_v7_pastel_eq_filter(clip_path: Path) -> str:
    """Computes an adaptive FFmpeg `eq` pastel saturation/luma grade across the active NLE window while leaving pastel clips untouched."""
    from pipeline.media_cache import cached_by_clip_stat

    def _probe_pastel_eq(local_p: Path) -> str:
        cap = cv2.VideoCapture(str(local_p))
        if not cap.isOpened():
            return ""
        fc = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        sats: list[float] = []
        lumas: list[float] = []
        fracs = (0.12, 0.25, 0.42) if fc >= 12 else (0.5,)
        for fr in fracs:
            if fc > 1:
                cap.set(cv2.CAP_PROP_POS_FRAMES, max(0, min(fc - 1, int(round(fc * fr)))))
            ok, frm = cap.read()
            if ok and frm is not None:
                hsv = cv2.cvtColor(frm, cv2.COLOR_BGR2HSV)
                gray = cv2.cvtColor(frm, cv2.COLOR_BGR2GRAY)
                sats.append(float(np.mean(hsv[:, :, 1])))
                lumas.append(float(np.mean(gray)))
        cap.release()
        if not lumas:
            return ""
        raw_sat = float(np.mean(sats))
        raw_luma = float(np.mean(lumas))
        min_luma = float(min(lumas))
        if raw_sat <= 42.0 and 112.0 <= raw_luma <= 146.0 and min_luma >= 96.0:
            return ""
        sat_mul = min(1.0, max(0.38, 36.5 / max(1.0, raw_sat))) if raw_sat > 42.0 else 1.0
        if min_luma < 96.0:
            bright_shift = float(np.clip((108.0 - min_luma) / 380.0, 0.015, 0.065))
        elif raw_luma > 146.0:
            bright_shift = float(np.clip((134.0 - raw_luma) / 520.0, -0.045, 0.0))
        elif raw_luma < 112.0:
            bright_shift = float(np.clip((124.0 - raw_luma) / 480.0, 0.0, 0.040))
        else:
            bright_shift = 0.0
        if abs(sat_mul - 1.0) < 0.02 and abs(bright_shift) < 0.005:
            return ""
        return f"eq=saturation={sat_mul:.3f}:brightness={bright_shift:.3f},"

    return str(cached_by_clip_stat(Path(clip_path), namespace="pastel_eq_v1", compute_fn=_probe_pastel_eq))


def _probe_segment_frame_count(seg_path: Path) -> int:
    """Probes exact video frame count of a rendered cut/xfade segment (fast metadata + decode fallback)."""
    if not seg_path.is_file() or seg_path.stat().st_size <= 0:
        return 0
    cap = cv2.VideoCapture(str(seg_path))
    if not cap.isOpened():
        return 0
    try:
        meta_cnt = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        if meta_cnt > 0:
            return meta_cnt
        cnt = 0
        while True:
            ok, _ = cap.read()
            if not ok:
                break
            cnt += 1
        return cnt
    finally:
        cap.release()


def _execute_xfade_batch_ffmpeg(
    ff: str,
    batch_inputs: list[tuple[Path, int, str, int]],
    out_path: Path,
    fps: int,
    *,
    target_crf: int = 18,
    ass_filter: str = "",
    burn_start_sec: float | None = None,
    cwd: Path | None = None,
    ffmpeg_threads: int = 2,
) -> int:
    """Validates input frame counts & xfade offsets and merges `batch_inputs` into `out_path` without silent truncation."""
    in_frame_counts: list[int] = []
    for b_idx, (raw_p, req_eff_f, _xf_k, req_ov_f) in enumerate(batch_inputs):
        actual_in_f = _probe_segment_frame_count(raw_p)
        min_needed_f = int(req_eff_f) + (
            int(req_ov_f) + 1 if (b_idx < len(batch_inputs) - 1 and int(req_ov_f) > 0) else 0
        )
        if actual_in_f < min_needed_f:
            raise RuntimeError(
                f"FFmpeg xfade input {raw_p.name} has {actual_in_f} frames (< required {min_needed_f} frames)"
            )
        in_frame_counts.append(actual_in_f)

    fc_parts: list[str] = [
        f"[{b_i}:v]setpts=PTS-STARTPTS,fps={fps}[vin{b_i}]"
        for b_i in range(len(batch_inputs))
    ]
    prev_lbl = "[vin0]"
    acc_f = 0
    avail_f = in_frame_counts[0]
    for m_idx in range(1, len(batch_inputs)):
        _prev_raw, prev_eff_f, prev_xf_kind, prev_ov_f = batch_inputs[m_idx - 1]
        acc_f += prev_eff_f
        nxt_lbl = f"[xf{m_idx}]"
        off_sec = acc_f / float(fps)
        ov_sec = prev_ov_f / float(fps)
        avail_dur = avail_f / float(fps)
        if not (off_sec < avail_dur - ov_sec - 1e-6):
            raise RuntimeError(
                f"Invalid xfade offset {off_sec:.6f}s >= avail_dur {avail_dur:.6f}s - overlap {ov_sec:.6f}s "
                f"at chain index {m_idx}"
            )
        fc_parts.append(
            f"{prev_lbl}[vin{m_idx}]xfade=transition={prev_xf_kind}:duration={ov_sec:.6f}:offset={off_sec:.6f}{nxt_lbl}"
        )
        avail_f = acc_f + in_frame_counts[m_idx]
        prev_lbl = nxt_lbl

    is_final_stage = burn_start_sec is not None
    if is_final_stage:
        total_out_f = sum(int(x[1]) for x in batch_inputs)
        ass_chain = f",{ass_filter}" if ass_filter else ""
        fc_parts.append(
            f"{prev_lbl}fps={fps},setpts=PTS+{float(burn_start_sec):.6f}/TB{ass_chain},setpts=PTS-STARTPTS,format=yuv420p[vout]"
        )
        enc_preset = "ultrafast"
        enc_crf = str(max(14, int(target_crf) - 2))
    else:
        tail_ov_f = int(batch_inputs[-1][3])
        total_out_f = sum(int(x[1]) for x in batch_inputs) + (tail_ov_f + 1 if tail_ov_f > 0 else 0)
        fc_parts.append(f"{prev_lbl}fps={fps},setpts=PTS-STARTPTS,format=yuv420p[vout]")
        enc_preset = "ultrafast"
        enc_crf = str(max(13, int(target_crf) - 3))

    in_args: list[str] = []
    for raw_p, _, _, _ in batch_inputs:
        in_args.extend(["-i", raw_p.name if cwd is not None else str(raw_p)])
    out_arg = out_path.name if cwd is not None else str(out_path)
    res_xf = subprocess.run(
        [
            ff,
            "-nostdin",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            *in_args,
            "-filter_complex",
            ";".join(fc_parts),
            "-map",
            "[vout]",
            "-frames:v",
            str(total_out_f),
            "-r",
            str(fps),
            "-c:v",
            "libx264",
            "-preset",
            enc_preset,
            "-crf",
            enc_crf,
            "-profile:v",
            "high",
            "-level:v",
            "4.2",
            "-x264-params",
            "stitchable=1",
            "-video_track_timescale",
            str(fps * 1000),
            "-threads",
            str(max(1, int(ffmpeg_threads))),
            "-pix_fmt",
            "yuv420p",
            "-an",
            out_arg,
        ],
        cwd=str(cwd) if cwd is not None else None,
        capture_output=True,
        text=True,
        check=False,
        timeout=240,
        stdin=subprocess.DEVNULL,
    )
    if res_xf.returncode != 0 or not out_path.exists():
        raise RuntimeError(f"FFmpeg Track-V1 camera transition xfade failed: {(res_xf.stderr or '')[:300]}")
    rendered_xf_f = _probe_segment_frame_count(out_path)
    if rendered_xf_f < total_out_f:
        raise RuntimeError(
            f"FFmpeg Track-V1 xfade output {out_path.name} truncated ({rendered_xf_f} < {total_out_f} frames)"
        )
    return rendered_xf_f


def _merge_xfade_group_multistage(
    ff: str,
    grp_inputs: list[tuple[Path, int, str, int]],
    out_path: Path,
    fps: int,
    *,
    target_crf: int = 18,
    ass_filter: str = "",
    burn_start_sec: float | None = 0.0,
    cwd: Path | None = None,
    group_idx: int = 0,
    n_workers: int | None = None,
) -> int:
    """Multi-stage (<=4-input per FFmpeg call) xfade merger preserving exact frame counts across mixed timebases."""
    eff_workers = int(n_workers) if (n_workers is not None and int(n_workers) >= 1) else resolve_xfade_workers()
    eff_ff_threads = resolve_ffmpeg_threads_per_worker(eff_workers)
    work_dir = cwd if cwd is not None else out_path.parent
    cur_stage = list(grp_inputs)
    stage_round = 0
    while len(cur_stage) > 4:
        chunks = [cur_stage[i : i + 4] for i in range(0, len(cur_stage), 4)]
        next_stage: list[tuple[Path, int, str, int]] = []
        sub_jobs: list[tuple[list[tuple[Path, int, str, int]], Path]] = []
        for ch_idx, chunk in enumerate(chunks):
            if len(chunk) == 1:
                next_stage.append(chunk[0])
            else:
                mid_p = work_dir / f"xfmid_g{group_idx}_r{stage_round}_{ch_idx}.mp4"
                sub_jobs.append((chunk, mid_p))
                next_stage.append((mid_p, sum(int(x[1]) for x in chunk), chunk[-1][2], int(chunk[-1][3])))
        if sub_jobs:
            with ThreadPoolExecutor(max_workers=min(max(1, eff_workers), len(sub_jobs))) as xf_pool:
                list(
                    xf_pool.map(
                        lambda jb: _execute_xfade_batch_ffmpeg(
                            ff=ff,
                            batch_inputs=jb[0],
                            out_path=jb[1],
                            fps=fps,
                            target_crf=int(target_crf),
                            ass_filter="",
                            burn_start_sec=None,
                            cwd=work_dir,
                            ffmpeg_threads=eff_ff_threads,
                        ),
                        sub_jobs,
                    )
                )
        cur_stage = next_stage
        stage_round += 1
    return _execute_xfade_batch_ffmpeg(
        ff=ff,
        batch_inputs=cur_stage,
        out_path=out_path,
        fps=fps,
        target_crf=int(target_crf),
        ass_filter=ass_filter,
        burn_start_sec=burn_start_sec,
        cwd=work_dir,
        ffmpeg_threads=resolve_ffmpeg_threads_per_worker(1),
    )


def _clamp_source_window_to_eof(
    clip_path: Path,
    s0_in: float,
    s1_in: float,
    min_span: float = 0.20,
) -> tuple[float, float]:
    """Shifts `s0` backward and clamps `s1` when a cut window approaches or exceeds source clip EOF."""
    s0 = max(0.0, float(s0_in))
    s1 = max(s0 + min_span, float(s1_in))
    actual_dur = float(_clip_duration(clip_path) or 0.0)
    if actual_dur <= min_span:
        return s0, s1
    req_span = max(min_span, s1 - s0)
    safe_eof = max(min_span, actual_dur - 0.015)
    if s1 > safe_eof:
        s0 = max(0.0, min(s0, safe_eof - req_span))
        s1 = max(s0 + min(min_span, safe_eof), min(s1, actual_dur))
    return round(s0, 5), round(s1, 5)


def _upsample_clip_window_optical_flow(
    ff: str,
    src_path: Path,
    s0: float,
    s1: float,
    target_fps: int,
    *,
    tail_pad_sec: float = 0.22,
) -> tuple[Path, float] | None:
    """
    Upsamples `[s0, s1 + tail_pad_sec]` from a sub-30fps source (e.g. 24fps Flow clip) to `target_fps` (e.g. 30fps)
    using half-res bidirectional OpenCV `DISOpticalFlow` (`ULTRAFAST`) so every output frame has genuine sub-frame
    motion without `fps=30` duplicated-frame judder or blurry alpha frame-blending.
    Returns `(temp_mp4_path, actual_t0)` when upsampled, or `None` if source is already `>= target_fps - 0.5` or small.
    """
    if not src_path.exists() or src_path.stat().st_size < 4096:
        return None
    cap = cv2.VideoCapture(str(src_path))
    if not cap.isOpened():
        return None
    try:
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 0.0)
        w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH) or 0)
        h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT) or 0)
        if src_fps <= 0.5 or src_fps >= float(target_fps) - 0.5 or w < 320 or h < 320:
            return None
        start_f = max(0, int(math.floor(max(0.0, float(s0) - 0.02) * src_fps)))
        end_f = max(start_f + 2, int(math.ceil((float(s1) + float(tail_pad_sec)) * src_fps)) + 1)
        frames: list[np.ndarray] = []
        f_idx = 0
        while f_idx <= end_f:
            if f_idx < start_f:
                if not cap.grab():
                    break
            else:
                ok, frm = cap.read()
                if not ok or frm is None:
                    break
                frames.append(frm)
            f_idx += 1
    finally:
        cap.release()
    if len(frames) < 2:
        return None

    actual_t0 = float(start_f) / src_fps
    t_rel_end = float(len(frames) - 1) / src_fps
    n_out = max(2, int(math.ceil(t_rel_end * float(target_fps))) + 1)
    sw = max(64, ((w // 2) // 2) * 2)
    sh = max(64, ((h // 2) // 2) * 2)
    sx_scale = float(w) / float(sw)
    sy_scale = float(h) / float(sh)
    dis = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_ULTRAFAST)
    grays = [cv2.cvtColor(cv2.resize(f, (sw, sh), interpolation=cv2.INTER_AREA), cv2.COLOR_BGR2GRAY) for f in frames]
    grid_x, grid_y = np.meshgrid(np.arange(w, dtype=np.float32), np.arange(h, dtype=np.float32))

    tmp_f = tempfile.NamedTemporaryFile(
        suffix=".mp4",
        prefix="aab_oflow_",
        dir=str(get_ram_scratch_root()),
        delete=False,
    )
    tmp_path = Path(tmp_f.name)
    tmp_f.close()

    cmd_pipe = [
        ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
        "-f", "rawvideo", "-pix_fmt", "bgr24", "-s", f"{w}x{h}", "-r", str(int(target_fps)),
        "-i", "pipe:0",
        "-c:v", "libx264", "-preset", "ultrafast", "-crf", "10", "-threads", "1",
        "-pix_fmt", "yuv420p", "-an",
        str(tmp_path),
    ]
    proc: subprocess.Popen[bytes] | None = None
    try:
        proc = subprocess.Popen(cmd_pipe, stdin=subprocess.PIPE, stdout=subprocess.DEVNULL, stderr=subprocess.PIPE)
        assert proc.stdin is not None
        cached_pair = -1
        cached_fwd: np.ndarray | None = None
        cached_bwd: np.ndarray | None = None
        cached_cut = False
        for k in range(n_out):
            pos = min(float(len(frames) - 1), (float(k) / float(target_fps)) * src_fps)
            i0 = min(len(frames) - 2, max(0, int(math.floor(pos))))
            i1 = i0 + 1
            alpha = max(0.0, min(1.0, pos - float(i0)))
            if alpha <= 0.005:
                out_frm = frames[i0]
            elif alpha >= 0.995:
                out_frm = frames[i1]
            else:
                if i0 != cached_pair:
                    g0, g1 = grays[i0], grays[i1]
                    mad = float(np.mean(np.abs(g1.astype(np.float32) - g0.astype(np.float32))))
                    cached_pair = i0
                    if mad > 68.0:
                        cached_cut = True
                        cached_fwd = None
                        cached_bwd = None
                    else:
                        cached_cut = False
                        f_low = dis.calc(g0, g1, None)
                        b_low = dis.calc(g1, g0, None)
                        ff_full = cv2.resize(f_low, (w, h), interpolation=cv2.INTER_LINEAR)
                        fb_full = cv2.resize(b_low, (w, h), interpolation=cv2.INTER_LINEAR)
                        ff_full[:, :, 0] *= sx_scale
                        ff_full[:, :, 1] *= sy_scale
                        fb_full[:, :, 0] *= sx_scale
                        fb_full[:, :, 1] *= sy_scale
                        cached_fwd = ff_full
                        cached_bwd = fb_full
                if cached_cut or cached_fwd is None or cached_bwd is None:
                    out_frm = frames[i0 if alpha < 0.5 else i1]
                else:
                    # Warp frames cleanly along bidirectional displacement fields without ghost crossfade.
                    m0x = grid_x - alpha * cached_fwd[:, :, 0]
                    m0y = grid_y - alpha * cached_fwd[:, :, 1]
                    m1x = grid_x - (1.0 - alpha) * cached_bwd[:, :, 0]
                    m1y = grid_y - (1.0 - alpha) * cached_bwd[:, :, 1]
                    w0 = cv2.remap(frames[i0], m0x, m0y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    w1 = cv2.remap(frames[i1], m1x, m1y, interpolation=cv2.INTER_LINEAR, borderMode=cv2.BORDER_REPLICATE)
                    out_frm = cv2.addWeighted(w0, 1.0 - alpha, w1, alpha, 0.0)
            proc.stdin.write(np.ascontiguousarray(out_frm).tobytes())
        proc.stdin.close()
        proc.wait(timeout=120)
        if proc.returncode != 0 or not tmp_path.exists() or tmp_path.stat().st_size < 1024:
            tmp_path.unlink(missing_ok=True)
            return None
        return tmp_path, round(actual_t0, 6)
    except Exception:
        if proc is not None:
            try:
                if proc.stdin:
                    proc.stdin.close()
                proc.kill()
            except Exception:
                pass
        tmp_path.unlink(missing_ok=True)
        return None


def _render_cut_segment(
    ff: str,
    cut: dict[str, Any],
    clips_by_num: dict[int, Path],
    out_seg: Path,
    fps: int,
    pastel_eq_by_num: dict[int, str] | None = None,
    ass_burn_chain: str = "",
    crf: int = 18,
    preset: str = "veryfast",
    cwd: Path | None = None,
    single_frame_offset_sec: float | None = None,
    override_frames: int | None = None,
    ffmpeg_threads: int = 1,
) -> None:
    """Renders one frame-exact stitchable H.264 cut segment (`1080x1920 @ fps`, optional single-pass ASS burn-in or 1-frame PNG)."""
    c_frames = int(override_frames if override_frames is not None else cut["frames"])
    out_dur = c_frames / float(fps)
    c1_num = int(cut["clip_index"])
    p1 = clips_by_num[c1_num]
    eq1 = (pastel_eq_by_num or {}).get(c1_num, "")
    s0, s1 = _clamp_source_window_to_eof(p1, float(cut["src_start_sec"]), float(cut["src_end_sec"]))
    src_dur = max(0.20, s1 - s0)
    pts_ratio = out_dur / src_dur
    if bool(cut.get("forbid_slowmo_stretch")):
        pts_ratio = min(1.0, pts_ratio)
    zoom = float(cut.get("crop_zoom") or 1.0)
    scaled_w = int(round(VIDEO_WIDTH * zoom))
    scaled_h = int(round(VIDEO_HEIGHT * zoom))
    scaled_w += scaled_w % 2
    scaled_h += scaled_h % 2

    # Never use FFmpeg double-image alpha frame-blending (causes blurry ghosting); use bidirectional DISOpticalFlow instead.
    pre_interp_1 = ""
    s1_pad = s1 + (0.05 if pts_ratio > 1.22 else 0.04)
    stop_pad = max(1.50, out_dur + 1.00)
    tmp_oflow_paths: list[Path] = []
    allow_oflow = single_frame_offset_sec is None and not bool(cut.get("disable_optical_flow"))
    try:
        if allow_oflow and (pts_ratio >= 0.76 or int(fps) >= 29):
            # At ~1.25x speed on a 24fps source (24 / 0.80 = 30.0fps), native frames already supply >= target_fps
            # without synthetic optical-flow interpolation blur or dropped-frame cadence judder.
            cap_chk = cv2.VideoCapture(str(p1))
            src_fps_chk = float(cap_chk.get(cv2.CAP_PROP_FPS) or 0.0) if cap_chk.isOpened() else 0.0
            cap_chk.release()
            eff_src_rate = src_fps_chk / max(0.25, float(pts_ratio)) if src_fps_chk > 0.5 else 0.0
            up1 = (
                None
                if (pts_ratio < 0.96 and abs(eff_src_rate - float(fps)) <= 0.65)
                else _upsample_clip_window_optical_flow(ff, p1, s0, s1, int(fps), tail_pad_sec=0.22)
            )
            if up1 is not None:
                p1_up, t0_1 = up1
                tmp_oflow_paths.append(p1_up)
                p1 = p1_up
                s0 = max(0.0, s0 - t0_1)
                s1 = max(s0 + 0.20, s1 - t0_1)
                s1_pad = max(s1 + 0.04, s1_pad - t0_1)
        tail_trim = f",trim=end_frame={c_frames},setpts=PTS-STARTPTS"
        if single_frame_offset_sec is not None:
            off_t = max(0.0, min(max(0.0, out_dur - (1.0 / float(fps))), float(single_frame_offset_sec)))
            tail_trim = f",trim=start={off_t:.4f},setpts=PTS-STARTPTS"
        eff_ass = "" if single_frame_offset_sec is not None else ass_burn_chain

        v_enc_args = (
            ["-frames:v", "1", str(out_seg)]
            if single_frame_offset_sec is not None
            else [
                "-frames:v", str(c_frames), "-r", str(fps),
                "-c:v", "libx264", "-preset", preset, "-crf", str(crf),
                "-profile:v", "high", "-level:v", "4.2",
                "-x264-params", "stitchable=1",
                "-video_track_timescale", str(fps * 1000),
                "-threads", str(max(1, int(ffmpeg_threads))),
                "-pix_fmt", "yuv420p", "-an",
                str(out_seg),
            ]
        )

        if cut.get("mode") == "split_hstack" and cut.get("secondary_clip_index"):
            c2_num = int(cut["secondary_clip_index"])
            p2 = clips_by_num[c2_num]
            eq2 = (pastel_eq_by_num or {}).get(c2_num, "")
            raw_sec0, raw_sec1 = cut["secondary_src_span"]
            sec0, sec1 = _clamp_source_window_to_eof(p2, float(raw_sec0), float(raw_sec1))
            sec_dur = max(0.20, float(sec1) - float(sec0))
            pts2 = out_dur / sec_dur
            pre_interp_2 = ""
            sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
            if allow_oflow and pts2 >= 0.85:
                up2 = _upsample_clip_window_optical_flow(ff, p2, sec0, sec1, int(fps), tail_pad_sec=0.22)
                if up2 is not None:
                    p2_up, t0_2 = up2
                    tmp_oflow_paths.append(p2_up)
                    p2 = p2_up
                    sec0 = max(0.0, sec0 - t0_2)
                    sec1 = max(sec0 + 0.20, sec1 - t0_2)
                    sec1_pad = max(sec1 + 0.04, sec1_pad - t0_2)
            div_w = int(DIORAMA_V7_SPLIT_DIVIDER_PX)
            left_w = (VIDEO_WIDTH - div_w) // 2
            right_w = VIDEO_WIDTH - left_w - div_w
            pts_expr_1 = "setpts=PTS-STARTPTS" if abs(pts_ratio - 1.0) <= 0.035 else f"{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS)"
            pts_expr_2 = "setpts=PTS-STARTPTS" if abs(pts2 - 1.0) <= 0.035 else f"{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS)"
            fc = (
                f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pts_expr_1},"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq1}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={left_w}:{VIDEO_HEIGHT}:(in_w-{left_w})/2:0[left];"
                f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pts_expr_2},"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq2}unsharp=5:5:0.35:5:5:0.0,format=gbrp,crop={right_w}:{VIDEO_HEIGHT}:(in_w-{right_w})/2:0[right];"
                f"color=c=black:s={div_w}x{VIDEO_HEIGHT}:r={fps}:d={out_dur + stop_pad:.4f},format=gbrp[div];"
                f"[left][div][right]hstack=inputs=3,setsar=1,format=yuv420p{eff_ass}{tail_trim}[vout]"
            )
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-i", str(p2),
                "-filter_complex", fc, "-map", "[vout]",
                *v_enc_args,
            ]
        elif cut.get("mode") == "split_vstack" and cut.get("secondary_clip_index"):
            p2 = clips_by_num[int(cut["secondary_clip_index"])]
            raw_sec0, raw_sec1 = cut["secondary_src_span"]
            sec0, sec1 = _clamp_source_window_to_eof(p2, float(raw_sec0), float(raw_sec1))
            sec_dur = max(0.20, float(sec1) - float(sec0))
            pts2 = out_dur / sec_dur
            pre_interp_2 = ""
            sec1_pad = float(sec1) + (0.05 if pts2 > 1.22 else 0.04)
            if allow_oflow and pts2 >= 0.85:
                up2 = _upsample_clip_window_optical_flow(ff, p2, sec0, sec1, int(fps), tail_pad_sec=0.22)
                if up2 is not None:
                    p2_up, t0_2 = up2
                    tmp_oflow_paths.append(p2_up)
                    p2 = p2_up
                    sec0 = max(0.0, sec0 - t0_2)
                    sec1 = max(sec0 + 0.20, sec1 - t0_2)
                    sec1_pad = max(sec1 + 0.04, sec1_pad - t0_2)
            half_h = (VIDEO_HEIGHT - 6) // 2
            half_h -= half_h % 2
            rem_h = VIDEO_HEIGHT - half_h - 6
            fc = (
                f"[0:v]trim=start={s0:.4f}:end={s1_pad:.4f},{pre_interp_1}setpts=({pts_ratio:.5f})*(PTS-STARTPTS),"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{half_h}[top];"
                f"[1:v]trim=start={sec0:.4f}:end={sec1_pad:.4f},{pre_interp_2}setpts=({pts2:.5f})*(PTS-STARTPTS),"
                f"fps={fps},tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={VIDEO_WIDTH}:{VIDEO_HEIGHT}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"unsharp=5:5:0.35:5:5:0.0,crop={VIDEO_WIDTH}:{rem_h}[bot];"
                f"color=c=white:s={VIDEO_WIDTH}x6:r={fps}:d={out_dur + stop_pad:.4f}[div];"
                f"[top][div][bot]vstack=inputs=3,setsar=1,format=yuv420p{eff_ass}{tail_trim}[vout]"
            )
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-i", str(p2),
                "-filter_complex", fc, "-map", "[vout]",
                *v_enc_args,
            ]
        else:
            use_v8_curve = bool(cut.get("v8_curve_ramp") and single_frame_offset_sec is None and not cut.get("outro_sky_card"))
            use_ramp = bool(cut.get("speed_ramp") and not cut.get("outro_sky_card"))
            if use_v8_curve:
                nom_f = max(c_frames, int(cut.get("curve_nominal_frames") or c_frames))
                nom_dur = max(0.25, nom_f / float(fps))
                s1_curve_pad = s1 + 0.12
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_curve_pad:.4f},"
                    "setpts=PTS-STARTPTS,"
                    f"setpts='(({nom_dur:.5f})*(min(T/{src_dur:.5f},1.0)-0.054113*sin(6.283185*min(T/{src_dur:.5f},1.0))+max(0.0,T/{src_dur:.5f}-1.0)*0.66))/TB',"
                )
            elif use_ramp:
                start_spd = max(1.05, float(DIORAMA_ENTRY_RAMP_START_SPEED))
                main_spd = max(0.85, float(cut.get("main_speed") or DIORAMA_ENTRY_RAMP_MAIN_SPEED))
                src_head = round(0.35 * start_spd, 5)
                s1_ramp_pad = s1 + 0.08
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_ramp_pad:.4f},"
                    "setpts=PTS-STARTPTS,"
                    f"setpts='(if(lt(T,{src_head:.5f}),T/{start_spd:.5f},0.35+(T-{src_head:.5f})/{main_spd:.5f}))/TB',"
                )
            elif abs(pts_ratio - 1.0) <= 0.035:
                pts_chain = f"trim=start={s0:.4f}:end={s1 + 0.08:.4f},setpts=PTS-STARTPTS,"
            else:
                pts_chain = (
                    f"trim=start={s0:.4f}:end={s1_pad:.4f},"
                    f"{pre_interp_1}"
                    f"setpts=({pts_ratio:.5f})*(PTS-STARTPTS),"
                )
            portal_zoom_parts: list[str] = []
            pz_head = int(cut.get("_portal_zoom_head_frames") or 0)
            pz_tail_start = cut.get("_portal_zoom_tail_start_f")
            if single_frame_offset_sec is None and (pz_head > 0 or pz_tail_start is not None):
                z_expr = "1.0"
                if pz_head > 0 and pz_tail_start is not None:
                    ts_i = max(1, int(pz_tail_start))
                    span_t = max(2, c_frames - ts_i)
                    z_expr = f"if(lte(n,{pz_head}),1.16-0.16*n/{float(pz_head):.1f},if(gte(n,{ts_i}),1.0+0.20*(n-{ts_i})/{float(span_t):.1f},1.0))"
                elif pz_head > 0:
                    z_expr = f"if(lte(n,{pz_head}),1.16-0.16*n/{float(pz_head):.1f},1.0)"
                elif pz_tail_start is not None:
                    ts_i = max(1, int(pz_tail_start))
                    span_t = max(2, c_frames - ts_i)
                    z_expr = f"if(gte(n,{ts_i}),1.0+0.20*(n-{ts_i})/{float(span_t):.1f},1.0)"
                portal_zoom_parts.append(
                    f"scale=w='trunc(iw*({z_expr})/2)*2':h='trunc(ih*({z_expr})/2)*2':eval=frame:flags=bicubic,"
                    f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT}:'(in_w-{VIDEO_WIDTH})/2':'(in_h-{VIDEO_HEIGHT})/2',"
                )
            elif (
                single_frame_offset_sec is None
                and not cut.get("outro_sky_card")
                and c_frames >= 20
                and any(k in str(cut.get("camera_move") or "").lower() for k in ("push", "pull", "dolly", "orbit"))
            ):
                # Locked-camera Flow Start->End color-morph clips (e.g. K06 twin stacked brains over #040711 void)
                # can have near-zero frame-to-frame camera motion (median center-ROI diff < 0.30).
                # Apply a silky sub-pixel 5.5% Ken Burns micro-push/pull so 30fps temporal motion stays fluid (0 frozen pairs).
                try:
                    cap_m = cv2.VideoCapture(str(p1))
                    if cap_m.isOpened():
                        fps_m = max(1.0, float(cap_m.get(cv2.CAP_PROP_FPS) or 24.0))
                        f_a = max(0, int(round(s0 * fps_m)))
                        f_b = max(f_a + 4, int(round(s1 * fps_m)))
                        sample_idxs = sorted({min(f_b - 1, f_a + int((f_b - f_a) * r)) for r in (0.15, 0.35, 0.55, 0.75)})
                        m_diffs: list[float] = []
                        for si in sample_idxs:
                            cap_m.set(cv2.CAP_PROP_POS_FRAMES, si)
                            ok_1, fr_1 = cap_m.read()
                            ok_2, fr_2 = cap_m.read()
                            if ok_1 and ok_2 and fr_1 is not None and fr_2 is not None:
                                g1 = cv2.cvtColor(fr_1, cv2.COLOR_BGR2GRAY)
                                g2 = cv2.cvtColor(fr_2, cv2.COLOR_BGR2GRAY)
                                hh, ww = g1.shape[:2]
                                r1 = g1[int(hh * 0.30):int(hh * 0.68), int(ww * 0.12):int(ww * 0.88)]
                                r2 = g2[int(hh * 0.30):int(hh * 0.68), int(ww * 0.12):int(ww * 0.88)]
                                m_diffs.append(float(np.mean(cv2.absdiff(r1, r2))))
                        cap_m.release()
                        if m_diffs and float(np.median(m_diffs)) < 0.30:
                            is_pull_cam = "pull" in str(cut.get("camera_move") or "").lower()
                            zp_expr = (
                                f"1.055-0.055*min(1,in/{max(1, c_frames):.1f})"
                                if is_pull_cam
                                else f"1+0.055*min(1,in/{max(1, c_frames):.1f})"
                            )
                            portal_zoom_parts.append(
                                f"zoompan=z='{zp_expr}':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:s={VIDEO_WIDTH}x{VIDEO_HEIGHT}:fps={fps},"
                            )
                except Exception:
                    pass
            portal_zoom_str = "".join(portal_zoom_parts)
            vf = (
                f"{pts_chain}"
                f"fps={fps},"
                f"tpad=stop_mode=clone:stop_duration={stop_pad:.4f},"
                f"scale={scaled_w}:{scaled_h}:force_original_aspect_ratio=increase:flags=lanczos,"
                f"{eq1}unsharp=5:5:0.75:3:3:0.35,"
                f"crop={VIDEO_WIDTH}:{VIDEO_HEIGHT},"
                f"{portal_zoom_str}"
                f"setsar=1,format=yuv420p"
            )
            if cut.get("outro_sky_card"):
                fade_s = max(0.0, out_dur - 0.14)
                vf += f",fade=t=out:st={fade_s:.3f}:d=0.12"
            if eff_ass:
                vf += eff_ass
            if tail_trim:
                vf += tail_trim
            cmd = [
                ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                "-i", str(p1), "-vf", vf,
                *v_enc_args,
            ]
        res = subprocess.run(
            cmd,
            cwd=(str(cwd) if cwd is not None else None),
            capture_output=True,
            text=True,
            check=False,
            timeout=180,
            stdin=subprocess.DEVNULL,
        )
        if res.returncode != 0 or not out_seg.exists():
            raise RuntimeError(f"Failed rendering EDL cut {cut['cut_index']}: {res.stderr[:280]}")
        if single_frame_offset_sec is None:
            rendered_f = _probe_segment_frame_count(out_seg)
            if rendered_f < c_frames:
                raise RuntimeError(
                    f"Rendered EDL cut {cut['cut_index']} truncated: got {rendered_f} frames < expected {c_frames} frames ({out_seg.name})"
                )
    finally:
        for tp in tmp_oflow_paths:
            tp.unlink(missing_ok=True)


def _atomic_copy_file(src: Path, dst: Path, suffix: str | None = None) -> None:
    """Copies `src` to a temporary sibling file and atomically replaces `dst` via `atomic_commit_from_scratch` (`EXDEV`-safe, preserves `src`)."""
    atomic_commit_from_scratch(src, dst, suffix=suffix, keep_src=True)


def refine_plaque_safe_source_windows(
    edl: dict[str, Any],
    clip_files: list[Path],
    run_fail_threshold: int = 5,
    max_candidates: int = 48,
    cache_dir: Path | None = None,
) -> list[dict[str, Any]]:
    """
    F-1 pre-render plaque guard: probes every single-mode cut's source window at the exact frames DQ9
    (`start+0.08`, mid, `end-0.08` on 1080x1920 non-subtitle ROIs) and R64 (12/31/50/69/88% on the 360x640 grid)
    will later inspect. When any probe hits a horizontal glyph run >= `run_fail_threshold`, the window slides
    (closest-first, 0.125s steps) to the nearest start whose probes all stay below the threshold. Mutates `edl`.
    """
    from pipeline.episode_qa import _non_subtitle_scene_rois
    from pipeline.flow_worker import _max_horizontal_plaque_glyph_run
    from pipeline.media_cache import fast_file_sha256, stage_local_file

    clips_by_num = {i: Path(cf) for i, cf in enumerate(clip_files, start=1)}
    plaque_cache_p = (Path(cache_dir) / "plaque_cache.json") if cache_dir else None
    plaque_cache: dict[str, Any] = {}
    if plaque_cache_p and plaque_cache_p.is_file():
        try:
            plaque_cache = json.loads(plaque_cache_p.read_text(encoding="utf-8"))
        except Exception:  # noqa: BLE001
            plaque_cache = {}
    plaque_cache_dirty = False
    clip_sha_by_num: dict[int, str] = {}
    caps: dict[int, Any] = {}
    fps_by: dict[int, float] = {}
    nframes_by: dict[int, int] = {}
    memo: dict[tuple[int, int], int] = {}

    def _cap(num: int) -> Any:
        if num not in caps:
            local_p, _ = stage_local_file(clips_by_num[num])
            cap = cv2.VideoCapture(str(local_p))
            caps[num] = cap
            fps_by[num] = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
            nframes_by[num] = int(cap.get(cv2.CAP_PROP_FRAME_COUNT) or 0)
        return caps[num]

    is_v8_ref = is_expressive_v8_plan(edl)

    def _run_at(num: int, t_sec: float) -> int:
        cap = _cap(num)
        f_idx = max(0, min(max(0, nframes_by[num] - 1), int(round(t_sec * fps_by[num]))))
        key = (num, f_idx)
        if key in memo:
            return memo[key]
        cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
        ok, frm = cap.read()
        if not ok or frm is None:
            memo[key] = 0
            return 0
        f1080 = cv2.resize(frm, (VIDEO_WIDTH, VIDEO_HEIGHT), interpolation=cv2.INTER_LINEAR)
        r_hi = max(
            (
                _max_horizontal_plaque_glyph_run(r)
                for r in _non_subtitle_scene_rois(
                    f1080,
                    has_top_overlay=False,
                    is_outro=False,
                    is_expressive_v8=is_v8_ref,
                )
            ),
            default=0,
        )
        small = cv2.resize(frm, (360, 640), interpolation=cv2.INTER_AREA)
        roi = cv2.cvtColor(small[int(640 * 0.06) : int(640 * 0.92), int(360 * 0.06) : int(360 * 0.94)], cv2.COLOR_BGR2GRAY)
        r_lo = _max_horizontal_plaque_glyph_run(roi)
        memo[key] = int(max(r_hi, r_lo))
        return memo[key]

    refinements: list[dict[str, Any]] = []
    try:
        for cut in edl.get("cuts") or []:
            if cut.get("mode") != "single" or cut.get("outro_sky_card"):
                continue
            if is_v8_ref and cut.get("diegetic_text_allowlist"):
                continue
            num = int(cut["clip_index"])
            if num not in clips_by_num or not clips_by_num[num].exists():
                continue
            s0 = float(cut["src_start_sec"])
            span = max(0.05, float(cut["src_end_sec"]) - s0)
            out_d = max(0.05, float(cut["duration_sec"]))
            c_sha = ""
            if plaque_cache_p is not None:
                if num not in clip_sha_by_num:
                    clip_sha_by_num[num] = fast_file_sha256(clips_by_num[num])
                c_sha = clip_sha_by_num[num]
                p_key = f"{c_sha}|{s0:.4f}|{span:.4f}|{out_d:.4f}|{int(is_v8_ref)}|{run_fail_threshold}"
                if p_key in plaque_cache:
                    hit_entry = plaque_cache[p_key]
                    if hit_entry.get("to_src_start") is not None:
                        cand_hit = float(hit_entry["to_src_start"])
                        cut["src_start_sec"] = round(cand_hit, 4)
                        cut["src_end_sec"] = round(cand_hit + span, 4)
                    if hit_entry.get("refinement"):
                        ref_cp = dict(hit_entry["refinement"])
                        ref_cp["cut_index"] = cut["cut_index"]
                        refinements.append(ref_cp)
                    continue
            else:
                p_key = ""
            ratio = span / out_d
            offs = sorted(
                {
                    round(min(out_d, max(0.0, o)), 4)
                    for o in (0.08, max(0.08, out_d - 0.08), 0.5 * out_d, 0.12 * out_d, 0.31 * out_d, 0.69 * out_d, 0.88 * out_d)
                }
            )

            def _probe(start: float, _num: int = num, _offs: tuple[float, ...] = tuple(offs), _ratio: float = ratio) -> int:
                return max(_run_at(_num, start + o * _ratio) for o in _offs)

            worst = _probe(s0)
            if worst < run_fail_threshold:
                if p_key:
                    plaque_cache[p_key] = {"to_src_start": None, "refinement": None}
                    plaque_cache_dirty = True
                continue
            clip_dur = max(span + 0.2, float(_clip_duration(clips_by_num[num])))
            max_start = max(0.08, clip_dur - 0.08 - span)
            grid = [round(0.08 + 0.125 * k, 4) for k in range(int((max_start - 0.08) / 0.125) + 1)]
            grid = sorted(grid, key=lambda c: abs(c - s0))[:max_candidates]
            fixed = False
            for cand in grid:
                if abs(cand - s0) < 1e-6:
                    continue
                if _probe(cand) < run_fail_threshold:
                    cut["src_start_sec"] = round(cand, 4)
                    cut["src_end_sec"] = round(cand + span, 4)
                    ref_item = {"cut_index": cut["cut_index"], "clip_index": num, "from_src_start": round(s0, 4), "to_src_start": round(cand, 4), "worst_run_before": worst}
                    refinements.append(ref_item)
                    if p_key:
                        plaque_cache[p_key] = {"to_src_start": round(cand, 4), "refinement": ref_item}
                        plaque_cache_dirty = True
                    fixed = True
                    break
            if not fixed:
                ref_unres = {"cut_index": cut["cut_index"], "clip_index": num, "status": "unresolved", "worst_run": worst}
                refinements.append(ref_unres)
                if p_key:
                    plaque_cache[p_key] = {"to_src_start": None, "refinement": ref_unres}
                    plaque_cache_dirty = True
    finally:
        for cap in caps.values():
            cap.release()
        if plaque_cache_p is not None and plaque_cache_dirty:
            try:
                plaque_cache_p.write_text(json.dumps(plaque_cache, indent=2), encoding="utf-8")
            except OSError:
                pass
    return refinements


def _segment_cache_dir(p_dir: Path) -> Path:
    from pipeline.media_cache import get_speed_cache_dir

    h = hashlib.sha1(str(Path(p_dir).resolve()).encode("utf-8")).hexdigest()[:16]
    d = get_speed_cache_dir() / "segments" / h
    d.mkdir(parents=True, exist_ok=True)
    return d


def _store_segment_cache(p_dir: Path, seg_jobs: list[tuple[dict[str, Any], Path, int, float]], edl: dict[str, Any], ass_path: Path) -> None:
    """F-3: persists rendered stitchable segments (local SSD cache) so `recut_diorama_cuts` can re-render single cuts."""
    try:
        cdir = _segment_cache_dir(p_dir)
        index: dict[str, Any] = {"ass_sha1": hashlib.sha1(Path(ass_path).read_bytes()).hexdigest(), "fps": int(edl["fps"]), "segments": []}
        for cut, s_path, eff_f, start_s in seg_jobs:
            dst = cdir / s_path.name
            shutil.copy2(s_path, dst)
            index["segments"].append({"cut_index": int(cut["cut_index"]), "file": dst.name, "frames": int(eff_f), "start_sec": round(start_s, 6)})
        (cdir / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    except Exception:  # noqa: BLE001
        pass


def _raw_cut_cache_path(
    p_dir: Path,
    cut: dict[str, Any],
    local_clips: dict[int, Path],
    fps: int,
    f_cnt: int,
    pastel_eq_by_num: dict[int, str],
    ass_burn_chain: str = "",
    ass_sha1: str = "",
) -> Path | None:
    """Deterministic local-SSD segment cache path (`/tmp/aab_speed_cache/segments/<proj>/raw_v8/<sha1>.mp4`)."""
    from pipeline.media_cache import fast_file_sha256

    c1_num = int(cut.get("clip_index") or 0)
    p1 = local_clips.get(c1_num)
    if p1 is None or not p1.exists():
        return None
    sha1_clip = fast_file_sha256(p1)
    c2_num = int(cut.get("secondary_clip_index") or 0)
    sha2_clip = ""
    if c2_num > 0:
        p2 = local_clips.get(c2_num)
        if p2 is None or not p2.exists():
            return None
        sha2_clip = fast_file_sha256(p2)
    render_spec = {
        "mode": cut.get("mode", "single"),
        "s0": round(float(cut.get("src_start_sec") or 0.0), 4),
        "s1": round(float(cut.get("src_end_sec") or 0.0), 4),
        "sec_span": cut.get("secondary_src_span"),
        "zoom": round(float(cut.get("crop_zoom") or 1.0), 4),
        "v8_curve": bool(cut.get("v8_curve_ramp")),
        "curve_nom_f": int(cut.get("curve_nominal_frames") or f_cnt) if cut.get("v8_curve_ramp") else 0,
        "speed_ramp": bool(cut.get("speed_ramp")),
        "main_speed": round(float(cut.get("main_speed") or 0.0), 4) if cut.get("speed_ramp") else 0.0,
        "outro": bool(cut.get("outro_sky_card")),
        "pz_head": int(cut.get("_portal_zoom_head_frames") or 0),
        "pz_tail": cut.get("_portal_zoom_tail_start_f"),
        "fps": int(fps),
        "frames": int(f_cnt),
        "eq1": (pastel_eq_by_num or {}).get(c1_num, ""),
        "eq2": (pastel_eq_by_num or {}).get(c2_num, "") if c2_num > 0 else "",
        "burn": ass_burn_chain if ass_burn_chain else "",
        "ass_sha1": ass_sha1 if ass_burn_chain else "",
    }
    raw_key = hashlib.sha1(
        f"raw_v8_v2_noblend|{sha1_clip}|{sha2_clip}|{json.dumps(render_spec, sort_keys=True)}".encode("utf-8")
    ).hexdigest()[:24]
    raw_dir = _segment_cache_dir(p_dir) / "raw_v8"
    raw_dir.mkdir(parents=True, exist_ok=True)
    return raw_dir / f"{raw_key}.mp4"


def recut_diorama_cuts(
    project_id_or_dir: str | Path,
    cut_indices: list[int],
    allow_published_overwrite: bool = False,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    F-3 official partial re-render: re-renders only `cut_indices` from the current EDL (font-safe libass burn-in at the
    exact output offset), reuses every other cached segment, re-concats with `-c:v copy`, and re-muxes audio_master.wav.
    """
    from pipeline.media_cache import stage_local_file

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    if (p_dir / "06_publish" / "upload_receipt.json").exists() and not allow_published_overwrite:
        raise RuntimeError(f"Refusing to recut published project {p_dir.name} (pass allow_published_overwrite=True)")
    verify_script_audio_freshness(p_dir, context="recut_diorama_cuts")
    asm_dir = p_dir / "05_assembly"
    edl = json.loads((asm_dir / "edit_decision_list.json").read_text(encoding="utf-8"))
    if any(
        str(c.get("transition_out") or "").strip().lower()
        in (
            "dissolve_6f",
            "dissolve_8f",
            "dissolve_12f",
            "dissolve_15f",
            "portal_crash_zoom_10f",
            "whip_pan_blur_8f",
            "occlusion_wipe",
            "split_screen_wipe",
            "match_cut_bridge",
            "daisy_chain_bridge",
        )
        for c in (edl.get("cuts") or [])
    ):
        keep_audio = (p_dir / "04_audio" / "audio_master.wav").exists() and (p_dir / "04_audio" / "voice_report.json").exists()
        res = assemble_diorama_project(
            p_dir,
            force_rebuild=True,
            preserve_audio_master=keep_audio,
            allow_published_overwrite=allow_published_overwrite,
            cpu_budget=cpu_budget,
        )
        res["recut_cuts"] = sorted({int(c) for c in cut_indices})
        return res
    ass_path = p_dir / "04_audio" / "subtitles.ass"
    wav_path = p_dir / "04_audio" / "audio_master.wav"
    cdir = _segment_cache_dir(p_dir)
    idx_p = cdir / "index.json"
    if not idx_p.exists():
        raise RuntimeError("No segment cache for this project; run a full diorama-assemble first.")
    index = json.loads(idx_p.read_text(encoding="utf-8"))
    if index.get("ass_sha1") != hashlib.sha1(ass_path.read_bytes()).hexdigest():
        raise RuntimeError("subtitles.ass changed since the cached render; run a full diorama-assemble instead.")
    segs = index["segments"]
    missing = [s["file"] for s in segs if not (cdir / s["file"]).exists()]
    if missing:
        raise RuntimeError(f"Segment cache incomplete ({len(missing)} missing); run a full diorama-assemble.")
    want = {int(c) for c in cut_indices}
    cuts_by_idx = {int(c["cut_index"]): c for c in edl["cuts"]}
    clip_files = _resolve_diorama_clip_files(p_dir / "03_visuals")
    ff = _ffmpeg()
    fps = int(index["fps"])
    with ram_tempdir(prefix="aab_recut_") as td:
        td_path = Path(td)
        need_nums = set()
        for ci in want:
            c = cuts_by_idx[ci]
            need_nums.add(int(c["clip_index"]))
            if c.get("secondary_clip_index"):
                need_nums.add(int(c["secondary_clip_index"]))
        local_clips = {n: stage_local_file(clip_files[n - 1])[0] for n in need_nums}
        pastel = (
            {}
            if (is_porcelain_v7_plan(edl) or is_expressive_v8_plan(edl))
            else {n: _compute_v7_pastel_eq_filter(local_clips[n]) for n in need_nums}
        )
        shutil.copy2(ass_path, td_path / "subtitles.ass")
        fonts_dir = td_path / "fonts"
        fonts_dir.mkdir()
        bundled = ensure_bundled_condensed_font()
        shutil.copy2(bundled, fonts_dir / bundled.name)
        font_rep = probe_ass_font_resolution(ff, td_path, "subtitles.ass", fontsdir="fonts")
        if not font_rep["passed"]:
            raise RuntimeError(f"F-2 font guard failed during recut: {font_rep['fallbacks'][:2]}")
        ass_filter = "ass=subtitles.ass:fontsdir=fonts"
        recut_targets = [s for s in segs if s["cut_index"] in want]
        recut_workers = min(resolve_assembler_workers(cpu_budget), max(1, len(want)))
        recut_ff_threads = resolve_ffmpeg_threads_per_worker(recut_workers, cpu_budget)

        def _recut_one_seg(s_entry: dict[str, Any]) -> None:
            out_seg = td_path / s_entry["file"]
            burn = f",setpts=PTS+{float(s_entry['start_sec']):.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
            _render_cut_segment(
                ff,
                cuts_by_idx[s_entry["cut_index"]],
                local_clips,
                out_seg,
                fps,
                pastel_eq_by_num=pastel,
                ass_burn_chain=burn,
                crf=18,
                preset="veryfast",
                cwd=td_path,
                override_frames=int(s_entry["frames"]),
                ffmpeg_threads=recut_ff_threads,
            )
            _atomic_copy_file(out_seg, cdir / s_entry["file"])

        if recut_targets:
            prev_cv_threads = cv2.getNumThreads()
            if recut_workers > 1 and prev_cv_threads > 1:
                cv2.setNumThreads(1)
            try:
                with ThreadPoolExecutor(max_workers=recut_workers) as recut_pool:
                    list(recut_pool.map(_recut_one_seg, recut_targets))
            finally:
                if recut_workers > 1 and prev_cv_threads > 1:
                    cv2.setNumThreads(prev_cv_threads)
        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{(cdir / s['file']).as_posix()}'" for s in segs) + "\n", encoding="utf-8")
        shutil.copy2(wav_path, td_path / "audio_master.wav")
        cum = sum(int(s["frames"]) for s in segs)
        recut_ceil_sec = EXPRESSIVE_V8_HARD_CEILING_SEC if is_expressive_v8_plan(edl) else SHORTS_HARD_CEILING_SEC
        exact_dur = min(recut_ceil_sec, cum / float(fps))
        local_final = td_path / "final_shorts_1080x1920.mp4"

        def _recut_mux(trim_db: float) -> subprocess.CompletedProcess:
            vol = f"volume={trim_db:.2f}dB," if trim_db < 0 else ""
            return subprocess.run(
                [
                    ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", "concat.txt", "-i", "audio_master.wav",
                    "-map", "0:v:0", "-map", "1:a:0", "-c:v", "copy",
                    "-af", f"atrim=0:{exact_dur:.6f},asetpts=PTS-STARTPTS,{vol}{DIORAMA_MUX_TRUE_PEAK_LIMITER}",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", str(DIORAMA_V7_AUDIO_CHANNELS),
                    "-movflags", "+faststart", local_final.name,
                ],
                cwd=str(td_path), capture_output=True, text=True, check=False, timeout=300, stdin=subprocess.DEVNULL,
            )

        res = _recut_mux(0.0)
        recut_trim_db = 0.0
        for _ in range(3):  # AAC true-peak guard (see assemble_diorama_project)
            if res.returncode != 0 or not local_final.exists():
                break
            tp_enc = _measure_true_peak_dbtp(local_final)
            if tp_enc is None or tp_enc <= DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP:
                break
            recut_trim_db -= (tp_enc - DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP) + 0.1
            res = _recut_mux(recut_trim_db)
        if res.returncode != 0 or not local_final.exists():
            raise RuntimeError(f"recut mux failed: {res.stderr[:300]}")
        final_mp4 = asm_dir / "final_shorts_1080x1920.mp4"
        _atomic_copy_file(local_final, final_mp4, suffix=".mp4.tmp")
    (asm_dir / "font_probe.json").write_text(json.dumps(font_rep, indent=2, ensure_ascii=False), encoding="utf-8")
    try:
        from pipeline import thumbnail as thumbnail_studio

        thumbnail_studio.run(p_dir, force=True, strict=False)
    except Exception:
        logger.warning("Non-fatal thumbnail refresh error during recut_diorama_cuts for %s", p_dir.name, exc_info=True)
    enforce_ram_scratch_budget()
    return {"project_dir": str(p_dir), "final_mp4": str(final_mp4), "recut_cuts": sorted(want), "frames": cum}


def assemble_diorama_project(
    project_id_or_dir: str | Path,
    force_rebuild: bool = True,
    align_whisper: bool = True,
    pre_synthesized_lines: list[np.ndarray] | None = None,
    tts_rate: str | None = None,
    run_posthoc_qa: bool = False,
    source_window_overrides: dict[int, Any] | None = None,
    apply_posthoc_window_shifts: bool = True,
    prosody_mode: str | None = None,
    voice_preset: str | None = None,
    preview_sec: float | None = None,
    allow_published_overwrite: bool = False,
    optimize_plaque_windows: bool = True,
    preserve_audio_master: bool = False,
    cpu_budget: int | None = None,
) -> dict[str, Any]:
    """
    End-to-end Schema v6 / Schema v7 `neuro_diorama` Gear 4 assembly:
      - Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`): `DIORAMA_VOICE_PRESETS` (`andrew_v7` / `emma_v7` / `ava_v7` / `aria_v7` / `christopher_v7`)
        breath-trimmed master clock (`dynamic_us_v7` / `dynamic_rush_v7`), `24.0fps` `1.00x` dynamic-rhythm 1:1 Zero-Reuse EDL,
        `split_hstack` `6px` black vertical divider, bundled `AABCondensed-Black.ttf` subtitles + `276pt` chapter headlines, and 2ch stereo score.
      - Schema v6 (`neuro_diorama`): `30fps` NLE EDL (`<= 5,370 frames`), `Y=64%` single-line ASS, `-24 dB` BGM.
    """
    from pipeline.config import (
        EXPRESSIVE_V8_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
        EXPRESSIVE_V8_DISSOLVE_FRAMES,
        EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
        EXPRESSIVE_V8_WHIP_PAN_FRAMES,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        is_expressive_v8_plan,
        resolve_shorts_format_profile,
        shorts_duration_range_for_profile,
    )

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    final_mp4 = p_dir / "05_assembly" / "final_shorts_1080x1920.mp4"
    if final_mp4.exists() and not force_rebuild and preview_sec is None:
        verify_script_audio_freshness(p_dir, context="assemble_diorama_project(force_rebuild=False)")
        return {"project_dir": str(p_dir), "final_mp4": str(final_mp4), "rebuilt": False}
    upload_receipt = p_dir / "06_publish" / "upload_receipt.json"
    if upload_receipt.exists() and not allow_published_overwrite:
        try:
            vid = json.loads(upload_receipt.read_text(encoding="utf-8")).get("video_id")
        except Exception:  # noqa: BLE001
            vid = "unknown"
        raise RuntimeError(
            f"Refusing to rebuild {p_dir.name}: it is already published (video_id={vid}). "
            "Rebuild a lab copy instead, or pass allow_published_overwrite=True / --allow-published-overwrite."
        )

    vp_path = next((p for p in (p_dir / "03_visuals" / "visual_plan.json", p_dir / "visual_plan.json") if p.exists()), None)
    visual_plan = json.loads(vp_path.read_text(encoding="utf-8")) if vp_path else {}
    if isinstance(visual_plan, dict):
        visual_plan = {**visual_plan, "_visuals_dir": str(p_dir / "03_visuals")}
    sentences, script_doc = load_diorama_script_sentences(p_dir)
    fmt_profile = resolve_shorts_format_profile(
        visual_plan,
        script_doc,
        {"sentences": sentences},
        project_id=p_dir.name,
    )
    if fmt_profile == MICRO_SHORT_PROFILE:
        min_clips_req = MICRO_SHORT_CUT_MIN
    elif fmt_profile == SHORTS_EXPRESSIVE_V8_PROFILE:
        from pipeline.config import (
            BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
            EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
            EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
            EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
            is_brain_sim_only_plan,
            is_r72_open_world_v8_plan,
            is_r76_v8_plan,
        )

        if bool(visual_plan.get("allow_legacy_v8_clip_count")):
            min_clips_req = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
        elif is_brain_sim_only_plan(visual_plan, script_doc):
            min_clips_req = BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0]
        elif is_r76_v8_plan(visual_plan, script_doc, project_id=p_dir.name):
            min_clips_req = EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
        elif not is_r72_open_world_v8_plan(visual_plan, script_doc, project_id=p_dir.name):
            min_clips_req = min(EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0], EXPRESSIVE_V8_CLIP_COUNT_RANGE[0])
        else:
            min_clips_req = EXPRESSIVE_V8_CLIP_COUNT_RANGE[0]
    elif fmt_profile == SHORTS_90S_PROFILE:
        min_clips_req = SHORTS_90S_CLIP_COUNT_MIN
    else:
        min_clips_req = DIORAMA_CLIP_COUNT_MIN

    clips_dir = p_dir / "03_visuals" / "flow_native_clips"
    clip_files = _resolve_diorama_clip_files(p_dir / "03_visuals")
    if len(clip_files) < min_clips_req:
        raise RuntimeError(
            f"neuro_diorama assembly requires >= {min_clips_req} clips in {clips_dir} (found {len(clip_files)})"
        )
    if not visual_plan.get("outro_title_lines") and script_doc.get("outro_title_lines"):
        visual_plan["outro_title_lines"] = script_doc["outro_title_lines"]
    is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
    is_v7 = is_v8 or is_diorama_v7_plan(visual_plan) or is_diorama_v7_plan(script_doc)
    if is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V8:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V8,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }
    elif is_v7 and not is_v8 and int(script_doc.get("schema") or 0) < PROMPT_SCHEMA_VERSION_V7:
        script_doc = {
            **script_doc,
            "schema": PROMPT_SCHEMA_VERSION_V7,
            "style_profile": resolve_diorama_v7_style_profile(visual_plan),
        }
    eff_voice_preset = str(
        voice_preset
        or script_doc.get("voice_preset")
        or visual_plan.get("voice_preset")
        or ""
    ).strip() or None
    if eff_voice_preset:
        script_doc = {**script_doc, "voice_preset": eff_voice_preset}

    # 1. Master Voiceover Clock
    audio_dir = p_dir / "04_audio"
    if preserve_audio_master:
        existing_wav = audio_dir / "audio_master.wav"
        existing_vr = audio_dir / "voice_report.json"
        if not existing_wav.exists() or not existing_vr.exists():
            raise FileNotFoundError(
                f"preserve_audio_master=True requires existing {existing_wav} and {existing_vr}"
            )
        verify_script_audio_freshness(p_dir, context="assemble_diorama_project(preserve_audio_master=True)")
        vr = json.loads(existing_vr.read_text(encoding="utf-8"))
        preserved_pcm: np.ndarray | None = None
        preserved_sr = int(vr.get("sample_rate") or 48000)
        needs_stereo_soundscape_mix = False
        try:
            import wave as _wave_mod

            with _wave_mod.open(str(existing_wav), "rb") as _wf_chk:
                if _wf_chk.getnchannels() == 1 and _wf_chk.getsampwidth() == 2:
                    dry_backup = audio_dir / "voice_dry_mono.wav"
                    if not dry_backup.exists():
                        _atomic_copy_file(existing_wav, dry_backup)
                    preserved_sr = int(_wf_chk.getframerate() or preserved_sr)
                    raw_i16 = np.frombuffer(_wf_chk.readframes(_wf_chk.getnframes()), dtype=np.int16)
                    preserved_pcm = (raw_i16.astype(np.float32) / 32768.0).reshape(-1)
                    needs_stereo_soundscape_mix = True
        except Exception:  # noqa: BLE001
            needs_stereo_soundscape_mix = False
        tts_res = {
            "sentence_spans": vr["sentence_spans"],
            "events": vr["events"],
            "speech_end_sec": float(vr["speech_end_sec"]),
            "total_duration_sec": float(vr["total_duration_sec"]),
            "active_speech_ratio": float(vr.get("active_speech_ratio", 0.90)),
            "true_rms_voiced_ratio": vr.get("true_rms_voiced_ratio"),
            "report": vr,
            "pcm": preserved_pcm,
            "sr": preserved_sr,
            "_needs_stereo_soundscape_mix": needs_stereo_soundscape_mix,
        }
    else:
        tts_res = synthesize_continuous_diorama_track(
            project_dir=p_dir,
            sentences=sentences,
            align_whisper=align_whisper,
            pre_synthesized_lines=pre_synthesized_lines,
            script_doc=script_doc,
            rate=tts_rate,
            prosody_mode=prosody_mode,
            voice_preset=eff_voice_preset,
            cpu_budget=cpu_budget,
        )

    # 2. Cross-Cut EDL (applying explicit or prior R64 shift_window_recommendations when present)
    eff_overrides: dict[int, Any] = dict(source_window_overrides or {})
    if apply_posthoc_window_shifts and not eff_overrides:
        vp_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
        authored_starts = {
            idx_1
            for idx_1, cs in enumerate(vp_clips, start=1)
            if isinstance(cs, dict) and (cs.get("src_start_sec") is not None or cs.get("source_start_sec") is not None)
        }
        prev_ph = p_dir / "05_assembly" / "posthoc_semantic_qa_report.json"
        if prev_ph.exists():
            try:
                ph_mtime_ns = prev_ph.stat().st_mtime_ns
                vp_path_chk = p_dir / "03_visuals" / "visual_plan.json"
                plan_not_newer = (not vp_path_chk.exists()) or (ph_mtime_ns >= vp_path_chk.stat().st_mtime_ns)
                ph_doc = json.loads(prev_ph.read_text(encoding="utf-8"))
                ph_src_clips = ph_doc.get("source_clips") if isinstance(ph_doc.get("source_clips"), list) else []
                clip_count_matches = (not ph_src_clips) or (len(ph_src_clips) == len(clip_files))
                if plan_not_newer and clip_count_matches:
                    def _clip_not_regenerated_since_report(cid_1: int) -> bool:
                        if not (1 <= cid_1 <= len(clip_files)):
                            return False
                        try:
                            return ph_mtime_ns >= Path(clip_files[cid_1 - 1]).stat().st_mtime_ns
                        except OSError:
                            return False

                    for rec in (ph_doc.get("summary") or {}).get("shift_window_recommendations") or []:
                        if isinstance(rec, dict) and rec.get("clip_index") and rec.get("recommended_src_window_sec"):
                            c_id = int(rec["clip_index"])
                            if c_id not in authored_starts and _clip_not_regenerated_since_report(c_id):
                                eff_overrides[c_id] = rec["recommended_src_window_sec"]
                    for crep in ph_doc.get("cuts") or []:
                        if (
                            isinstance(crep, dict)
                            and crep.get("remediation") == "shift_edl_source_window"
                            and crep.get("recommended_src_window_sec")
                        ):
                            c_id = int((crep.get("offending_clip_indices") or [crep["clip_index"]])[0])
                            if c_id not in authored_starts and _clip_not_regenerated_since_report(c_id):
                                eff_overrides.setdefault(c_id, crep["recommended_src_window_sec"])
            except Exception:  # noqa: BLE001
                pass

    asm_dir = p_dir / "05_assembly"
    asm_dir.mkdir(parents=True, exist_ok=True)
    edl_path = asm_dir / "edit_decision_list.json"

    def _build_edl_and_audio_outputs(cur_tts_res: dict[str, Any]) -> tuple[dict[str, Any], Path, Path]:
        cur_edl = build_crosscut_edl(
            visual_plan=visual_plan,
            sentence_spans=cur_tts_res["sentence_spans"],
            clip_files=clip_files,
            speech_end_sec=cur_tts_res["speech_end_sec"],
            total_duration_sec=cur_tts_res["total_duration_sec"],
            script_doc=script_doc,
            source_window_overrides=(eff_overrides or None),
        )
        if is_v7 and optimize_plaque_windows:
            cur_edl["plaque_window_refinements"] = refine_plaque_safe_source_windows(
                cur_edl,
                clip_files,
                cache_dir=_segment_cache_dir(p_dir),
            )
        cur_pros_mode = str((cur_tts_res.get("report") or {}).get("prosody_mode") or "uniform_108x")
        cur_edl["prosody_mode"] = cur_pros_mode
        cur_gap_wins = (cur_tts_res.get("report") or {}).get("gap_windows")
        if isinstance(cur_gap_wins, list) and cur_gap_wins:
            cur_edl["gap_windows"] = cur_gap_wins
        if cur_pros_mode != "uniform_108x":
            stamp_windows_local: list[list[float]] = []
            spans_by_idx_local = {int(sp["sentence_index"]): sp for sp in cur_tts_res["sentence_spans"]}
            try:
                pr_doc_local = json.loads((p_dir / "04_audio" / "prosody_report.json").read_text(encoding="utf-8"))
                for row_local in pr_doc_local.get("sentences") or []:
                    si_local = int(row_local["sentence_index"])
                    if row_local.get("gear") == "stamp" and si_local > 1 and (si_local - 1) in spans_by_idx_local and si_local in spans_by_idx_local:
                        w0 = float(spans_by_idx_local[si_local - 1]["end_sec"]) - 0.04
                        w1 = float(spans_by_idx_local[si_local]["start_sec"]) + 0.06
                        if w1 - w0 >= 0.12:
                            stamp_windows_local.append([round(w0, 3), round(w1, 3)])
            except Exception:  # noqa: BLE001
                stamp_windows_local = []
            cur_edl["prosody_stamp_windows"] = stamp_windows_local
        cur_ass = generate_diorama_ass_subtitles(
            ass_path=audio_dir / "subtitles.ass",
            events=cur_tts_res["events"],
            sentence_spans=cur_tts_res["sentence_spans"],
            visual_plan=visual_plan,
            edl=cur_edl,
        )
        if preserve_audio_master and not cur_tts_res.get("_needs_stereo_soundscape_mix"):
            cur_wav = audio_dir / "audio_master.wav"
        else:
            cur_wav = generate_diorama_audio_master(
                wav_path=audio_dir / "audio_master.wav",
                voice_pcm=cur_tts_res["pcm"],
                sr=cur_tts_res["sr"],
                speech_end_sec=cur_edl["speech_end_sec"],
                edl=cur_edl,
            )
        tmp_edl_local = edl_path.with_suffix(".json.tmp")
        tmp_edl_local.write_text(json.dumps(cur_edl, indent=2, ensure_ascii=False), encoding="utf-8")
        os.replace(tmp_edl_local, edl_path)
        return cur_edl, cur_ass, cur_wav

    edl, ass_path, wav_path = _build_edl_and_audio_outputs(tts_res)
    enforce_combined_r88a_r89_edl_contract(
        p_dir,
        edl,
        float(edl.get("total_duration_sec") or tts_res.get("total_duration_sec") or 0.0),
    )

    # 3B. Pre-Assembly 3-Second Audio & ASR Prosody Gate (Workstream 2A: catch word drops BEFORE video encode)
    pre_assembly_prosody_retried_sentences: list[int] = []
    if (not preserve_audio_master) and align_whisper and preview_sec is None:
        try:
            from pipeline import prosody_qa as _prosody_mod

            pre_pros = _prosody_mod.evaluate_prosody_gates_on_audio(
                p_dir,
                audio_path=wav_path,
                gates=("P6_asr_by_gear",),
                run_asr=True,
            )
            p6_gate = (pre_pros.get("gates") or {}).get("P6_asr_by_gear") or {}
            low_sents = sorted(
                {int(i) for i in (p6_gate.get("low_sentences_lt_0_80") or []) if int(i) >= 1}
            )
            if (not p6_gate.get("passed", True)) or low_sents:
                retry_targets = set(low_sents) if low_sents else set(range(1, len(sentences) + 1))
                pre_assembly_prosody_retried_sentences = sorted(retry_targets)
                tts_res = synthesize_continuous_diorama_track(
                    project_dir=p_dir,
                    sentences=sentences,
                    align_whisper=align_whisper,
                    pre_synthesized_lines=None if pre_synthesized_lines is None else pre_synthesized_lines,
                    script_doc=script_doc,
                    rate=tts_rate,
                    prosody_mode=prosody_mode,
                    voice_preset=eff_voice_preset,
                    retry_intact_sentence_indices=retry_targets,
                    cpu_budget=cpu_budget,
                )
                edl, ass_path, wav_path = _build_edl_and_audio_outputs(tts_res)
                enforce_combined_r88a_r89_edl_contract(
                    p_dir,
                    edl,
                    float(edl.get("total_duration_sec") or tts_res.get("total_duration_sec") or 0.0),
                )
        except Exception:  # noqa: BLE001
            logger.warning("Pre-assembly P6 prosody retry failed for %s; retaining initial track", p_dir.name, exc_info=True)

    # 4. Single-pass stitchable ASS segment encode in local /tmp scratch + zero-reencode mux (Speed-3)
    from concurrent.futures import ThreadPoolExecutor
    from pipeline.media_cache import register_staged_copy, stage_local_file

    ff = _ffmpeg()
    fps = int(edl["fps"])
    is_v8_edl = is_v8 or is_expressive_v8_plan(visual_plan, edl)
    is_v7_edl = is_v8_edl or is_v7 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    ceiling_frames = (
        int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps))
        if is_v8_edl
        else (SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_edl else SHORTS_HARD_CEILING_FRAMES)
    )
    total_frames = min(ceiling_frames, int(edl["total_frames"]))
    target_crf = 18 if is_v7_edl else 19
    n_workers = resolve_assembler_workers(cpu_budget)
    seg_ff_threads = resolve_ffmpeg_threads_per_worker(n_workers, cpu_budget)
    xf_workers = resolve_xfade_workers(cpu_budget)
    xf_ff_threads = resolve_ffmpeg_threads_per_worker(xf_workers, cpu_budget)
    preview_result: dict[str, Any] | None = None

    with ram_tempdir(prefix="aab_diorama_asm_") as td:
        td_path = Path(td)
        local_clips: dict[int, Path] = {}
        for idx, cf in enumerate(clip_files, start=1):
            local_clips[idx], _ = stage_local_file(cf)
        pastel_eq_by_num: dict[int, str] = {}
        is_porcelain_edl = is_porcelain_v7_plan(visual_plan, edl)
        if is_v7_edl and not (is_porcelain_edl or is_v8_edl):
            with ThreadPoolExecutor(max_workers=n_workers) as eq_pool:
                eq_vals = list(eq_pool.map(_compute_v7_pastel_eq_filter, [local_clips[i] for i in range(1, len(clip_files) + 1)]))
            pastel_eq_by_num = {i: v for i, v in enumerate(eq_vals, start=1)}

        local_ass = td_path / "subtitles.ass"
        local_wav = td_path / "audio_master.wav"
        shutil.copy2(ass_path, local_ass)
        shutil.copy2(wav_path, local_wav)

        ass_filter = f"ass={local_ass.name}"
        if is_v7_edl:
            fonts_dir = td_path / "fonts"
            fonts_dir.mkdir(parents=True, exist_ok=True)
            bundled_ttf = ensure_bundled_condensed_font()
            shutil.copy2(bundled_ttf, fonts_dir / bundled_ttf.name)
            ass_filter = f"ass={local_ass.name}:fontsdir=fonts"
            font_rep = probe_ass_font_resolution(ff, td_path, local_ass.name, fontsdir="fonts")
            (asm_dir / "font_probe.json").write_text(json.dumps(font_rep, indent=2, ensure_ascii=False), encoding="utf-8")
            if not font_rep["passed"]:
                raise RuntimeError(f"F-2 font guard: libass fell back from {DIORAMA_V7_SUBTITLE_FONT_NAME}: {font_rep['fallbacks'][:2]}")

        # Compute exact clamped per-segment frame counts & start offsets so concat `-c:v copy` equals `total_frames`
        seg_jobs: list[tuple[dict[str, Any], Path, int, float]] = []
        cum_frames = 0
        preview_frames = int(round(float(preview_sec) * fps)) if preview_sec else None
        for cut in edl["cuts"]:
            rem = total_frames - cum_frames
            if preview_frames is not None:
                rem = min(rem, preview_frames - cum_frames)
            if rem <= 0:
                break
            eff_f = min(rem, int(cut["frames"]))
            s_path = td_path / f"seg_{int(cut['cut_index']):03d}.mp4"
            seg_jobs.append((cut, s_path, eff_f, cum_frames / float(fps)))
            cum_frames += eff_f

        # Render 3 clean uncaptioned 1080x1920 preview frames (Act 1, Act 4, Act 6) into 05_assembly/
        # (`06_publish/thumbnail_var_A/B/C.png` are generated via R65 `thumbnail_studio` after final mux).
        pub_dir = p_dir / "06_publish"
        pub_dir.mkdir(parents=True, exist_ok=True)
        total_dur_eff = cum_frames / float(fps)
        thumb_targets = (
            ("A", "frame_preview_A.png", min(total_dur_eff * 0.10, 4.5)),
            ("B", "frame_preview_B.png", total_dur_eff * 0.54),
            ("C", "frame_preview_C.png", total_dur_eff * 0.84),
        )
        for var_tag, t_fname, t_sec in (thumb_targets if preview_sec is None else ()):
            if preserve_audio_master and (asm_dir / f"frame_preview_{var_tag}.png").is_file():
                continue
            chosen_job = seg_jobs[-1]
            for jb in seg_jobs:
                j_start = jb[3]
                j_end = j_start + (jb[2] / float(fps))
                if j_start <= t_sec < j_end:
                    chosen_job = jb
                    break
            j_cut, _, j_frames, j_start = chosen_job
            local_png = td_path / t_fname
            _render_cut_segment(
                ff,
                j_cut,
                local_clips,
                local_png,
                fps,
                pastel_eq_by_num=pastel_eq_by_num,
                cwd=td_path,
                single_frame_offset_sec=max(0.0, t_sec - j_start),
                override_frames=j_frames,
            )
            _atomic_copy_file(local_png, asm_dir / f"frame_preview_{var_tag}.png")

        # Group contiguous Track-V1 camera transitions (`expressive_25d_v8`) underneath crisp Track-V2 ASS subtitles
        def _source_daisy_boundary_mae(cut_a: dict[str, Any], cut_b: dict[str, Any]) -> float:
            pa = local_clips.get(int(cut_a.get("clip_index") or 0))
            pb = local_clips.get(int(cut_b.get("clip_index") or 0))
            if pa is None or pb is None or not pa.exists() or not pb.exists():
                return 99.0
            cap_a = cv2.VideoCapture(str(pa))
            cap_b = cv2.VideoCapture(str(pb))
            try:
                if not cap_a.isOpened() or not cap_b.isOpened():
                    return 99.0
                fps_a = max(1.0, float(cap_a.get(cv2.CAP_PROP_FPS) or 24.0))
                fc_a = max(1, int(cap_a.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                src_end_a = float(cut_a.get("src_end_sec") or 0.0)
                idx_a = max(0, min(fc_a - 1, int(round(src_end_a * fps_a)) - 1))
                fps_b = max(1.0, float(cap_b.get(cv2.CAP_PROP_FPS) or 24.0))
                fc_b = max(1, int(cap_b.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                src_start_b = float(cut_b.get("src_start_sec") or 0.0)
                idx_b = max(0, min(fc_b - 1, int(round(src_start_b * fps_b))))
                cap_a.set(cv2.CAP_PROP_POS_FRAMES, idx_a)
                ok_a, frm_a = cap_a.read()
                cap_b.set(cv2.CAP_PROP_POS_FRAMES, idx_b)
                ok_b, frm_b = cap_b.read()
                if not ok_a or not ok_b or frm_a is None or frm_b is None:
                    return 99.0
                ga = cv2.cvtColor(cv2.resize(frm_a, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                gb = cv2.cvtColor(cv2.resize(frm_b, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                return float(np.mean(np.abs(ga - gb)))
            finally:
                cap_a.release()
                cap_b.release()

        daisy_pair_mae_cache: dict[tuple[int, int], float] = {}

        def _v8_track_v1_spec(
            tr_raw: str,
            cut_a: dict[str, Any] | None = None,
            cut_b: dict[str, Any] | None = None,
        ) -> tuple[str, int]:
            tr_n = str(tr_raw or "").strip().lower()
            allow_alpha = bool((visual_plan or {}).get("allow_alpha_dissolves"))
            if tr_n == "portal_crash_zoom_10f":
                return "smoothup", int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
            if tr_n == "whip_pan_blur_8f":
                return "smoothleft", int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
            if tr_n == "occlusion_wipe":
                return "smoothright", int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
            if allow_alpha:
                if tr_n == "dissolve_15f":
                    return "fade", 15
                if tr_n == "dissolve_12f":
                    return "fade", 12
                if tr_n == "dissolve_8f":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                if tr_n == "dissolve_6f":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
                if tr_n == "split_screen_wipe":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
                if tr_n == "match_cut_bridge":
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
                if tr_n == "daisy_chain_bridge":
                    if cut_a is not None and cut_b is not None:
                        pair_k = (int(cut_a.get("cut_index") or 0), int(cut_b.get("cut_index") or 0))
                        if pair_k not in daisy_pair_mae_cache:
                            daisy_pair_mae_cache[pair_k] = _source_daisy_boundary_mae(cut_a, cut_b)
                        if daisy_pair_mae_cache[pair_k] < 22.0:
                            return "", 0
                    return "fade", int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
            return "", 0

        chains: list[list[tuple[dict[str, Any], Path, int, float]]] = []
        for idx_j, jb in enumerate(seg_jobs):
            prev_tr_name = str(seg_jobs[idx_j - 1][0].get("transition_out") or "").strip().lower() if idx_j > 0 else ""
            prev_xf, prev_ov_f = (
                _v8_track_v1_spec(prev_tr_name, seg_jobs[idx_j - 1][0], jb[0])
                if (is_v8_edl and idx_j > 0)
                else ("", 0)
            )
            prev_bridges = (
                bool(prev_xf)
                and prev_ov_f > 0
                and seg_jobs[idx_j - 1][0].get("mode") == "single"
                and jb[0].get("mode") == "single"
                and seg_jobs[idx_j - 1][2] >= prev_ov_f + 4
                and jb[2] >= prev_ov_f + 4
            )
            if prev_bridges and chains:
                chains[-1].append(jb)
            else:
                chains.append([jb])

        render_tasks: list[tuple[dict[str, Any], Path, int, str]] = []
        dissolve_groups: list[tuple[list[tuple[Path, int, str, int]], Path, float, int]] = []
        concat_names: list[str] = []
        for chain in chains:
            if len(chain) == 1:
                c_item, s_path, eff_f, start_s = chain[0]
                burn_chain = f",setpts=PTS+{start_s:.6f}/TB,{ass_filter},setpts=PTS-STARTPTS"
                render_tasks.append((c_item, s_path, eff_f, burn_chain))
                concat_names.append(s_path.name)
            else:
                grp_inputs: list[tuple[Path, int, str, int]] = []
                for k_ch, (c_item, _s_path, eff_f, _start_s) in enumerate(chain):
                    raw_p = td_path / f"raw_{int(c_item['cut_index']):03d}.mp4"
                    prev_tr_k = str(chain[k_ch - 1][0].get("transition_out") or "").strip().lower() if k_ch > 0 else ""
                    cur_tr_k = str(c_item.get("transition_out") or "").strip().lower() if k_ch < len(chain) - 1 else ""
                    xf_k, ov_f_k = (
                        _v8_track_v1_spec(cur_tr_k, c_item, chain[k_ch + 1][0])
                        if k_ch < len(chain) - 1
                        else ("", 0)
                    )
                    c_mod: dict[str, Any] = dict(c_item)
                    if prev_tr_k == "portal_crash_zoom_10f":
                        c_mod["_portal_zoom_head_frames"] = int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
                    if k_ch < len(chain) - 1 and ov_f_k > 0:
                        req_raw_f = eff_f + ov_f_k + 1
                        if cur_tr_k == "portal_crash_zoom_10f":
                            c_mod["_portal_zoom_tail_start_f"] = max(1, eff_f - 3)
                        if c_mod.get("v8_curve_ramp"):
                            c_mod["curve_nominal_frames"] = req_raw_f
                        else:
                            c_mod["src_end_sec"] = round(float(c_item["src_end_sec"]) + ((ov_f_k + 1) / float(fps)), 4)
                        render_tasks.append((c_mod, raw_p, req_raw_f, ""))
                    else:
                        render_tasks.append((c_mod, raw_p, eff_f, ""))
                    grp_inputs.append((raw_p, eff_f, xf_k, ov_f_k))
                grp_out = td_path / f"grp_{int(chain[0][0]['cut_index']):03d}.mp4"
                dissolve_groups.append((grp_inputs, grp_out, chain[0][3], sum(x[1] for x in grp_inputs)))
                concat_names.append(grp_out.name)

        import hashlib
        import threading

        ass_sha1_cur = hashlib.sha1(local_ass.read_bytes()).hexdigest()
        cache_stats_lock = threading.Lock()
        cache_stats = {"hits": 0, "misses": 0}

        def _render_task(task: tuple[dict[str, Any], Path, int, str]) -> None:
            c_item, out_p, f_cnt, b_chain = task
            use_raw_cache = bool(preview_sec is None and (dissolve_groups or b_chain == ""))
            cache_p = (
                _raw_cut_cache_path(
                    p_dir,
                    c_item,
                    local_clips,
                    fps,
                    f_cnt,
                    pastel_eq_by_num,
                    ass_burn_chain=b_chain,
                    ass_sha1=ass_sha1_cur,
                )
                if use_raw_cache
                else None
            )
            if (
                cache_p is not None
                and cache_p.is_file()
                and cache_p.stat().st_size > 2048
                and _probe_segment_frame_count(cache_p) >= f_cnt
            ):
                out_p.unlink(missing_ok=True)
                try:
                    os.link(cache_p, out_p)
                except OSError:
                    shutil.copy2(cache_p, out_p)
                with cache_stats_lock:
                    cache_stats["hits"] += 1
                return
            seg_preset = "ultrafast" if b_chain == "" else "veryfast"
            seg_crf = max(13, target_crf - 4) if b_chain == "" else target_crf
            _render_cut_segment(
                ff,
                c_item,
                local_clips,
                out_p,
                fps,
                pastel_eq_by_num=pastel_eq_by_num,
                ass_burn_chain=b_chain,
                crf=seg_crf,
                preset=seg_preset,
                cwd=td_path,
                override_frames=f_cnt,
                ffmpeg_threads=seg_ff_threads,
            )
            with cache_stats_lock:
                cache_stats["misses"] += 1
            if cache_p is not None and out_p.is_file() and out_p.stat().st_size > 2048:
                try:
                    _atomic_copy_file(out_p, cache_p)
                except OSError:
                    logger.warning("Failed to persist raw cut segment cache %s", cache_p, exc_info=True)

        prev_cv_threads = cv2.getNumThreads()
        if n_workers > 1 and prev_cv_threads > 1:
            cv2.setNumThreads(1)
        try:
            with ThreadPoolExecutor(max_workers=n_workers) as pool:
                list(pool.map(_render_task, render_tasks))
        finally:
            if n_workers > 1 and prev_cv_threads > 1:
                cv2.setNumThreads(prev_cv_threads)
        raw_segment_cache_hits = int(cache_stats["hits"])
        raw_segment_cache_misses = int(cache_stats["misses"])

        xfmid_cache_dir = _segment_cache_dir(p_dir) / "xfmid_v8"
        xfmid_cache_dir.mkdir(parents=True, exist_ok=True)

        def _file_head_tail_sig(fp: Path) -> str:
            st = fp.stat()
            h = hashlib.sha1()
            h.update(f"{st.st_size}:".encode("utf-8"))
            with fp.open("rb") as fh:
                h.update(fh.read(65536))
                if st.st_size > 131072:
                    fh.seek(max(0, st.st_size - 65536))
                    h.update(fh.read(65536))
            return h.hexdigest()[:18]

        def _run_xfade_batch(
            batch_inputs: list[tuple[Path, int, str, int]],
            out_path: Path,
            burn_start_sec: float | None = None,
        ) -> None:
            is_final_stage = burn_start_sec is not None
            xf_cache_p: Path | None = None
            if not is_final_stage:
                tail_ov_f = int(batch_inputs[-1][3])
                total_out_f = sum(int(x[1]) for x in batch_inputs) + (tail_ov_f + 1 if tail_ov_f > 0 else 0)
                enc_crf = str(max(13, int(target_crf) - 3))
                xf_key = hashlib.sha1(
                    json.dumps(
                        [
                            [_file_head_tail_sig(rp), int(ef), str(xk), int(of)]
                            for rp, ef, xk, of in batch_inputs
                        ]
                        + [int(fps), enc_crf, int(total_out_f)],
                        separators=(",", ":"),
                    ).encode("utf-8")
                ).hexdigest()[:24]
                xf_cache_p = xfmid_cache_dir / f"{xf_key}.mp4"
                if (
                    xf_cache_p.is_file()
                    and xf_cache_p.stat().st_size > 2048
                    and _probe_segment_frame_count(xf_cache_p) >= total_out_f
                ):
                    try:
                        os.link(xf_cache_p, out_path)
                    except OSError:
                        shutil.copy2(xf_cache_p, out_path)
                    return
            _execute_xfade_batch_ffmpeg(
                ff=ff,
                batch_inputs=batch_inputs,
                out_path=out_path,
                fps=fps,
                target_crf=int(target_crf),
                ass_filter=ass_filter,
                burn_start_sec=burn_start_sec,
                cwd=td_path,
                ffmpeg_threads=(resolve_ffmpeg_threads_per_worker(1, cpu_budget) if is_final_stage else xf_ff_threads),
            )
            if xf_cache_p is not None and out_path.is_file() and out_path.stat().st_size > 2048:
                try:
                    _atomic_copy_file(out_path, xf_cache_p)
                except OSError:
                    logger.warning("Failed to persist xfmid segment cache %s", xf_cache_p, exc_info=True)

        for grp_idx, (grp_inputs, grp_out, grp_start_s, _grp_total_f) in enumerate(dissolve_groups):
            cur_stage = list(grp_inputs)
            stage_round = 0
            while len(cur_stage) > 4:
                chunks = [cur_stage[i : i + 4] for i in range(0, len(cur_stage), 4)]
                next_stage: list[tuple[Path, int, str, int]] = []
                sub_jobs: list[tuple[list[tuple[Path, int, str, int]], Path]] = []
                for ch_idx, chunk in enumerate(chunks):
                    if len(chunk) == 1:
                        next_stage.append(chunk[0])
                    else:
                        mid_p = td_path / f"xfmid_g{grp_idx}_r{stage_round}_{ch_idx}.mp4"
                        sub_jobs.append((chunk, mid_p))
                        next_stage.append(
                            (mid_p, sum(int(x[1]) for x in chunk), chunk[-1][2], int(chunk[-1][3]))
                        )
                if sub_jobs:
                    with ThreadPoolExecutor(max_workers=min(xf_workers, len(sub_jobs))) as xf_pool:
                        list(xf_pool.map(lambda jb: _run_xfade_batch(jb[0], jb[1], None), sub_jobs))
                cur_stage = next_stage
                stage_round += 1
            _run_xfade_batch(cur_stage, grp_out, burn_start_sec=grp_start_s)

        concat_txt = td_path / "concat.txt"
        concat_txt.write_text("\n".join(f"file '{nm}'" for nm in concat_names) + "\n", encoding="utf-8")

        active_stamps = [
            ds
            for ds in (edl.get("resolved_data_stamps") or [])
            if isinstance(ds, dict)
            and (preview_sec is None or float(ds.get("start_sec") or 0.0) < float(preview_sec) - 0.5)
        ]
        active_anatomy_callouts = [
            ac
            for ac in (edl.get("resolved_anatomy_callouts") or [])
            if isinstance(ac, dict)
            and (preview_sec is None or float(ac.get("start_sec") or 0.0) < float(preview_sec) - 0.5)
        ]
        if active_stamps or active_anatomy_callouts:
            pre_ov_mp4 = td_path / "pre_overlay_concat.mp4"
            res_pre_ov = subprocess.run(
                [
                    ff,
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
                    str(concat_txt.name),
                    "-c:v",
                    "copy",
                    str(pre_ov_mp4.name),
                ],
                cwd=str(td_path),
                capture_output=True,
                text=True,
                check=False,
                timeout=180,
                stdin=subprocess.DEVNULL,
            )
            if res_pre_ov.returncode != 0 or not pre_ov_mp4.is_file():
                raise RuntimeError(f"Pre-overlay concat failed: {(res_pre_ov.stderr or '')[:300]}")
            cur_ov_mp4 = pre_ov_mp4
            if active_stamps:
                from pipeline.stamp_overlay import composite_data_stamps_on_video

                stamped_mp4 = td_path / "stamped_video_stream.mp4"
                composite_data_stamps_on_video(
                    cur_ov_mp4,
                    stamped_mp4,
                    active_stamps,
                    fps=fps,
                    width=VIDEO_WIDTH,
                    height=VIDEO_HEIGHT,
                )
                cur_ov_mp4 = stamped_mp4
            if active_anatomy_callouts:
                from pipeline.anatomy_overlay import composite_anatomy_labels_on_video

                anat_mp4 = td_path / "anatomy_labeled_video_stream.mp4"
                composite_anatomy_labels_on_video(
                    cur_ov_mp4,
                    anat_mp4,
                    active_anatomy_callouts,
                    fps=fps,
                    width=VIDEO_WIDTH,
                    height=VIDEO_HEIGHT,
                )
                cur_ov_mp4 = anat_mp4
            concat_txt.write_text(f"file '{cur_ov_mp4.name}'\n", encoding="utf-8")

        local_final = td_path / "final_shorts_1080x1920.mp4"
        audio_ch = str(DIORAMA_V7_AUDIO_CHANNELS) if is_v7_edl else "1"
        lim_ceil = "0.812" if is_v7_edl else "0.776"
        # v7: 4x-oversampled (192 kHz) limiter so intersample peaks are caught before AAC; loudness untouched
        lim_chain = (DIORAMA_MUX_TRUE_PEAK_LIMITER if is_v7_edl
                     else f"alimiter=limit={lim_ceil}:attack=5:release=50:level=disabled")
        mux_ceil_sec = EXPRESSIVE_V8_HARD_CEILING_SEC if is_v8_edl else SHORTS_HARD_CEILING_SEC
        exact_dur = min(mux_ceil_sec, cum_frames / float(fps))

        def _run_final_mux(trim_db: float) -> subprocess.CompletedProcess:
            vol = f"volume={trim_db:.2f}dB," if trim_db < 0 else ""
            return subprocess.run(
                [
                    ff, "-nostdin", "-hide_banner", "-loglevel", "error", "-y",
                    "-f", "concat", "-safe", "0", "-i", str(concat_txt.name),
                    "-i", str(local_wav.name),
                    "-map", "0:v:0", "-map", "1:a:0",
                    "-c:v", "copy",
                    "-af", f"atrim=0:{exact_dur:.6f},asetpts=PTS-STARTPTS,{vol}{lim_chain}",
                    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", audio_ch,
                    "-movflags", "+faststart",
                    str(local_final.name),
                ],
                cwd=str(td_path), capture_output=True, text=True, check=False, timeout=300, stdin=subprocess.DEVNULL,
            )

        mux_trim_cache_p = _segment_cache_dir(p_dir) / "mux_trim_cache.json"
        wav_trim_key = f"{_file_head_tail_sig(local_wav)}|{exact_dur:.3f}" if dissolve_groups or is_v7_edl else ""
        mux_trim_cache: dict[str, float] = {}
        if mux_trim_cache_p.is_file():
            try:
                mux_trim_cache = json.loads(mux_trim_cache_p.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001
                mux_trim_cache = {}
        mux_trim_db = float(mux_trim_cache.get(wav_trim_key, 0.0)) if wav_trim_key else 0.0
        res_mux = _run_final_mux(mux_trim_db)
        # AAC true-peak guard: the sample-peak limiter cannot see AAC intersample overshoot (up to ~1.4 dB on
        # restored-HF consonant transients). Re-encode with a static trim until the encoded file sits under target.
        for _ in range(3):
            if res_mux.returncode != 0 or not local_final.exists():
                break
            tp_enc = _measure_true_peak_dbtp(local_final)
            if tp_enc is None or tp_enc <= DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP:
                break
            mux_trim_db -= (tp_enc - DIORAMA_MUX_TRUE_PEAK_TARGET_DBTP) + 0.1
            res_mux = _run_final_mux(mux_trim_db)
        if wav_trim_key and res_mux.returncode == 0:
            try:
                mux_trim_cache[wav_trim_key] = round(mux_trim_db, 4)
                mux_trim_cache_p.write_text(json.dumps(mux_trim_cache, indent=2), encoding="utf-8")
            except OSError:
                pass
        if res_mux.returncode != 0 or not local_final.exists():
            raise RuntimeError(f"FFmpeg final mux failed: {res_mux.stderr[:300]}")
        if preview_sec is not None:
            prev_mp4 = asm_dir / f"preview_0-{int(round(float(preview_sec)))}s.mp4"
            _atomic_copy_file(local_final, prev_mp4, suffix=".mp4.tmp")
            preview_result = {
                "project_dir": str(p_dir),
                "preview_mp4": str(prev_mp4),
                "preview_sec": round(cum_frames / float(fps), 3),
                "prosody_mode": edl.get("prosody_mode"),
                "plaque_window_refinements": edl.get("plaque_window_refinements"),
                "rebuilt": True,
            }
        else:
            if not dissolve_groups:
                _store_segment_cache(p_dir, seg_jobs, edl, ass_path)
            _atomic_copy_file(local_final, final_mp4, suffix=".mp4.tmp")
            register_staged_copy(local_final, final_mp4)
            from pipeline import thumbnail as thumbnail_studio

            thumbnail_studio.run(
                p_dir,
                force=bool(force_rebuild and not preserve_audio_master),
                strict=False,
                local_clips=local_clips,
                pastel_eq_by_num=pastel_eq_by_num,
            )

    if preview_result is not None:
        enforce_ram_scratch_budget()
        return preview_result

    if fmt_profile in (MICRO_SHORT_PROFILE, SHORTS_90S_PROFILE, SHORTS_EXPRESSIVE_V8_PROFILE):
        probe_min_dur, probe_max_dur = shorts_duration_range_for_profile(
            fmt_profile,
            project_id=p_dir.name,
            plan=visual_plan,
            script_doc=script_doc,
        )
    else:
        probe_min_dur = DIORAMA_V7_DURATION_MIN_SEC if is_v7_edl else None
        probe_max_dur = None
    probe_report = MediaIntegrityValidator.validate_video_asset(
        final_mp4,
        asset_type="final_shorts",
        strict=True,
        min_duration_sec=probe_min_dur,
        max_duration_sec=probe_max_dur,
    )
    tmp_probe = asm_dir / "probe_report.json.tmp"
    tmp_probe.write_text(json.dumps(probe_report, indent=2, ensure_ascii=False), encoding="utf-8")
    os.replace(tmp_probe, asm_dir / "probe_report.json")
    manifest_path = p_dir / "00_project_manifest.json"
    if manifest_path.exists():
        try:
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
            manifest["status"] = "ASSEMBLED"
            manifest["clip_count"] = len(clip_files)
            manifest["cut_count"] = edl["cut_count"]
            manifest["max_clip_reuse"] = edl.get("max_clip_reuse", 1)
            manifest["duration_sec"] = edl["total_duration_sec"]
            manifest["final_mp4"] = str(final_mp4)
            if (tts_res.get("report") or {}).get("voice_preset"):
                manifest["voice_preset"] = tts_res["report"]["voice_preset"]
            manifest_path.write_text(json.dumps(manifest, indent=2, ensure_ascii=False), encoding="utf-8")
        except Exception:
            pass

    posthoc_summary = None
    if run_posthoc_qa:
        from pipeline.posthoc_qa import run_posthoc_semantic_qa

        ph_rep = run_posthoc_semantic_qa(
            p_dir,
            render_strips=True,
            run_asr_sync=align_whisper,
            save_report=True,
            sync_knowledge_base=False,
        )
        posthoc_summary = {
            "passed": ph_rep["passed"],
            "cv_passed": ph_rep.get("cv_passed", False),
            "mean_clarity_score": ph_rep["summary"]["mean_clarity_score"],
            "weak_cut_indices": ph_rep["summary"]["weak_cut_indices"],
            "viewer_sheets": ph_rep.get("viewer_sheets") or [],
            "semantic_review": ph_rep.get("semantic_review") or {},
        }

    if manifest_path.exists():
        from pipeline.storage import ProjectStorage

        ProjectStorage.sync_existing_manifest_from_disk(p_dir, status="ASSEMBLED")

    out_payload = {
        "project_dir": str(p_dir),
        "final_mp4": str(final_mp4),
        "edl_path": str(edl_path),
        "ass_path": str(ass_path),
        "wav_path": str(wav_path),
        "duration_sec": edl["total_duration_sec"],
        "cut_count": edl["cut_count"],
        "cut_duration_cv": edl.get("cut_duration_cv"),
        "max_clip_reuse": edl.get("max_clip_reuse", 1),
        "avg_cut_duration_sec": edl["avg_cut_duration_sec"],
        "active_speech_ratio": tts_res["active_speech_ratio"],
        "true_rms_voiced_ratio": tts_res.get("true_rms_voiced_ratio"),
        "voice_preset": (tts_res.get("report") or {}).get("voice_preset"),
        "raw_segment_cache_hits": raw_segment_cache_hits,
        "raw_segment_cache_misses": raw_segment_cache_misses,
        "pre_assembly_prosody_retried_sentences": pre_assembly_prosody_retried_sentences,
        "rebuilt": True,
    }
    if posthoc_summary is not None:
        out_payload["posthoc_qa"] = posthoc_summary
    enforce_ram_scratch_budget()
    return out_payload


assemble_diorama_episode = assemble_diorama_project
