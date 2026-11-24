"""ALL ABOUT BRAIN — Audio-First EDL, Source Window Selector & R88/R89 Contract (`assembler_edl.py`)."""

from __future__ import annotations
from pipeline import config as _cfg
from pipeline.assembler_subtitles import *
from pipeline.assembler_audio import *
from pipeline.assembler_subtitles import _KEYWORD_BEAT_SPLIT_RE, _V7_DEFAULT_CAM_CYCLE, _V8_POWER_TOKENS, _V8_STOPWORDS, _clip_duration, _ffmpeg, _format_ass_ts, _frame_boundary_ass_sec, _parse_ass_time, _sanitize_ass_multiline, _sanitize_ass_single_line, _write_mono_wav, ensure_bundled_condensed_font, generate_diorama_ass_subtitles, probe_ass_font_resolution
from pipeline.assembler_audio import _measure_true_peak_dbtp, _synthesize_documentary_pulse_bgm, _synthesize_expressive_v8_ambience_and_foley, _synthesize_stereo_orchestral_bgm, _synthesize_v8_foley_oneshot, _write_stereo_wav, generate_diorama_audio_master

def load_diorama_script_sentences(project_dir: Path) -> tuple[list[str], dict[str, Any]]:
    """Loads ordered US English sentences and full script dict from `02_script/script.json`."""
    p_dir = Path(project_dir)
    script_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
    if script_path is None:
        raise FileNotFoundError(f"script.json not found in {p_dir}")
    doc = json.loads(script_path.read_text(encoding="utf-8"))
    if isinstance(doc.get("sentences"), list) and doc["sentences"]:
        sents = [str(s).strip() for s in doc["sentences"] if str(s).strip()]
    elif isinstance(doc.get("acts"), list) and doc["acts"]:
        sents = [
            str(s).strip()
            for act in doc["acts"]
            if isinstance(act, dict)
            for s in (act.get("sentences") or [])
            if str(s).strip()
        ]
    elif isinstance(doc.get("clip_narrations"), list) and doc["clip_narrations"]:
        sents = [str(s).strip() for s in doc["clip_narrations"] if str(s).strip()]
    else:
        raise ValueError(f"No sentences/acts/clip_narrations found in {script_path}")
    return sents, doc


def compute_script_freshness_digests(project_dir: Path) -> dict[str, Any]:
    """Computes raw file SHA-256 and normalized spoken-sentences SHA-256 for `02_script/script.json`."""
    p_dir = Path(project_dir)
    script_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
    if script_path is None:
        return {"script_path": None, "script_sha256": "", "sentences_sha256": "", "script_mtime": None}
    raw_bytes = script_path.read_bytes()
    script_sha256 = hashlib.sha256(raw_bytes).hexdigest()
    sentences_sha256 = ""
    try:
        sents, _ = load_diorama_script_sentences(p_dir)
        sentences_sha256 = hashlib.sha256(
            json.dumps([str(s).strip() for s in sents if str(s).strip()], ensure_ascii=False, separators=(",", ":")).encode("utf-8")
        ).hexdigest()
    except Exception:
        sentences_sha256 = ""
    return {
        "script_path": script_path,
        "script_sha256": script_sha256,
        "sentences_sha256": sentences_sha256,
        "script_mtime": float(script_path.stat().st_mtime),
    }


def verify_script_audio_freshness(project_dir: Path, *, context: str = "QA") -> dict[str, Any]:
    """
    Mtime + SHA-256 guard ensuring `02_script/script.json` has not been modified after
    `04_audio/audio_master.wav` / `04_audio/voice_report.json`.
    Raises `RuntimeError` so cached assembly, `preserve_audio_master`, `recut`, and QA gates
    refuse to run against stale audio/EDL artifacts.
    """
    p_dir = Path(project_dir)
    dig = compute_script_freshness_digests(p_dir)
    script_path: Path | None = dig["script_path"]
    if script_path is None:
        return {"fresh": True, "checked": False, "reason": "no_script_json"}

    wav_path = p_dir / "04_audio" / "audio_master.wav"
    vr_path = p_dir / "04_audio" / "voice_report.json"
    script_mtime = float(dig["script_mtime"])
    wav_mtime: float | None = None

    if wav_path.exists():
        wav_mtime = float(wav_path.stat().st_mtime)
        dt = script_mtime - wav_mtime
        if dt > SCRIPT_AUDIO_MTIME_TOLERANCE_SEC:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: {script_path.name} is newer than audio_master.wav "
                f"by {dt:.2f}s in '{p_dir.name}'. Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )

    if vr_path.exists():
        try:
            vr = json.loads(vr_path.read_text(encoding="utf-8"))
        except Exception as exc:
            raise RuntimeError(f"[{context}] Corrupt voice_report.json in '{p_dir.name}': {exc}") from exc
        vr_script_sha = str(vr.get("script_sha256") or "").strip()
        if vr_script_sha and dig["script_sha256"] and vr_script_sha != dig["script_sha256"]:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: script.json sha256 ({dig['script_sha256'][:12]}) != "
                f"voice_report.script_sha256 ({vr_script_sha[:12]}) in '{p_dir.name}'. "
                "Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )
        vr_sents_sha = str(vr.get("sentences_sha256") or "").strip()
        if vr_sents_sha and dig["sentences_sha256"] and vr_sents_sha != dig["sentences_sha256"]:
            raise RuntimeError(
                f"[{context}] Stale audio/assembly guard: script sentences sha256 ({dig['sentences_sha256'][:12]}) != "
                f"voice_report.sentences_sha256 ({vr_sents_sha[:12]}) in '{p_dir.name}'. "
                "Re-run TTS synthesis and full assembly (`diorama-assemble --force`) first."
            )

    return {
        "fresh": True,
        "checked": bool(wav_path.exists() or vr_path.exists()),
        "script_mtime": script_mtime,
        "audio_mtime": wav_mtime,
        "script_sha256": dig["script_sha256"],
        "sentences_sha256": dig["sentences_sha256"],
    }


def _sentence_act_map(script_doc: dict[str, Any], n_sentences: int) -> dict[int, int]:
    """Maps 1-based sentence_index -> act number (1..6)."""
    mapping: dict[int, int] = {}
    acts = script_doc.get("acts") if isinstance(script_doc.get("acts"), list) else []
    if acts:
        cursor = 1
        for a_idx, act in enumerate(acts, start=1):
            sents = (act.get("sentences") or []) if isinstance(act, dict) else []
            for _ in sents:
                if cursor <= n_sentences:
                    mapping[cursor] = min(DIORAMA_ACT_COUNT, a_idx)
                    cursor += 1
        while cursor <= n_sentences:
            mapping[cursor] = DIORAMA_ACT_COUNT
            cursor += 1
        return mapping
    for i in range(1, n_sentences + 1):
        mapping[i] = min(DIORAMA_ACT_COUNT, ((i - 1) * DIORAMA_ACT_COUNT) // max(1, n_sentences) + 1)
    return mapping


def _compute_max_clip_reuse(cuts: list[dict[str, Any]]) -> int:
    counts: dict[int, int] = {}
    for c in cuts:
        p_idx = c.get("clip_index")
        if p_idx is not None:
            counts[int(p_idx)] = counts.get(int(p_idx), 0) + 1
        s_idx = c.get("secondary_clip_index")
        if s_idx is not None:
            counts[int(s_idx)] = counts.get(int(s_idx), 0) + 1
    return max(counts.values()) if counts else 0


def _resolve_v7_clip_camera(spec: dict[str, Any], idx_0based: int) -> str:
    """Resolves Schema v7/v8 camera_move identically to build_diorama_v7_prompts / build_expressive_v8_prompts."""
    from pipeline.config import EXPRESSIVE_V8_CAMERA_MOVES

    explicit_cam = str(spec.get("camera") or spec.get("camera_move") or "").strip().lower()
    if explicit_cam in DIORAMA_V7_CAMERA_MOVES or explicit_cam in EXPRESSIVE_V8_CAMERA_MOVES:
        return explicit_cam
    if str(spec.get("cut_role") or "").strip().lower() == "outro":
        return "tilt_up"
    cam = _V7_DEFAULT_CAM_CYCLE[idx_0based % len(_V7_DEFAULT_CAM_CYCLE)]
    g = str(spec.get("grammar") or spec.get("visual_grammar") or "").strip().lower()
    if g in ("lowpoly_hands_closeup", "porcelain_hands_closeup", "hands_closeup") and cam in ("tilt_up", "clean_pullback_reveal"):
        cam = "locked_tripod" if cam == "tilt_up" else "gentle_push_in"
    return cam


def _select_v7_source_window(
    clip_path: Path,
    clip_dur: float,
    out_dur: float,
    spec: dict[str, Any] | None = None,
    override_src_start_sec: float | None = None,
    override_src_end_sec: float | None = None,
) -> tuple[float, float]:
    """
    Selects `[src_start_sec, src_span_sec]` inside an 8.0s native Flow clip:
      - Honors explicit `override_src_start_sec` / `override_src_end_sec` (e.g. from R64
        `shift_window_recommendations`) or authored `spec["src_start_sec"]` / `spec["max_src_end_sec"]`.
      - On real video clips with `>= 0.90s` slack, samples sequential low-res grayscale frames and
        scores candidate windows by combining physical motion (`raw_mad`) with upper-center
        `[22%..56%]` focal-zone Canny edge occupancy so `tilt_down` / `pan_*` reveals never slice
        empty-wall pre-roll before the primary subject enters frame.
    """
    spec_d = spec if isinstance(spec, dict) else {}
    allow_slowmo = bool(spec_d.get("allow_slowmo_stretch"))
    max_usable_end = max(0.62, float(clip_dur) - 0.08)
    explicit_end = (
        override_src_end_sec
        if override_src_end_sec is not None
        else (
            spec_d.get("max_src_end_sec")
            if spec_d.get("max_src_end_sec") is not None
            else spec_d.get("src_end_sec")
        )
    )
    if explicit_end is not None:
        try:
            max_usable_end = max(0.62, min(max_usable_end, float(explicit_end)))
        except (TypeError, ValueError):
            pass
    elif bool(spec_d.get("end_reference_image")) and clip_path.exists() and clip_path.stat().st_size >= 8_192:
        end_ref_str = str(spec_d.get("end_reference_image") or "").strip()
        cand_refs = [
            clip_path.parent.parent / "reference_images" / Path(end_ref_str).name,
            clip_path.parent.parent.parent / end_ref_str,
        ]
        ref_png = next((rp for rp in cand_refs if rp.exists() and rp.is_file()), None)
        if ref_png is not None:
            ref_im = cv2.imread(str(ref_png))
            if ref_im is not None:
                ref_g = cv2.cvtColor(cv2.resize(ref_im, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                cap_kf = cv2.VideoCapture(str(clip_path))
                try:
                    if cap_kf.isOpened():
                        fps_kf = max(1.0, float(cap_kf.get(cv2.CAP_PROP_FPS) or 24.0))
                        fc_kf = max(1, int(cap_kf.get(cv2.CAP_PROP_FRAME_COUNT) or 1))
                        best_mae = 999.0
                        best_idx = fc_kf - 1
                        for f_i in range(max(0, fc_kf - 12), fc_kf):
                            cap_kf.set(cv2.CAP_PROP_POS_FRAMES, f_i)
                            ok_f, frm_f = cap_kf.read()
                            if ok_f and frm_f is not None:
                                fg = cv2.cvtColor(cv2.resize(frm_f, (180, 320)), cv2.COLOR_BGR2GRAY).astype(np.float32)
                                m_val = float(np.mean(np.abs(fg - ref_g)))
                                if m_val < best_mae:
                                    best_mae = m_val
                                    best_idx = f_i
                        if best_mae < 24.0:
                            snapped_end = (best_idx + 1) / fps_kf
                            max_usable_end = max(0.62, min(float(clip_dur) - 0.02, snapped_end))
                finally:
                    cap_kf.release()
    min_non_slowmo_span = min(max(0.50, float(clip_dur) - 0.08), float(out_dur))
    if not allow_slowmo and (max_usable_end - 0.06) < min_non_slowmo_span and float(clip_dur) >= float(out_dur) + 0.08:
        # Never accidentally clamp a native full-length clip below out_dur into artificial slow-mo stretch.
        max_usable_end = max(max_usable_end, min(float(clip_dur) - 0.04, 0.06 + min_non_slowmo_span))
    from pipeline.config import (
        EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
        EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC,
        EXPRESSIVE_V8_NEURAL_DIVE_MOVES,
        EXPRESSIVE_V8_NEURAL_DIVE_PEAK_WINDOW_SEC,
        R79M_HUMAN_CUT_MAX_MAIN_SPEED,
    )

    is_r79m_snappy = bool(spec_d.get("_r79m_snappy_human") or spec_d.get("r79m_snappy_human"))
    is_full_traj = bool(spec_d.get("end_reference_image") or spec_d.get("full_trajectory_span"))
    cam_spec_cur = str(spec_d.get("camera_move") or spec_d.get("camera") or "").strip()
    is_sim_3d = (
        str(spec_d.get("grammar") or "") == "brain_simulator_3d"
        or str(spec_d.get("render_engine") or "") == "blender_3d_simulator"
        or "brain_simulator_clips" in str(clip_path)
    )
    if is_sim_3d:
        exp_sim_s = (
            override_src_start_sec
            if override_src_start_sec is not None
            else (
                spec_d.get("src_start_sec")
                if spec_d.get("src_start_sec") is not None
                else spec_d.get("source_start_sec")
            )
        )
        is_flow_brain = (
            str(spec_d.get("render_engine") or "").strip().lower() == "google_flow"
            and "brain_simulator_clips" not in str(clip_path)
        )
        sim_s = 0.0
        if exp_sim_s is not None:
            try:
                sim_s = max(0.0, min(max(0.0, float(clip_dur) - float(out_dur) - 0.04), float(exp_sim_s)))
            except (TypeError, ValueError):
                sim_s = 0.0
        elif is_flow_brain and float(clip_dur) >= float(out_dur) + 0.32:
            sim_s = 0.20
        span_sim = max(0.50, min(max(0.50, float(clip_dur) - sim_s - (0.04 if sim_s > 0.0 else 0.0)), float(out_dur)))
        return round(sim_s, 4), round(span_sim, 4)
    default_s = 0.12
    if cam_spec_cur in EXPRESSIVE_V8_DRONE_CAMERA_MOVES and not is_full_traj:
        peak_s = float(EXPRESSIVE_V8_DRONE_PEAK_CORE_WINDOW_SEC[0])
        if max_usable_end - peak_s >= max(0.50, float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)) + 0.10:
            default_s = peak_s
    elif cam_spec_cur in EXPRESSIVE_V8_NEURAL_DIVE_MOVES and cam_spec_cur != "neural_macro_orbit_hold" and not is_full_traj:
        peak_s = float(EXPRESSIVE_V8_NEURAL_DIVE_PEAK_WINDOW_SEC[0])
        if max_usable_end - peak_s >= max(0.50, float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)) + 0.10:
            default_s = peak_s
    target_src_span = float(out_dur) * float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED)
    if not allow_slowmo:
        target_src_span = max(float(out_dur), target_src_span)
    if not allow_slowmo and (max_usable_end - default_s) < float(out_dur) and (max_usable_end - 0.06) >= float(out_dur):
        default_s = max(0.06, max_usable_end - max(float(out_dur), target_src_span))
    default_avail = max(0.50, max_usable_end - default_s)
    default_span = target_src_span if default_avail >= target_src_span else default_avail

    explicit_start = (
        override_src_start_sec
        if override_src_start_sec is not None
        else (
            spec_d.get("src_start_sec")
            if spec_d.get("src_start_sec") is not None
            else spec_d.get("source_start_sec")
        )
    )
    if explicit_start is not None:
        try:
            exp_s = float(explicit_start)
            if not allow_slowmo:
                needed_span = min(max(0.50, max_usable_end - 0.06), max(float(out_dur), target_src_span))
                latest_s = max(0.06, max_usable_end - needed_span)
                chosen_s = max(0.06, min(latest_s, exp_s))
            elif explicit_end is not None or is_full_traj:
                chosen_s = max(0.06, min(max(0.06, max_usable_end - 0.50), exp_s))
            else:
                latest_s = max(0.08, max_usable_end - default_span)
                chosen_s = max(0.08, min(latest_s, exp_s))
            avail = max(0.50, max_usable_end - chosen_s)
            if is_full_traj and avail >= float(out_dur):
                return round(chosen_s, 4), round(avail, 4)
            return round(chosen_s, 4), round(target_src_span if avail >= target_src_span else avail, 4)
        except (TypeError, ValueError):
            pass

    if is_full_traj and clip_dur >= float(out_dur) + 0.16:
        traj_s = 0.06
        traj_span = max(float(out_dur), max_usable_end - traj_s)
        if is_r79m_snappy:
            traj_span = min(traj_span, float(out_dur) * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))
        if (
            str(spec_d.get("grammar") or "") in ("architectural_cutaway_portal", "expressive_exterior_establishing")
            and clip_path.exists()
            and clip_path.stat().st_size >= 8_192
            and (max_usable_end - (traj_s + 0.85)) >= traj_span
        ):
            try:
                from pipeline.flow_worker import _max_horizontal_plaque_glyph_run

                cap_p = cv2.VideoCapture(str(clip_path))
                if cap_p.isOpened():
                    pfps = max(1.0, float(cap_p.get(cv2.CAP_PROP_FPS) or 24.0))
                    cap_p.set(cv2.CAP_PROP_POS_FRAMES, int(round((traj_s + 0.22) * pfps)))
                    ok_p0, fr_p0 = cap_p.read()
                    if ok_p0 and fr_p0 is not None and _max_horizontal_plaque_glyph_run(fr_p0) >= 5:
                        for cand_nudge in (0.75, 0.95, 1.15):
                            if (max_usable_end - cand_nudge) < traj_span:
                                break
                            cap_p.set(cv2.CAP_PROP_POS_FRAMES, int(round((cand_nudge + 0.18) * pfps)))
                            ok_pn, fr_pn = cap_p.read()
                            if ok_pn and fr_pn is not None and _max_horizontal_plaque_glyph_run(fr_pn) < 5:
                                traj_s = cand_nudge
                                break
                    cap_p.release()
            except Exception:  # noqa: BLE001
                pass
        return round(traj_s, 4), round(traj_span, 4)

    if is_r79m_snappy and clip_dur >= float(out_dur) + 0.12 and clip_path.exists() and clip_path.stat().st_size >= 8_192:
        from pipeline.media_cache import cached_by_clip_stat

        min_s_r79 = 0.16 if (max_usable_end - 0.16) >= float(out_dur) else 0.06
        max_avail_r79 = max(0.50, max_usable_end - min_s_r79)
        # Prefer 1.25x snappy cadence (maps 24fps Flow natively 1:1 onto 30fps without frame-drop judder)
        pref_span = float(out_dur) * 1.25
        if max_avail_r79 >= pref_span:
            r79_span = pref_span
        else:
            r79_span = min(max_avail_r79, max(float(out_dur), float(out_dur) * min(float(R79M_HUMAN_CUT_MAX_MAIN_SPEED), max_avail_r79 / max(0.1, float(out_dur)))))
        r79_span = min(r79_span, float(out_dur) * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))

        if (max_usable_end - min_s_r79 - r79_span) < 0.24:
            return round(min_s_r79, 4), round(r79_span, 4)

        def _probe_r79_dis_tel(local_clip: Path) -> dict[str, Any]:
            cap_d = cv2.VideoCapture(str(local_clip))
            if not cap_d.isOpened():
                return {"ok": False}
            sfps = max(1.0, float(cap_d.get(cv2.CAP_PROP_FPS) or 24.0))
            sw_d, sh_d = 270, 480
            gs: list[np.ndarray] = []
            ts: list[float] = []
            fi_d = 0
            while True:
                ok_d, bgr_d = cap_d.read()
                if not ok_d:
                    break
                if fi_d % 2 == 0:
                    t_c = fi_d / sfps
                    if t_c <= max_usable_end + 0.06:
                        sm_d = cv2.resize(bgr_d, (sw_d, sh_d), interpolation=cv2.INTER_AREA)
                        gs.append(cv2.cvtColor(sm_d, cv2.COLOR_BGR2GRAY))
                        ts.append(round(t_c, 4))
                fi_d += 1
            cap_d.release()
            if len(gs) < 5:
                return {"ok": False}
            dis_f = cv2.DISOpticalFlow_create(cv2.DISOPTICAL_FLOW_PRESET_FAST)
            b_mask = np.ones((sh_d, sw_d), dtype=bool)
            b_mask[int(sh_d * 0.22) : int(sh_d * 0.82), int(sw_d * 0.18) : int(sw_d * 0.82)] = False
            pairs: list[list[float]] = []
            for k_i in range(len(gs) - 1):
                fl = dis_f.calc(gs[k_i], gs[k_i + 1], None)
                fx_d, fy_d = fl[..., 0], fl[..., 1]
                mvx = float(np.median(fx_d[b_mask]))
                mvy = float(np.median(fy_d[b_mask]))
                res_m = np.hypot(fx_d - mvx, fy_d - mvy)
                roi_m = res_m[int(sh_d * 0.12) : int(sh_d * 0.88), int(sw_d * 0.12) : int(sw_d * 0.88)]
                p90_v = float(np.percentile(roi_m, 90))
                pairs.append([round(0.5 * (ts[k_i] + ts[k_i + 1]), 4), round(p90_v, 4)])
            return {"ok": True, "pairs": pairs}

        r79_tel = cached_by_clip_stat(
            clip_path,
            namespace="v8_r79_dis_tel_v1",
            compute_fn=_probe_r79_dis_tel,
            extra_key=f"{round(max_usable_end, 2)}",
        )
        if isinstance(r79_tel, dict) and r79_tel.get("ok") and r79_tel.get("pairs"):
            p_list = [(float(tm), float(pv)) for tm, pv in r79_tel["pairs"]]
            latest_ws = max(min_s_r79, max_usable_end - r79_span)
            best_ws = min_s_r79
            best_wscore = -1.0
            ws_c = min_s_r79
            while ws_c <= latest_ws + 1e-6:
                we_c = ws_c + r79_span
                vals_w = [pv for tm, pv in p_list if ws_c - 1e-3 <= tm <= we_c + 1e-3]
                if len(vals_w) >= 2:
                    h_w = max(1, len(vals_w) // 2)
                    m_all = float(np.mean(vals_w))
                    sh_r = float(np.mean(vals_w[h_w:]) / max(0.15, float(np.mean(vals_w[:h_w]))))
                    tail_mult = min(1.12, max(0.25, sh_r)) if sh_r < 0.45 else min(1.12, 0.85 + 0.25 * min(1.2, sh_r))
                    dead_head = 0.82 if vals_w[0] < 0.65 else 1.0
                    sc_w = m_all * tail_mult * dead_head
                    if sc_w > best_wscore:
                        best_wscore = sc_w
                        best_ws = ws_c
                ws_c += 0.20
            return round(best_ws, 4), round(r79_span, 4)
        return round(min_s_r79, 4), round(r79_span, 4)

    if (
        out_dur > PORCELAIN_V7_LONG_TAKE_MAX_SEC
        or (max_usable_end - default_s - out_dur) < 0.90
        or not clip_path.exists()
        or clip_path.stat().st_size < 8_192
    ):
        return default_s, round(default_span, 4)

    from pipeline.media_cache import cached_by_clip_stat

    is_brain_clip = str(spec_d.get("grammar") or "").strip() in ("lowpoly_matte_brain", "porcelain_living_brain", "living_brain")
    action_blob = " ".join(
        str(spec_d.get(k) or "") for k in ("action", "prop_action", "consequence", "comparison_action", "internal_mechanism")
    ).lower()
    upward_bias = any(tok in action_blob for tok in ("upward", "blast", "sparks", "airborne", "sky", "shoots", "streaks"))

    def _probe_clip_tel(local_clip: Path) -> dict[str, Any]:
        cap = cv2.VideoCapture(str(local_clip))
        if not cap.isOpened():
            return {"ok": False}
        src_fps = float(cap.get(cv2.CAP_PROP_FPS) or 24.0)
        step = max(1, int(round(src_fps * 0.25)))
        s_t: list[float] = []
        s_g: list[np.ndarray] = []
        s_focal: list[float] = []
        s_chroma: list[float] = []
        f_idx = 0
        while True:
            ok, frm = cap.read()
            if not ok:
                break
            if f_idx % step == 0:
                t_cur = f_idx / max(1.0, src_fps)
                if t_cur <= max_usable_end + 0.05:
                    small_bgr = cv2.resize(frm, (90, 160))
                    g_small = cv2.cvtColor(small_bgr, cv2.COLOR_BGR2GRAY)
                    focal_roi = g_small[int(160 * 0.22) : int(160 * 0.56), int(90 * 0.08) : int(90 * 0.92)]
                    focal_e = float(np.mean(cv2.Canny(focal_roi, 45, 135) > 0))
                    if is_brain_clip:
                        lab_roi = cv2.cvtColor(
                            small_bgr[int(160 * 0.20) : int(160 * 0.72), int(90 * 0.12) : int(90 * 0.88)],
                            cv2.COLOR_BGR2LAB,
                        ).astype(np.float32)
                        chroma_dev = np.hypot(lab_roi[:, :, 1] - 130.5, lab_roi[:, :, 2] - 144.0)
                        s_chroma.append(round(float(np.mean(chroma_dev > 11.5)), 6))
                    else:
                        s_chroma.append(0.0)
                    s_t.append(round(t_cur, 5))
                    s_g.append(g_small)
                    s_focal.append(round(focal_e, 6))
            f_idx += 1
        cap.release()
        if len(s_g) < 6:
            return {"ok": False}
        steps: list[list[float]] = []
        for i in range(1, len(s_g)):
            diff_full = np.abs(s_g[i].astype(np.float32) - s_g[i - 1].astype(np.float32))
            raw_mad = float(np.mean(diff_full))
            upper = float(np.mean(diff_full[8:92, :]))
            lower = float(np.mean(diff_full[92:, :]))
            steps.append([round(0.5 * (s_t[i - 1] + s_t[i]), 5), round(raw_mad, 5), round(upper, 5), round(lower, 5)])
        return {
            "ok": True,
            "sampled_t": s_t,
            "sampled_focal": s_focal,
            "sampled_chroma": s_chroma,
            "steps": steps,
        }

    tel = cached_by_clip_stat(
        clip_path,
        namespace="v7_win_tel_v1",
        compute_fn=_probe_clip_tel,
        extra_key=f"{int(is_brain_clip)}|{round(max_usable_end, 2)}",
    )
    if not isinstance(tel, dict) or not tel.get("ok"):
        return default_s, round(default_span, 4)

    sampled_t = [float(x) for x in tel["sampled_t"]]
    sampled_focal = [float(x) for x in tel["sampled_focal"]]
    sampled_chroma = [float(x) for x in tel["sampled_chroma"]]
    max_clip_focal = max(sampled_focal, default=0.0)
    max_clip_chroma = max(sampled_chroma, default=0.0)
    scores: list[tuple[float, float, float]] = []
    for t_mid, raw_mad, upper, lower in tel["steps"]:
        sc_val = (2.0 * float(upper) + 0.65 * float(lower)) if upward_bias else float(raw_mad)
        scores.append((float(t_mid), sc_val, float(raw_mad)))

    def _focal_at_mid(ws: float, we: float) -> float:
        mid_t = 0.5 * (ws + we)
        best_i = min(range(len(sampled_t)), key=lambda k: abs(sampled_t[k] - mid_t))
        return sampled_focal[best_i]

    def _mean_chroma_in_win(ws: float, we: float) -> float:
        vals = [sampled_chroma[k] for k, t_k in enumerate(sampled_t) if ws - 1e-3 <= t_k <= we + 1e-3]
        return float(np.mean(vals)) if vals else 0.0

    def _window_score(ws: float) -> float:
        we = ws + default_span
        sub = [(v, m) for t_m, v, m in scores if ws <= t_m <= we]
        if not sub:
            return 0.0
        dead_cnt = sum(1 for _, m in sub if m < 0.35)
        penalty = 0.55 ** max(0, dead_cnt - 1)
        mid_focal = _focal_at_mid(ws, we)
        if max_clip_focal >= 0.010 and mid_focal < 0.0045:
            focal_mult = 0.18
        elif mid_focal >= 0.008:
            focal_mult = 1.0 + min(0.35, mid_focal * 6.0)
        else:
            focal_mult = 1.0
        chroma_mult = 1.0
        if is_brain_clip and max_clip_chroma >= 0.015:
            win_ch = _mean_chroma_in_win(ws, we)
            if win_ch < 0.35 * max_clip_chroma:
                chroma_mult = 0.25
            else:
                chroma_mult = 1.0 + 0.65 * (win_ch / max(1e-6, max_clip_chroma))
        return max(0.05 if is_brain_clip else 0.0, float(np.mean([v for v, _ in sub]))) * penalty * focal_mult * chroma_mult

    base_score = _window_score(default_s)
    base_focal = _focal_at_mid(default_s, default_s + default_span)
    base_chroma = _mean_chroma_in_win(default_s, default_s + default_span)
    latest_start = max(default_s, max_usable_end - default_span)
    best_s = default_s
    best_score = base_score
    cand = default_s
    while cand <= latest_start + 1e-6:
        sc_c = _window_score(cand)
        if sc_c > best_score:
            best_score = sc_c
            best_s = cand
        cand += 0.25

    focal_rescue = max_clip_focal >= 0.010 and base_focal < 0.0045 and _focal_at_mid(best_s, best_s + default_span) >= 0.008
    chroma_rescue = (
        is_brain_clip
        and max_clip_chroma >= 0.015
        and base_chroma < 0.35 * max_clip_chroma
        and _mean_chroma_in_win(best_s, best_s + default_span) >= 0.65 * max_clip_chroma
    )
    if focal_rescue or chroma_rescue or best_score >= max(0.75, base_score * 1.12):
        return round(best_s, 4), round(default_span, 4)
    return default_s, round(default_span, 4)


def _normalize_v7_anatomy_badge_text(raw_label: str) -> str:
    """Formats an uppercase 1- or 2-line programmatic ASS anatomical region badge without curly-brace or raw-newline injection."""
    cleaned = (
        str(raw_label or "")
        .replace("{", "")
        .replace("}", "")
        .replace("\r\n", "\\N")
        .replace("\r", "\\N")
        .replace("\n", "\\N")
        .replace("\\n", "\\N")
        .strip()
    )
    if not cleaned:
        return ""
    if "\\N" in cleaned:
        segs = [s.strip().upper() for s in cleaned.split("\\N") if s.strip()]
        return "\\N".join(segs[:2])
    if len(cleaned) > 18:
        for sep in (" · ", " — ", " – ", " | ", " - ", ": "):
            if sep in cleaned:
                left, right = cleaned.split(sep, 1)
                if left.strip() and right.strip():
                    return f"{left.strip().upper()}\\N{right.strip().upper()}"
    return cleaned.upper()


def _resolve_v7_cut_anatomy_label(
    spec: dict[str, Any] | None,
    auto_enabled: bool = True,
) -> tuple[str | None, str | None]:
    """Resolves `(canonical_brain_region, formatted_anatomy_label)` for Schema v7 `porcelain_living_brain` / `lowpoly_matte_brain` clips."""
    if not isinstance(spec, dict):
        return None, None
    grammar = str(spec.get("grammar") or "").strip()
    if grammar not in ("lowpoly_matte_brain", "porcelain_living_brain", "living_brain"):
        return None, None
    from pipeline.anatomy_map import find_regions, plain_name, resolve_region

    raw_reg = str(spec.get("brain_region") or "").strip()
    canon = resolve_region(raw_reg) if raw_reg else None
    if not canon:
        scene_probe = str(spec.get("brain_scene") or spec.get("maquette_scene") or spec.get("scene") or "")
        found = find_regions(scene_probe)
        if found:
            canon = found[0]

    raw_lbl = spec.get("anatomy_label")
    if raw_lbl is False:
        return canon, None
    if isinstance(raw_lbl, str) and raw_lbl.strip():
        return canon, _normalize_v7_anatomy_badge_text(raw_lbl)
    if auto_enabled and canon:
        p_name = plain_name(canon).strip()
        if p_name and p_name.lower() != canon.lower():
            return canon, f"{canon.upper()}\\N{p_name.upper()}"
        return canon, canon.upper()
    return canon, None


def resolve_overlay_window_conflicts(
    resolved_data_stamps: list[dict[str, Any]],
    resolved_anatomy_callouts: list[dict[str, Any]],
    *,
    buffer_sec: float | None = None,
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    """
    R70-M8 / R81 conflict avoidance between R70 HERO Data Stamps and R71/R81 3D Anatomy Leader-Line Callouts:
      - Ensures at least `DATA_STAMP_OVERLAY_BUFFER_SEC` (`2.0s`) separation when sharing the same cut,
        and `DATA_STAMP_CROSS_CUT_BUFFER_SEC` (`0.08s`) across distinct cuts already separated by a hard cut.
      - Shifts/trims the anatomy callout if `>= 1.2s` of non-conflicting duration remains; otherwise suppresses
        the overlapping anatomy callout so R70 HERO graph takes priority.
    """
    from pipeline.config import DATA_STAMP_CROSS_CUT_BUFFER_SEC, DATA_STAMP_OVERLAY_BUFFER_SEC

    buf = float(DATA_STAMP_OVERLAY_BUFFER_SEC if buffer_sec is None else buffer_sec)
    if not resolved_data_stamps or not resolved_anatomy_callouts:
        return list(resolved_anatomy_callouts or []), []

    kept_callouts: list[dict[str, Any]] = []
    conflicts: list[dict[str, Any]] = []
    for ac in resolved_anatomy_callouts:
        if not isinstance(ac, dict):
            continue
        ac0 = float(ac.get("start_sec") or 0.0)
        ac1 = float(ac.get("end_sec") or 0.0)
        ac_cut_s = ac.get("cut_start_sec")
        ac_cut_e = ac.get("cut_end_sec")
        adj0, adj1 = ac0, ac1
        suppressed = False
        for ds in resolved_data_stamps:
            if not isinstance(ds, dict):
                continue
            ds0 = float(ds.get("start_sec") or 0.0)
            ds1 = float(ds.get("end_sec") or 0.0)
            is_distinct_cut = (
                buffer_sec is None
                and ac_cut_s is not None
                and ac_cut_e is not None
                and (ds1 <= float(ac_cut_s) + 0.05 or ds0 >= float(ac_cut_e) - 0.05)
            )
            eff_buf = float(DATA_STAMP_CROSS_CUT_BUFFER_SEC) if is_distinct_cut else buf
            if adj0 < ds1 + eff_buf and adj1 > ds0 - eff_buf:
                # Try keeping tail after ds1 + eff_buf or head before ds0 - eff_buf
                if adj1 - (ds1 + eff_buf) >= 1.2:
                    conflicts.append(
                        {
                            "type": "shifted_after_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "new_span": [round(ds1 + eff_buf, 3), round(adj1, 3)],
                        }
                    )
                    adj0 = ds1 + eff_buf
                elif (ds0 - eff_buf) - adj0 >= 1.2:
                    conflicts.append(
                        {
                            "type": "trimmed_before_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "new_span": [round(adj0, 3), round(ds0 - eff_buf, 3)],
                        }
                    )
                    adj1 = ds0 - eff_buf
                else:
                    conflicts.append(
                        {
                            "type": "suppressed_by_data_stamp",
                            "region": ac.get("canonical_region"),
                            "old_span": [round(adj0, 3), round(adj1, 3)],
                            "stamp_span": [round(ds0, 3), round(ds1, 3)],
                        }
                    )
                    suppressed = True
                    break
        if not suppressed and adj1 - adj0 >= 1.0:
            kept_callouts.append(
                {
                    **ac,
                    "start_sec": round(adj0, 3),
                    "end_sec": round(adj1, 3),
                    "duration_sec": round(adj1 - adj0, 3),
                }
            )
    return kept_callouts, conflicts


def _resolve_diorama_clip_files(visuals_dir: Path) -> list[Path]:
    """Collects `flow_native_clips/clip_*.mp4` and lets `brain_simulator_clips/` + verified `archival_insert_clips/` + verified `archival_video_clips/` override matching indices."""
    from pipeline.archival_insert import load_verified_archival_insert_clip_map
    from pipeline.archival_video import load_verified_archival_video_clip_map

    clips_dir = visuals_dir / "flow_native_clips"
    sim_dir = visuals_dir / "brain_simulator_clips"
    by_name: dict[str, Path] = {}
    if clips_dir.is_dir():
        for f in clips_dir.glob("clip_*.mp4"):
            if f.is_file():
                by_name[f.name] = f
    if sim_dir.is_dir():
        for f in sim_dir.glob("clip_*.mp4"):
            if f.is_file():
                by_name[f.name] = f
    for verified_map in (
        load_verified_archival_insert_clip_map(visuals_dir),
        load_verified_archival_video_clip_map(visuals_dir),
    ):
        for clip_num, entry in sorted(verified_map.items()):
            c_path = Path(str(entry.get("resolved_clip_path") or entry.get("clip_path") or ""))
            if c_path.is_file():
                target_key = f"clip_{clip_num:02d}.mp4"
                unpadded_key = f"clip_{clip_num}.mp4"
                if unpadded_key in by_name and target_key not in by_name:
                    del by_name[unpadded_key]
                by_name[target_key] = c_path
    return sorted(by_name.values(), key=numeric_clip_sort_key)


def enforce_combined_r88a_r89_edl_contract(
    project_dir: str | Path,
    edl: dict[str, Any],
    total_duration_sec: float,
) -> dict[str, Any]:
    """
    Validates R88-A + R89 EDL placement (`cut_index >= 2`, `start >= 2.20s` for R89 video cuts)
    and combined quota (`<= 2` cuts total, `<= 10%` combined duration share).
    """
    p_dir = Path(project_dir)
    v_dir = p_dir / "03_visuals"
    r88_mf = v_dir / "archival_inserts_manifest.json"
    r89_mf = v_dir / "archival_videos_manifest.json"
    if not r88_mf.is_file() and not r89_mf.is_file():
        return {"present": False, "passed": True, "r88a_cuts": [], "r89_cuts": []}

    from pipeline.archival_insert import load_verified_archival_insert_clip_map
    from pipeline.archival_video import (
        load_verified_archival_video_clip_map,
        validate_archival_videos_manifest,
        validate_combined_archival_budget,
    )
    from pipeline.config import R89_MIN_CUT_INDEX, R89_MIN_START_SEC

    if r89_mf.is_file():
        r89_val = validate_archival_videos_manifest(
            p_dir,
            episode_duration_sec=total_duration_sec,
            edl=edl,
            check_faces=False,
            strict_sha256=False,
        )
        if not r89_val["passed"]:
            raise ValueError("R89 archival videos contract failed: " + "; ".join(r89_val["issues"]))

    r88_map = load_verified_archival_insert_clip_map(v_dir)
    r89_map = load_verified_archival_video_clip_map(v_dir)

    r88_used: list[dict[str, Any]] = []
    r89_used: list[dict[str, Any]] = []
    for cut in edl.get("cuts") or []:
        if not isinstance(cut, dict) or cut.get("outro_sky_card"):
            continue
        c_idx = int(cut.get("clip_index") or 0)
        cut_num = int(cut.get("cut_index") or 0)
        start_s = float(cut.get("start") or 0.0)
        end_s = float(cut.get("end") or start_s)
        dur_s = max(0.0, end_s - start_s)
        c_file = str(cut.get("clip_file") or "").replace("\\", "/")

        is_r89 = ("archival_video_clips/" in c_file) or (c_idx in r89_map and "flow_native_clips/" not in c_file)
        is_r88 = ("archival_insert_clips/" in c_file) or (c_idx in r88_map and "flow_native_clips/" not in c_file and not is_r89)
        if is_r89:
            if cut_num < R89_MIN_CUT_INDEX or start_s < R89_MIN_START_SEC - 1e-6:
                raise ValueError(
                    f"[r89_cut_placement_forbidden] cut {cut_num} at start={start_s:.2f}s violates "
                    f"Cut>={R89_MIN_CUT_INDEX} & start>={R89_MIN_START_SEC:.2f}s (118pt HookTitle zone)"
                )
            r89_used.append({"cut_index": cut_num, "clip_index": c_idx, "duration_sec": dur_s})
        elif is_r88:
            r88_used.append({"cut_index": cut_num, "clip_index": c_idx, "duration_sec": dur_s})

    edl_budget_issues = validate_combined_archival_budget(
        len(r88_used),
        sum(x["duration_sec"] for x in r88_used),
        len(r89_used),
        sum(x["duration_sec"] for x in r89_used),
        episode_duration_sec=total_duration_sec,
    )
    if edl_budget_issues:
        raise ValueError("; ".join(edl_budget_issues))

    return {
        "present": True,
        "passed": True,
        "r88a_cuts": r88_used,
        "r89_cuts": r89_used,
    }


def build_v7_dynamic_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
    virtual_clip_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    R63/R66 Schema v7 (`porcelain_cinematic_v7` / `lowpoly_pastel_v7`) 24.0fps Dynamic-Rhythm Zero-Reuse EDL builder:
      - Native `24.0fps` timeline (`<= 4,296 frames` for `<= 179.0s`) at `1.00x` natural motion speed
        (zero `1.26x -> 1.10x` entry speed-ramp knee, zero `24->30fps` pulldown judder).
      - Pairs `0.68-1.35s` rapid multi-beat physical impact sub-cuts with `4.5-7.2s` multi-sentence
        continuous long-take holds (`sentence_index..end_sentence_index`) so `cut_duration_cv >= 0.50`
        while strictly preserving `max_clip_reuse == 1` (`0%` clip reuse).
      - Populates `camera_move` per cut (`1..N`) and top-level camera ratios (`locked_camera_ratio`, `zoom_camera_ratio`).
      - Renders side-by-side comparisons via `split_hstack` (`6px` solid `#000000` vertical divider).
    """
    from pipeline.config import (
        EXPRESSIVE_25D_V8_STYLE_PROFILE,
        EXPRESSIVE_V8_3D_FLIGHT_MOVES,
        EXPRESSIVE_V8_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC,
        EXPRESSIVE_V8_FIRST_CUT_MAX_SEC,
        EXPRESSIVE_V8_FLIGHT_SPEED_RAMP_RANGE,
        EXPRESSIVE_V8_HARD_CEILING_SEC,
        EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN,
        EXPRESSIVE_V8_LONG_TAKE_MAX_SEC,
        EXPRESSIVE_V8_MAX_CUT_SEC,
        EXPRESSIVE_V8_MIN_CUT_SEC,
        EXPRESSIVE_V8_VIDEO_FPS,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        PROMPT_SCHEMA_VERSION_V8,
        SHORTS_90S_CLIP_COUNT_MIN,
        SHORTS_90S_PROFILE,
        SHORTS_EXPRESSIVE_V8_PROFILE,
        resolve_shorts_format_profile,
    )
    from pipeline.depiction_rules import (
        normalize_expressive_v8_grammar,
        normalize_porcelain_v7_grammar,
    )

    from pipeline.config import (
        EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC,
        EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC,
        EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC,
        EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC,
        BRAIN_SIM_ONLY_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE,
        EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC,
        EXPRESSIVE_V8_R76_MAX_CUT_SEC,
        EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC,
        R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE,
        R82_BRAIN_MAX_CUT_SEC,
        R82_BRAIN_MIN_CUT_SEC,
        R82_CLIP_COUNT_RANGE,
        R82_FIRST_15S_MAX_CUT_SEC,
        R82_FIRST_CUT_MAX_SEC,
        R82_HUMAN_MAX_CUT_SEC,
        R82_HUMAN_MIN_CUT_SEC,
        SHORTS_EXPRESSIVE_V8_CUT_COUNT_MIN,
        is_brain_sim_only_plan,
        is_r72_open_world_v8_plan,
        is_r76_v8_plan,
        is_r82_dual_speed_pacing_plan,
    )

    n_sents = len(sentence_spans)
    n_clips = len(clip_files)
    is_v8 = is_expressive_v8_plan(visual_plan, script_doc)
    is_brain_only_edl = is_v8 and is_brain_sim_only_plan(visual_plan, script_doc)
    is_r82_edl = is_v8 and is_r82_dual_speed_pacing_plan(visual_plan, script_doc)
    is_r76_edl = is_v8 and is_r76_v8_plan(visual_plan, script_doc)
    is_r72_edl = is_v8 and is_r72_open_world_v8_plan(visual_plan, script_doc)
    fmt_prof_edl = resolve_shorts_format_profile(visual_plan, script_doc)
    if fmt_prof_edl == MICRO_SHORT_PROFILE:
        min_edl_clips = MICRO_SHORT_CUT_MIN
    elif is_brain_only_edl:
        min_edl_clips = BRAIN_SIM_ONLY_CLIP_COUNT_RANGE[0]
    elif is_r82_edl:
        min_edl_clips = R82_CLIP_COUNT_RANGE[0]
    elif is_r76_edl:
        min_edl_clips = EXPRESSIVE_V8_R76_CLIP_COUNT_RANGE[0]
    elif is_v8 or fmt_prof_edl == SHORTS_EXPRESSIVE_V8_PROFILE:
        if bool(visual_plan.get("allow_legacy_v8_clip_count")):
            min_edl_clips = EXPRESSIVE_V8_LEGACY_CLIP_COUNT_MIN
        elif not is_r72_edl:
            min_edl_clips = min(EXPRESSIVE_V8_LEGACY_INDOOR_CLIP_COUNT_RANGE[0], EXPRESSIVE_V8_CLIP_COUNT_RANGE[0])
        else:
            min_edl_clips = EXPRESSIVE_V8_CLIP_COUNT_RANGE[0]
    else:
        min_edl_clips = DIORAMA_CLIP_COUNT_MIN
    if n_clips < min_edl_clips:
        raise ValueError(
            f"build_v7_dynamic_edl requires >= {min_edl_clips} unique clips (got {n_clips})"
        )
    use_porcelain = (not is_v8) and is_porcelain_v7_plan(visual_plan)
    fps = int(visual_plan.get("fps") or (EXPRESSIVE_V8_VIDEO_FPS if is_v8 else DIORAMA_V7_VIDEO_FPS))
    ceiling_edl_frames = int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps)) if is_v8 else SHORTS_HARD_CEILING_FRAMES_V7
    total_frames = min(ceiling_edl_frames, max(48, int(round(total_duration_sec * fps))))
    if is_v8:
        speech_frames_actual = min(total_frames - 2, max(24, int(round(speech_end_sec * fps))))
        speech_frames = total_frames
        outro_frames = 0
    else:
        min_outro_f = int(math.ceil(PORCELAIN_V7_MIN_CUT_SEC * fps - 1e-9)) if use_porcelain else 24
        speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
        if use_porcelain:
            max_outro_f = int(PORCELAIN_V7_LONG_TAKE_MAX_SEC * fps)
            speech_frames = max(speech_frames, total_frames - max_outro_f)
        speech_frames = max(24, min(total_frames - min_outro_f, speech_frames))
        speech_frames_actual = speech_frames
        outro_frames = max(min_outro_f, total_frames - speech_frames)
    resolved_style = EXPRESSIVE_25D_V8_STYLE_PROFILE if is_v8 else resolve_diorama_v7_style_profile(visual_plan)
    default_grammar = (
        "expressive_story_world"
        if is_v8
        else ("porcelain_fullbleed_world" if use_porcelain else "lowpoly_fullbleed_world")
    )
    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    auto_anat = False if is_v8 else bool(visual_plan.get("auto_anatomy_labels", True))

    def _v7_edl_clip_dur(cf: Path) -> float:
        p_cf = Path(cf)
        if virtual_clip_duration_sec is not None and (not p_cf.is_file() or p_cf.stat().st_size <= 0):
            return max(0.50, float(virtual_clip_duration_sec))
        raw_cd = float(_clip_duration(p_cf))
        return max(0.50, raw_cd) if raw_cd > 0.05 else 4.0

    clip_durs = [_v7_edl_clip_dur(cf) for cf in clip_files]
    clip_specs: dict[int, dict[str, Any]] = {}
    clip_grammars: dict[int, str] = {}
    clip_locations: dict[int, str] = {}
    clip_cameras: dict[int, str] = {}
    clip_brain_regions: dict[int, str | None] = {}
    clip_anatomy_labels: dict[int, str | None] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        g_raw = str(spec.get("grammar") or spec.get("visual_grammar") or default_grammar)
        if is_v8:
            g_norm = normalize_expressive_v8_grammar(g_raw)
        elif use_porcelain:
            g_norm = normalize_porcelain_v7_grammar(g_raw)
        else:
            g_norm = g_raw
        spec_eff = {**spec, "grammar": g_norm} if spec else {"grammar": g_norm}
        clip_specs[idx] = spec_eff
        clip_grammars[idx] = g_norm
        clip_locations[idx] = str(spec.get("location_id") or "").strip()
        clip_cameras[idx] = _resolve_v7_clip_camera(spec_eff, idx)
        b_reg, a_lbl = _resolve_v7_cut_anatomy_label(spec_eff, auto_enabled=auto_anat)
        clip_brain_regions[idx] = b_reg
        clip_anatomy_labels[idx] = None if is_v8 else a_lbl

    # 1. Identify dedicated outro clip (0-based) — suppressed on `expressive_25d_v8` (`0` outro cards)
    outro_clip_idx = n_clips - 1
    if is_v8:
        reserved_clips: set[int] = set()
    else:
        for idx in range(n_clips):
            spec = clip_specs[idx]
            if str(spec.get("cut_role") or "").strip().lower() == "outro":
                outro_clip_idx = idx
                break
        reserved_clips = {outro_clip_idx}

    is_legacy_lowpoly = (not is_v8) and resolve_diorama_v7_style_profile(visual_plan) == DIORAMA_V7_STYLE_PROFILE

    # 2. Parse split_comparisons (supporting explicit left_clip_index/top_clip_index + right_clip_index/bottom_clip_index)
    split_by_sentence: dict[int, dict[str, Any]] = {}
    split_by_left_clip: dict[int, dict[str, Any]] = {}
    raw_splits = visual_plan.get("split_comparisons") if isinstance(visual_plan.get("split_comparisons"), list) else []
    for sc in raw_splits:
        if not isinstance(sc, dict):
            continue
        s_no = int(sc.get("sentence_index") or 0)
        sec_1based = int(sc.get("right_clip_index") or sc.get("bottom_clip_index") or 0)
        sec_idx = sec_1based - 1
        left_1based = int(sc.get("left_clip_index") or sc.get("top_clip_index") or 0)
        if 1 <= s_no <= n_sents and 0 <= sec_idx < n_clips and sec_idx not in reserved_clips:
            split_by_sentence[s_no] = sc
            if 1 <= left_1based <= n_clips and (left_1based - 1) != sec_idx:
                split_by_left_clip[left_1based - 1] = sc
            reserved_clips.add(sec_idx)

    # 3. Map remaining unique primary clips across sentences (supporting multi-sentence holds & explicit sub-beats)
    clips_by_start_sentence: dict[int, list[tuple[int, int, int, float]]] = {s: [] for s in range(1, n_sents + 1)}
    used_primary: set[int] = set()
    for idx in range(n_clips):
        if idx in reserved_clips:
            continue
        spec = clip_specs[idx]
        role = str(spec.get("cut_role") or "").strip().lower()
        if role in ("split_right", "split_bottom") or (not is_v8 and role == "outro"):
            reserved_clips.add(idx)
            continue
        s_no = spec.get("sentence_index")
        if isinstance(s_no, int) and 1 <= s_no <= n_sents:
            hold_cnt = max(1, int(spec.get("hold_sentences") or 1))
            s_end = int(spec.get("end_sentence_index") or (s_no + hold_cnt - 1))
            s_end = max(s_no, min(n_sents, s_end))
            beat_i = int(spec.get("beat_index") or (len(clips_by_start_sentence[s_no]) + 1))
            b_weight = max(0.25, float(spec.get("beat_weight") or 1.0))
            clips_by_start_sentence[s_no].append((beat_i, idx, s_end, b_weight))
            used_primary.add(idx)

    spare_clips = [idx for idx in range(n_clips) if idx not in reserved_clips and idx not in used_primary]
    spare_cursor = 0

    span_by_s = {int(sp["sentence_index"]): sp for sp in sentence_spans}
    s_act = _sentence_act_map(script_doc or {}, n_sents)
    raw_beats: list[dict[str, Any]] = []
    emitted_primary: set[int] = set()
    s_cursor = 1
    while s_cursor <= n_sents:
        assigned = sorted(clips_by_start_sentence.get(s_cursor) or [], key=lambda x: (x[0], x[1]))
        if assigned:
            s_end = max(x[2] for x in assigned)
            # Never orphan an explicitly authored primary clip on an intermediate sentence inside a multi-sentence hold:
            # split the hold cleanly before the next occupied sentence so every authored primary clip gets its own cut.
            if s_end > s_cursor:
                for mid_s in range(s_cursor + 1, s_end + 1):
                    if clips_by_start_sentence.get(mid_s):
                        s_end = mid_s - 1
                        break
            t0 = float(span_by_s[s_cursor]["start_sec"])
            t1 = float(span_by_s[s_end]["end_sec"])
            dur = max(0.35, t1 - t0)
            eff_weights = [float(x[3]) for x in assigned]
            if is_legacy_lowpoly and len(assigned) == 2 and dur >= 2.15:
                w_sum = sum(eff_weights) or 1.0
                r0 = eff_weights[0] / w_sum
                if 0.39 <= r0 <= 0.61:
                    eff_weights = [0.33, 0.67]
            total_w = sum(eff_weights) or float(len(assigned))
            acc_w = 0.0
            for sub_i, ((_, c_idx, _, _), bw) in enumerate(zip(assigned, eff_weights)):
                b0 = t0 + dur * (acc_w / total_w)
                acc_w += bw
                b1 = t0 + dur * (acc_w / total_w)
                emitted_primary.add(c_idx)
                raw_beats.append(
                    {
                        "act": s_act.get(s_cursor, 1),
                        "sentence_index": s_cursor,
                        "end_sentence_index": s_end,
                        "sub_beat": sub_i,
                        "clip_idx": c_idx,
                        "t0": b0,
                        "t1": b1,
                    }
                )
            s_cursor = s_end + 1
        else:
            # Recycle any previously un-emitted primary clip before drawing from spare_clips
            if spare_cursor >= len(spare_clips):
                recycled = [
                    idx_r
                    for s_prev in range(1, s_cursor)
                    for _, idx_r, _, _ in sorted(clips_by_start_sentence.get(s_prev) or [], key=lambda x: (x[0], x[1]))
                    if idx_r not in emitted_primary and idx_r not in spare_clips
                ]
                if recycled:
                    spare_clips.extend(recycled)
            if spare_cursor < len(spare_clips):
                chosen_idx = spare_clips[spare_cursor]
                spare_cursor += 1
                used_primary.add(chosen_idx)
                emitted_primary.add(chosen_idx)
                sp = span_by_s[s_cursor]
                raw_beats.append(
                    {
                        "act": s_act.get(s_cursor, 1),
                        "sentence_index": s_cursor,
                        "end_sentence_index": s_cursor,
                        "sub_beat": 0,
                        "clip_idx": chosen_idx,
                        "t0": float(sp["start_sec"]),
                        "t1": float(sp["end_sec"]),
                    }
                )
                s_cursor += 1
            elif raw_beats:
                # Extend preceding hold to cover uncovered sentence if clip count is compact
                raw_beats[-1]["end_sentence_index"] = s_cursor
                raw_beats[-1]["t1"] = float(span_by_s[s_cursor]["end_sec"])
                s_cursor += 1
            else:
                raise ValueError(f"build_v7_dynamic_edl has zero usable primary clips at sentence {s_cursor}")

    # Consume any remaining unused spare clips on R72 fast-cut timelines by splitting the longest single-clip beats
    # Rule R76-P forbids mid-sentence spare-clip splitting to eliminate chaotic ADHD flicker.
    while is_r72_edl and (not is_r76_edl) and spare_cursor < len(spare_clips) and raw_beats:
        longest_i = max(
            range(len(raw_beats)),
            key=lambda bi: (
                float(raw_beats[bi]["t1"]) - float(raw_beats[bi]["t0"])
                if "brain" not in str(clip_grammars.get(int(raw_beats[bi]["clip_idx"])) or "")
                and not bool(clip_specs.get(int(raw_beats[bi]["clip_idx"]), {}).get("cameo_easter_egg"))
                else -1.0
            ),
        )
        b_long = raw_beats[longest_i]
        span_l = float(b_long["t1"]) - float(b_long["t0"])
        if span_l < 2.40:
            break
        nxt_spare = spare_clips[spare_cursor]
        spare_cursor += 1
        used_primary.add(nxt_spare)
        emitted_primary.add(nxt_spare)
        mid_t_l = 0.5 * (float(b_long["t0"]) + float(b_long["t1"]))
        raw_beats[longest_i : longest_i + 1] = [
            {**b_long, "sub_beat": int(b_long.get("sub_beat") or 0), "t1": mid_t_l},
            {**b_long, "sub_beat": int(b_long.get("sub_beat") or 0) + 1, "clip_idx": nxt_spare, "t0": mid_t_l},
        ]

    if is_v8:
        if is_r82_edl:
            eff_min_cut_sec = R82_HUMAN_MIN_CUT_SEC
            eff_mid_act_max_sec = R82_BRAIN_MAX_CUT_SEC
            eff_long_take_max_sec = R82_BRAIN_MAX_CUT_SEC
        elif is_r76_edl:
            eff_min_cut_sec = EXPRESSIVE_V8_R76_HUMAN_MIN_CUT_SEC
            eff_mid_act_max_sec = EXPRESSIVE_V8_R76_MAX_CUT_SEC
            eff_long_take_max_sec = EXPRESSIVE_V8_R76_MAX_CUT_SEC
        else:
            eff_min_cut_sec = EXPRESSIVE_V8_MIN_CUT_SEC
            eff_mid_act_max_sec = EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_MAX_CUT_SEC
            eff_long_take_max_sec = EXPRESSIVE_V8_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_LONG_TAKE_MAX_SEC
    else:
        eff_min_cut_sec = DIORAMA_V7_RAPID_CUT_MIN_SEC if is_legacy_lowpoly else PORCELAIN_V7_MIN_CUT_SEC
        eff_mid_act_max_sec = DIORAMA_V7_MID_ACT_MAX_CUT_SEC if is_legacy_lowpoly else PORCELAIN_V7_MID_ACT_MAX_CUT_SEC
        eff_long_take_max_sec = DIORAMA_V7_LONG_TAKE_MAX_SEC if is_legacy_lowpoly else PORCELAIN_V7_LONG_TAKE_MAX_SEC

    def _compute_v7_boundaries_and_cv(beats_in: list[dict[str, Any]]) -> tuple[list[int], float]:
        nb_loc = len(beats_in)
        raw_min_cf = (
            int(round(eff_min_cut_sec * fps))
            if is_legacy_lowpoly
            else int(math.ceil(eff_min_cut_sec * fps - 1e-9))
        )
        min_slack_ratio = 0.80 if is_legacy_lowpoly else 0.96
        min_cf = min(
            raw_min_cf,
            max(10, int(speech_frames * min_slack_ratio) // max(1, nb_loc)),
        )
        max_cf = max(min_cf + 1, int(eff_long_take_max_sec * fps))
        max_ss_cf = max(min_cf + 1, int(eff_mid_act_max_sec * fps))
        r82_human_cap_cf = max(min_cf + 1, int(math.floor(R82_HUMAN_MAX_CUT_SEC * fps)))
        r82_brain_cap_cf = max(min_cf + 1, int(math.floor(R82_BRAIN_MAX_CUT_SEC * fps)))
        is_brain_beat_cap = [
            str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") == "brain_simulator_3d"
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("brain_clip"))
            for b in beats_in
        ]
        caps_loc = [
            (r82_brain_cap_cf if is_b_c else r82_human_cap_cf)
            if is_r82_edl
            else (
                max_ss_cf
                if int(b.get("end_sentence_index") or b.get("sentence_index") or 0) == int(b.get("sentence_index") or 0)
                else max_cf
            )
            for b, is_b_c in zip(beats_in, is_brain_beat_cap)
        ]
        if is_v8 and nb_loc > 0 and not bool(visual_plan.get("allow_legacy_v8_clip_count")):
            from pipeline.config import R87_FIRST_CUT_MAX_SEC, is_r87_plan as _is_r87_edl_fn

            is_r87_edl = _is_r87_edl_fn(visual_plan, None)
            eff_first_cap_s = (
                R87_FIRST_CUT_MAX_SEC
                if is_r87_edl
                else (
                    R82_FIRST_CUT_MAX_SEC
                    if is_r82_edl
                    else (
                        5.20
                        if is_r76_edl
                        else (EXPRESSIVE_V8_FIRST_CUT_MAX_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_FIRST_CUT_MAX_SEC)
                    )
                )
            )
            eff_f15_cap_s = (
                R82_FIRST_15S_MAX_CUT_SEC
                if is_r82_edl
                else (
                    5.80
                    if is_r76_edl
                    else (EXPRESSIVE_V8_FIRST_15S_MAX_CUT_SEC if is_r72_edl else EXPRESSIVE_V8_LEGACY_FIRST_15S_MAX_CUT_SEC)
                )
            )
            first_cap_cf = max(min_cf, int(round(eff_first_cap_s * fps)))
            first_15_cap_cf = max(min_cf + 1, int(round(eff_f15_cap_s * fps)))
            cand_caps = list(caps_loc)
            cand_caps[0] = min(cand_caps[0], first_cap_cf)
            for idx_cap in range(1, nb_loc):
                if float(beats_in[idx_cap].get("t0") or 0.0) < 15.0:
                    cand_caps[idx_cap] = min(cand_caps[idx_cap], first_15_cap_cf)
            if sum(cand_caps) >= speech_frames:
                caps_loc = cand_caps
            elif (cand_caps[0] + sum(caps_loc[1:])) >= speech_frames:
                caps_loc[0] = cand_caps[0]
        if nb_loc > 0 and sum(caps_loc) < speech_frames <= nb_loc * max_cf:
            caps_loc = [max_cf] * nb_loc
        bnds = [0]
        ref_end_sec = max(0.1, total_duration_sec if is_v8 else speech_end_sec)
        spatial_min_cf = min(
            min_cf,
            max(10, int(math.ceil(EXPRESSIVE_V8_SPATIAL_RELAY_MIN_CUT_SEC * fps - 1e-9))),
        )
        is_spatial_relay_beat = [
            str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") in ("spatial_3d_arrow_diorama", "expressive_split_contrast")
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("spatial_relay_cut"))
            or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("non_spatial_contrast_cut"))
            for b in beats_in
        ]
        init_mins_loc = [
            spatial_min_cf if (is_r76_edl and is_sp_b) else min_cf
            for is_sp_b in is_spatial_relay_beat
        ]
        for i_b in range(1, nb_loc):
            ideal_t = float(beats_in[i_b]["t0"])
            f_idx = int(round((ideal_t / ref_end_sec) * speech_frames))
            min_f = bnds[-1] + init_mins_loc[i_b - 1]
            max_f = speech_frames - sum(init_mins_loc[i_b:])
            bnds.append(max(min_f, min(max_f, f_idx)))
        bnds.append(speech_frames)
        if nb_loc > 0 and speech_frames <= sum(caps_loc):
            lens = [bnds[i_b + 1] - bnds[i_b] for i_b in range(nb_loc)]
            for i_b in range(nb_loc):
                while lens[i_b] > caps_loc[i_b]:
                    best_j = -1
                    for dist in range(1, nb_loc):
                        cand_js = [
                            j_c
                            for j_c in (i_b + dist, i_b - dist)
                            if 0 <= j_c < nb_loc and lens[j_c] < caps_loc[j_c]
                        ]
                        if cand_js:
                            best_j = max(cand_js, key=lambda j_c: caps_loc[j_c] - lens[j_c])
                            break
                    if best_j < 0:
                        break
                    take = min(lens[i_b] - caps_loc[i_b], caps_loc[best_j] - lens[best_j])
                    lens[i_b] -= take
                    lens[best_j] += take
            bnds = [0]
            for ln_f in lens:
                bnds.append(bnds[-1] + ln_f)
        if is_r76_edl and nb_loc > 1:
            eff_b_min_s = R82_BRAIN_MIN_CUT_SEC if is_r82_edl else EXPRESSIVE_V8_R76_BRAIN_SIM_MIN_CUT_SEC
            brain_min_cf = max(min_cf, int(math.ceil((eff_b_min_s + 0.02) * fps - 1e-9)))
            is_brain_beat = [
                str(clip_grammars.get(int(b.get("clip_idx") or 0)) or "") == "brain_simulator_3d"
                or bool(clip_specs.get(int(b.get("clip_idx") or 0), {}).get("brain_clip"))
                for b in beats_in
            ]
            mins_loc = [
                brain_min_cf if is_b else (min_cf if is_r82_edl else (spatial_min_cf if is_sp_b else min_cf))
                for is_b, is_sp_b in zip(is_brain_beat, is_spatial_relay_beat)
            ]
            if sum(mins_loc) <= speech_frames:
                lens_r76 = [bnds[i_b + 1] - bnds[i_b] for i_b in range(nb_loc)]
                for i_b in range(nb_loc):
                    while lens_r76[i_b] < mins_loc[i_b]:
                        best_j = -1
                        for same_dom in (True, False):
                            for dist in range(1, nb_loc):
                                cand_js = [
                                    j_c
                                    for j_c in (i_b + dist, i_b - dist)
                                    if 0 <= j_c < nb_loc
                                    and lens_r76[j_c] > mins_loc[j_c]
                                    and ((is_brain_beat[j_c] == is_brain_beat[i_b]) if same_dom else True)
                                ]
                                if cand_js:
                                    best_j = max(cand_js, key=lambda j_c: lens_r76[j_c] - mins_loc[j_c])
                                    break
                            if best_j >= 0:
                                break
                        if best_j < 0:
                            break
                        give = min(mins_loc[i_b] - lens_r76[i_b], lens_r76[best_j] - mins_loc[best_j])
                        lens_r76[i_b] += give
                        lens_r76[best_j] -= give
                bnds = [0]
                for ln_f in lens_r76:
                    bnds.append(bnds[-1] + ln_f)
        all_durs_loc = [max(10, bnds[i_b + 1] - bnds[i_b]) / float(fps) for i_b in range(nb_loc)]
        if not is_v8:
            all_durs_loc.append(outro_frames / float(fps))
        cv_loc = float(np.std(all_durs_loc) / max(1e-6, np.mean(all_durs_loc))) if all_durs_loc else 0.0
        return bnds, cv_loc

    def _is_swappable_room_beat(b_item: dict[str, Any]) -> bool:
        s0 = int(b_item.get("sentence_index") or 0)
        s1 = int(b_item.get("end_sentence_index") or s0)
        if s0 < 4 or s0 != s1 or int(b_item.get("sub_beat") or 0) != 0:
            return False
        if s0 in split_by_sentence:
            return False
        c_i = int(b_item.get("clip_idx") or 0)
        gm = str(clip_grammars.get(c_i) or "")
        if (
            "brain" in gm
            or "analogy" in gm
            or gm in ("spatial_3d_arrow_diorama", "expressive_split_contrast")
            or bool(clip_specs.get(c_i, {}).get("spatial_relay_cut"))
            or bool(clip_specs.get(c_i, {}).get("non_spatial_contrast_cut"))
            or clip_anatomy_labels.get(c_i)
        ):
            return False
        return True

    boundaries, cur_cv = _compute_v7_boundaries_and_cv(raw_beats)
    if is_legacy_lowpoly:
        target_cv_floor = 0.385
        if cur_cv < target_cv_floor and len(raw_beats) >= 50:
            min_split_dur = 2.54
            max_hold_dur = 6.15
            for _swap_round in range(5):
                if cur_cv >= target_cv_floor:
                    break
                merge_cands: list[tuple[float, int]] = []
                for k_idx in range(len(raw_beats) - 1):
                    ba, bb = raw_beats[k_idx], raw_beats[k_idx + 1]
                    if not (_is_swappable_room_beat(ba) and _is_swappable_room_beat(bb)):
                        continue
                    if int(ba.get("act") or 0) != int(bb.get("act") or 0):
                        continue
                    comb_d = float(bb["t1"]) - float(ba["t0"])
                    if 3.60 <= comb_d <= max_hold_dur and clip_durs[int(ba["clip_idx"])] >= comb_d + 0.35:
                        merge_cands.append((comb_d, k_idx))
                if not merge_cands:
                    break
                merge_cands.sort(reverse=True)
                best_merge_k = merge_cands[0][1]
                freed_clip = int(raw_beats[best_merge_k + 1]["clip_idx"])

                split_cands: list[tuple[float, int]] = []
                for m_idx, bm in enumerate(raw_beats):
                    if m_idx in (best_merge_k, best_merge_k + 1) or not _is_swappable_room_beat(bm):
                        continue
                    m_d = float(bm["t1"]) - float(bm["t0"])
                    if m_d >= min_split_dur:
                        split_cands.append((-abs(m_d - 2.65), m_idx))
                if not split_cands:
                    break
                split_cands.sort(reverse=True)
                best_split_m = split_cands[0][1]

                cand_beats: list[dict[str, Any]] = []
                idx_it = 0
                while idx_it < len(raw_beats):
                    if idx_it == best_merge_k:
                        ba = raw_beats[idx_it]
                        bb = raw_beats[idx_it + 1]
                        cand_beats.append(
                            {
                                **ba,
                                "end_sentence_index": int(bb["end_sentence_index"]),
                                "t1": float(bb["t1"]),
                            }
                        )
                        idx_it += 2
                    elif idx_it == best_split_m:
                        bm = raw_beats[idx_it]
                        mt0 = float(bm["t0"])
                        mt1 = float(bm["t1"])
                        mmid = mt0 + 0.30 * (mt1 - mt0)
                        cand_beats.append({**bm, "sub_beat": 0, "t0": mt0, "t1": mmid})
                        cand_beats.append({**bm, "sub_beat": 1, "clip_idx": freed_clip, "t0": mmid, "t1": mt1})
                        idx_it += 1
                    else:
                        cand_beats.append(dict(raw_beats[idx_it]))
                        idx_it += 1
                cand_bnds, cand_cv = _compute_v7_boundaries_and_cv(cand_beats)
                if cand_cv <= cur_cv:
                    break
                raw_beats = cand_beats
                boundaries = cand_bnds
                cur_cv = cand_cv

    n_b = len(raw_beats)
    from pipeline.config import (
        EXPRESSIVE_V8_DRONE_CAMERA_MOVES,
        R79M_HUMAN_CUT_MAX_MAIN_SPEED,
        is_r79m_character_motion_plan,
    )

    is_r79m_edl = bool(is_v8 and is_r79m_character_motion_plan(visual_plan, script_doc))

    cuts: list[dict[str, Any]] = []
    for cut_i in range(n_b):
        f0, f1 = boundaries[cut_i], boundaries[cut_i + 1]
        c_frames = max(10, f1 - f0)
        out_dur = c_frames / float(fps)
        beat = raw_beats[cut_i]
        act_no = int(beat["act"])
        s_idx = int(beat["sentence_index"])
        s_end = int(beat["end_sentence_index"])
        chosen = int(beat["clip_idx"])
        c_spec_raw = clip_specs.get(chosen) or {}
        is_r79m_human_cut = bool(
            is_r79m_edl
            and str(clip_grammars.get(chosen, default_grammar)) != "brain_simulator_3d"
            and str(c_spec_raw.get("render_engine") or "") != "blender_3d_simulator"
            and str(clip_cameras.get(chosen, "")) not in EXPRESSIVE_V8_DRONE_CAMERA_MOVES
        )

        split_sc = None
        if chosen in split_by_left_clip:
            split_sc = split_by_left_clip[chosen]
        elif beat["sub_beat"] == 0:
            for s_chk in range(s_idx, s_end + 1):
                if s_chk in split_by_sentence:
                    cand_sc = split_by_sentence[s_chk]
                    exp_left = int(cand_sc.get("left_clip_index") or cand_sc.get("top_clip_index") or 0)
                    if exp_left <= 0 or exp_left == chosen + 1:
                        split_sc = cand_sc
                        break

        def _override_start_for_1based(clip_1based: int) -> float | None:
            if not isinstance(source_window_overrides, dict):
                return None
            val = source_window_overrides.get(clip_1based)
            if val is None:
                val = source_window_overrides.get(str(clip_1based))  # type: ignore[arg-type]
            if isinstance(val, (list, tuple)) and len(val) >= 1:
                return float(val[0])
            if isinstance(val, (int, float)):
                return float(val)
            return None

        def _override_end_for_1based(clip_1based: int) -> float | None:
            if not isinstance(source_window_overrides, dict):
                return None
            val = source_window_overrides.get(clip_1based)
            if val is None:
                val = source_window_overrides.get(str(clip_1based))  # type: ignore[arg-type]
            if isinstance(val, (list, tuple)) and len(val) >= 2 and val[1] is not None:
                return float(val[1])
            return None

        spec_for_win = {**c_spec_raw, "_r79m_snappy_human": True} if is_r79m_human_cut else clip_specs.get(chosen)
        src_s, src_span = _select_v7_source_window(
            Path(clip_files[chosen]),
            clip_durs[chosen],
            out_dur,
            spec_for_win,
            override_src_start_sec=_override_start_for_1based(chosen + 1),
            override_src_end_sec=_override_end_for_1based(chosen + 1),
        )
        src_e = round(src_s + src_span, 4)

        mode = "single"
        secondary_clip_idx = None
        secondary_src = None
        secondary_cam = None
        split_labels = None
        if split_sc is not None:
            sec_1based = int(split_sc.get("right_clip_index") or split_sc.get("bottom_clip_index") or 0)
            sec_idx = sec_1based - 1
            s2_s, s2_span = _select_v7_source_window(
                Path(clip_files[sec_idx]),
                clip_durs[sec_idx],
                out_dur,
                clip_specs.get(sec_idx),
                override_src_start_sec=_override_start_for_1based(sec_1based),
                override_src_end_sec=_override_end_for_1based(sec_1based),
            )
            mode = str(split_sc.get("mode") or DIORAMA_V7_SPLIT_MODE).strip()
            if mode not in ("split_hstack", "split_vstack"):
                mode = "split_hstack"
            secondary_clip_idx = sec_idx
            secondary_src = [round(s2_s, 4), round(s2_s + s2_span, 4)]
            secondary_cam = clip_cameras.get(sec_idx, "locked_tripod")
            split_labels = [
                str(split_sc.get("left_label") or split_sc.get("top_label") or "EXPECTED"),
                str(split_sc.get("right_label") or split_sc.get("bottom_label") or "ACTUAL"),
            ]

        c_spec_cur = clip_specs.get(chosen) or {}
        cut_row: dict[str, Any] = {
            "cut_index": cut_i + 1,
            "act": act_no,
            "sentence_index": s_idx,
            "end_sentence_index": s_end,
            "sentence_span": [s_idx, s_end],
            "mode": mode,
            "out_start_sec": round(f0 / float(fps), 4),
            "out_end_sec": round(f1 / float(fps), 4),
            "frames": c_frames,
            "duration_sec": round(out_dur, 4),
            "clip_index": chosen + 1,
            "clip_file": clip_files[chosen].name,
            "grammar": clip_grammars.get(chosen, default_grammar),
            "camera_move": clip_cameras.get(chosen, "locked_tripod"),
            "location_id": clip_locations.get(chosen, ""),
            "brain_region": clip_brain_regions.get(chosen),
            "anatomy_label": (None if is_v8 else (clip_anatomy_labels.get(chosen) if mode == "single" else None)),
            "src_start_sec": round(src_s, 4),
            "src_end_sec": src_e,
            "forbid_slowmo_stretch": bool(c_spec_cur.get("forbid_slowmo_stretch")),
            "allow_slowmo_stretch": bool(c_spec_cur.get("allow_slowmo_stretch")),
            "speed_ramp": False,
            "main_speed": round(src_span / max(0.1, out_dur), 4),
            "crop_zoom": round(max(1.0, min(1.30, float(c_spec_cur.get("crop_zoom") or 1.00))), 4),
            "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
            "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
            "secondary_camera_move": secondary_cam,
            "secondary_src_span": secondary_src,
            "split_labels": split_labels,
            "outro_sky_card": False,
        }
        if is_v8:
            from pipeline.config import EXPRESSIVE_V8_TRANSITION_TYPES

            raw_tr = str(c_spec_cur.get("transition_out") or c_spec_cur.get("transition_to_next") or "").strip().lower()
            if raw_tr == "dissolve_6f":
                eff_tr = "dissolve_6f" if (cut_i < n_b - 1 and mode == "single") else "action_impact_cut"
            elif raw_tr in EXPRESSIVE_V8_TRANSITION_TYPES:
                eff_tr = raw_tr
            else:
                eff_tr = "hard"
            cut_row["transition_out"] = eff_tr
            cut_row["transition_to_next"] = eff_tr
            cut_row["cameo_easter_egg"] = bool(c_spec_cur.get("cameo_easter_egg"))
            if c_spec_cur.get("end_reference_image"):
                cut_row["end_reference_image"] = str(c_spec_cur["end_reference_image"])
            is_flight_span = bool(
                c_spec_cur.get("end_reference_image")
                or c_spec_cur.get("full_trajectory_span")
                or clip_cameras.get(chosen, "") in EXPRESSIVE_V8_3D_FLIGHT_MOVES
            )
            cut_row["is_3d_flight"] = is_flight_span
            is_r80_spatial = bool(
                str(cut_row.get("grammar") or "") == "spatial_3d_arrow_diorama"
                or c_spec_cur.get("spatial_relay_cut")
            )
            if is_r80_spatial:
                cut_row["spatial_relay_cut"] = True
                if c_spec_cur.get("arrow_3d_mode"):
                    cut_row["arrow_3d_mode"] = str(c_spec_cur.get("arrow_3d_mode")).strip()
            if is_flight_span and (c_spec_cur.get("flight_speed_ramp") is not None or is_r80_spatial):
                raw_rv = c_spec_cur.get("flight_speed_ramp")
                ramp_v = float(raw_rv) if raw_rv is not None else 1.32
                if is_r80_spatial:
                    lo_r, hi_r = R80_SPATIAL_FLIGHT_SPEED_RAMP_RANGE
                elif is_r82_edl or is_r76_edl or (raw_rv is not None and float(raw_rv) < 2.0):
                    lo_r, hi_r = (1.05, float(R79M_HUMAN_CUT_MAX_MAIN_SPEED))
                else:
                    lo_r, hi_r = EXPRESSIVE_V8_FLIGHT_SPEED_RAMP_RANGE
                ramp_v = max(lo_r, min(hi_r, ramp_v))
                max_avail_span = max(0.50, clip_durs[chosen] - 0.08 - src_s)
                ramped_span = min(max_avail_span, out_dur * ramp_v)
                cut_row["src_end_sec"] = round(src_s + ramped_span, 4)
                cut_row["main_speed"] = round(ramped_span / max(0.1, out_dur), 4)
                cut_row["flight_speed_ramp"] = round(ramped_span / max(0.1, out_dur), 3)
            elif is_flight_span:
                cut_row["flight_speed_ramp"] = round(float(cut_row["main_speed"]), 3)
            cur_src_span = float(cut_row["src_end_sec"]) - float(cut_row["src_start_sec"])
            is_sim_cut = (
                str(cut_row.get("grammar") or "") == "brain_simulator_3d"
                or str(c_spec_cur.get("render_engine") or "") == "blender_3d_simulator"
            )
            if (
                not is_sim_cut
                and not bool(cut_row.get("allow_slowmo_stretch"))
                and float(clip_durs[chosen]) >= out_dur + 0.08
                and cur_src_span < out_dur - 0.02
            ):
                safe_clip_end = float(clip_durs[chosen]) - 0.04
                new_s0 = max(0.06, min(float(cut_row["src_start_sec"]), safe_clip_end - out_dur))
                new_s1 = min(safe_clip_end, new_s0 + out_dur)
                cut_row["src_start_sec"] = round(new_s0, 4)
                cut_row["src_end_sec"] = round(new_s1, 4)
                cut_row["main_speed"] = round((new_s1 - new_s0) / max(0.1, out_dur), 4)
            is_r82_non_brain_cut = bool(is_r82_edl and not is_sim_cut)
            if (is_r79m_human_cut or is_r82_non_brain_cut) and float(cut_row["main_speed"]) > float(R79M_HUMAN_CUT_MAX_MAIN_SPEED) + 1e-4:
                clamped_span = round(out_dur * float(R79M_HUMAN_CUT_MAX_MAIN_SPEED), 4)
                cut_row["src_end_sec"] = round(float(cut_row["src_start_sec"]) + clamped_span, 4)
                cut_row["main_speed"] = round(clamped_span / max(0.1, out_dur), 4)
                if "flight_speed_ramp" in cut_row:
                    cut_row["flight_speed_ramp"] = round(float(cut_row["main_speed"]), 3)
            if (
                bool(getattr(_cfg, "EXPRESSIVE_V8_CURVE_RAMP", False) or c_spec_cur.get("force_curve_ramp"))
                and mode == "single"
                and bool(c_spec_cur.get("end_reference_image") or c_spec_cur.get("full_trajectory_span"))
                and (float(cut_row["src_end_sec"]) - float(cut_row["src_start_sec"])) / max(0.1, out_dur) >= 1.28
                and out_dur >= 1.10
            ):
                cut_row["v8_curve_ramp"] = True
            cut_row["diegetic_text_allowlist"] = [
                str(x).strip() for x in (c_spec_cur.get("diegetic_text_allowlist") or []) if str(x).strip()
            ]
            cut_row["lighting_mode"] = str(c_spec_cur.get("lighting_mode") or "daylight_studio")
            if c_spec_cur.get("foley_cue"):
                cut_row["foley_cue"] = str(c_spec_cur["foley_cue"])
            for r74b_k in ("render_engine", "start_brain_region", "end_brain_region", "neural_state", "start_neural_state", "callout_mode", "callout_gloss"):
                if c_spec_cur.get(r74b_k) is not None and str(c_spec_cur.get(r74b_k)).strip():
                    cut_row[r74b_k] = str(c_spec_cur[r74b_k]).strip()
            if isinstance(c_spec_cur.get("r78m_callout"), dict):
                cut_row["r78m_callout"] = dict(c_spec_cur["r78m_callout"])
            if "callout_enabled" in c_spec_cur:
                cut_row["callout_enabled"] = c_spec_cur["callout_enabled"]
            if "anatomy_label" in c_spec_cur:
                cut_row["anatomy_label"] = c_spec_cur["anatomy_label"]
            if c_spec_cur.get("single_start_frame_lock"):
                cut_row["single_start_frame_lock"] = True
            for r82_k in ("human_action_relay", "r72_cold_open_relay", "side_by_side_brain_compare", "stacked_cutaway_brain_compare", "dashed_baseline"):
                if c_spec_cur.get(r82_k):
                    cut_row[r82_k] = True
            if c_spec_cur.get("surgical_cutaway") is not None:
                cut_row["surgical_cutaway"] = bool(c_spec_cur["surgical_cutaway"])
            if c_spec_cur.get("morph_mode"):
                cut_row["morph_mode"] = str(c_spec_cur["morph_mode"]).strip()
            if c_spec_cur.get("stacked_cutaway_brain_compare") and not cut_row.get("secondary_clip_index"):
                cut_row["mode"] = "split_vstack"
        cuts.append(cut_row)

    # Append dedicated final Act 6 Sky Tilt-Up Outro Card cut ONLY for Schema v7 (suppressed on Schema v8)
    if not is_v8:
        outro_dur = outro_frames / float(fps)
        outro_s = 0.12
        outro_avail = max(0.50, (clip_durs[outro_clip_idx] - 0.08) - outro_s)
        outro_span = outro_dur if outro_avail >= outro_dur else outro_avail
        outro_e = round(outro_s + outro_span, 4)
        cuts.append(
            {
                "cut_index": len(cuts) + 1,
                "act": DIORAMA_ACT_COUNT,
                "sentence_index": n_sents,
                "end_sentence_index": n_sents,
                "sentence_span": [n_sents, n_sents],
                "mode": "single",
                "out_start_sec": round(speech_frames / float(fps), 4),
                "out_end_sec": round(total_frames / float(fps), 4),
                "frames": outro_frames,
                "duration_sec": round(outro_dur, 4),
                "clip_index": outro_clip_idx + 1,
                "clip_file": clip_files[outro_clip_idx].name,
                "grammar": clip_grammars.get(outro_clip_idx, default_grammar),
                "camera_move": clip_cameras.get(outro_clip_idx, "tilt_up"),
                "location_id": clip_locations.get(outro_clip_idx, ""),
                "brain_region": None,
                "anatomy_label": None,
                "src_start_sec": outro_s,
                "src_end_sec": outro_e,
                "speed_ramp": False,
                "main_speed": round(outro_span / max(0.1, outro_dur), 4),
                "crop_zoom": 1.00,
                "secondary_clip_index": None,
                "secondary_clip_file": None,
                "secondary_camera_move": None,
                "secondary_src_span": None,
                "split_labels": None,
                "outro_sky_card": True,
            }
        )

    max_reuse = _compute_max_clip_reuse(cuts)
    if bool(visual_plan.get("zero_clip_reuse", True)) and max_reuse > DIORAMA_MAX_CLIP_REUSE:
        raise RuntimeError(
            f"build_v7_dynamic_edl violated zero-reuse lock: max_clip_reuse={max_reuse} > {DIORAMA_MAX_CLIP_REUSE}"
        )

    cut_durs = [float(c["duration_sec"]) for c in cuts]
    mean_cut = float(np.mean(cut_durs)) if cut_durs else 0.0
    std_cut = float(np.std(cut_durs)) if cut_durs else 0.0
    cut_cv = round(std_cut / max(1e-6, mean_cut), 4)
    rapid_ratio = round(sum(1 for d in cut_durs if d <= 1.50) / max(1, len(cut_durs)), 4)

    cam_counts: dict[str, int] = {m: 0 for m in DIORAMA_V7_CAMERA_MOVES}
    for c in cuts:
        cm = str(c.get("camera_move") or "locked_tripod")
        cam_counts[cm] = cam_counts.get(cm, 0) + 1
    n_c_tot = max(1, len(cuts))
    locked_cam_ratio = round(cam_counts.get("locked_tripod", 0) / float(n_c_tot), 4)
    zoom_cam_ratio = round(
        (cam_counts.get("gentle_push_in", 0) + cam_counts.get("clean_pullback_reveal", 0)) / float(n_c_tot),
        4,
    )

    # Count A-B-A spatial location returns (same location_id returning after >=1 different location)
    seen_locs: dict[str, int] = {}
    aba_returns = 0
    for idx_c, c in enumerate(cuts):
        loc = str(c.get("location_id") or "").strip()
        if not loc:
            continue
        if loc in seen_locs and idx_c - seen_locs[loc] >= 2:
            aba_returns += 1
        seen_locs[loc] = idx_c

    from pipeline.anatomy_overlay import resolve_anatomy_callout_windows
    from pipeline.stamp_overlay import resolve_data_stamp_windows

    allow_v8_alpha_dissolves = bool((visual_plan or {}).get("allow_alpha_dissolves"))
    if is_v8 and not allow_v8_alpha_dissolves:
        _alpha_fade_names = {
            "dissolve_6f",
            "dissolve_8f",
            "dissolve_12f",
            "dissolve_15f",
            "match_cut_bridge",
            "split_screen_wipe",
            "daisy_chain_bridge",
        }
        for c in cuts:
            if str(c.get("transition_out") or "").strip().lower() in _alpha_fade_names:
                c["transition_out"] = "action_impact_cut"
                c["transition_to_next"] = "action_impact_cut"

    resolved_data_stamps = resolve_data_stamp_windows(
        script_doc,
        sentence_spans,
        round(total_frames / float(fps), 3),
    )
    if is_v8 and resolved_data_stamps and cuts:
        for ds in resolved_data_stamps:
            ds_s_idx = int(ds.get("sentence_index") or 0)
            ds_e_idx = int(ds.get("end_sentence_index") or ds_s_idx)
            matching_cuts = [
                c_it
                for c_it in cuts
                if int(c_it.get("sentence_index") or 0) <= ds_e_idx
                and int(c_it.get("end_sentence_index") or c_it.get("sentence_index") or 0) >= ds_s_idx
            ]
            if matching_cuts:
                c_bound_s = float(matching_cuts[0].get("out_start_sec") or 0.0)
                c_bound_e = float(matching_cuts[-1].get("out_end_sec") or 0.0)
                ds_t0 = float(ds.get("start_sec") or 0.0)
                ds_t1 = float(ds.get("end_sec") or 0.0)
                ds_dur = max(1.0, ds_t1 - ds_t0)
                if (c_bound_e - c_bound_s) >= 1.60 and (ds_t0 < c_bound_s + 0.05 or ds_t1 > c_bound_e - 0.05):
                    new_t0 = max(ds_t0, c_bound_s + 0.06)
                    new_t1 = min(c_bound_e - 0.06, new_t0 + ds_dur)
                    if new_t1 - new_t0 >= 1.0:
                        ds["start_sec"] = round(new_t0, 3)
                        ds["end_sec"] = round(new_t1, 3)
                        ds["duration_sec"] = round(new_t1 - new_t0, 3)
    data_stamp_spans = [[float(ds["start_sec"]), float(ds["end_sec"])] for ds in resolved_data_stamps]
    vdir_hint = (visual_plan or {}).get("_visuals_dir")
    raw_anatomy_callouts = (
        resolve_anatomy_callout_windows(
            {"cuts": cuts},
            visual_plan,
            visuals_dir=Path(str(vdir_hint)) if vdir_hint else None,
        )
        if is_v8
        else []
    )
    resolved_anatomy_callouts, overlay_conflicts_resolved = resolve_overlay_window_conflicts(
        resolved_data_stamps,
        raw_anatomy_callouts,
    )
    anatomy_callout_spans = [[float(ac["start_sec"]), float(ac["end_sec"])] for ac in resolved_anatomy_callouts]
    for c in cuts:
        c_s0 = float(c.get("out_start_sec") or 0.0)
        c_e0 = float(c.get("out_end_sec") or 0.0)
        c["has_data_stamp"] = any(ds0 < c_e0 - 0.04 and ds1 > c_s0 + 0.04 for ds0, ds1 in data_stamp_spans)
        c["has_anatomy_callout"] = any(ac0 < c_e0 - 0.04 and ac1 > c_s0 + 0.04 for ac0, ac1 in anatomy_callout_spans)

    all_used = {int(c["clip_index"]) for c in cuts} | {
        int(c["secondary_clip_index"]) for c in cuts if c.get("secondary_clip_index") is not None
    }
    edl_out: dict[str, Any] = {
        "schema": (PROMPT_SCHEMA_VERSION_V8 if is_v8 else PROMPT_SCHEMA_VERSION_V7),
        "profile": "neuro_diorama",
        "style_profile": resolved_style,
        "edl_mode": (f"v8_expressive_dynamic_{fps}fps" if is_v8 else "v7_dynamic_zero_reuse_24fps"),
        "playback_speed": float(DIORAMA_V7_VISUAL_PLAYBACK_SPEED),
        "zero_clip_reuse": bool(max_reuse <= 1),
        "max_clip_reuse": max_reuse,
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round((speech_frames_actual if is_v8 else speech_frames) / float(fps), 3),
        "cut_count": len(cuts),
        "avg_cut_duration_sec": round(mean_cut, 3),
        "cut_duration_std_sec": round(std_cut, 3),
        "cut_duration_cv": cut_cv,
        "rapid_cut_ratio": rapid_ratio,
        "max_cut_duration_sec": round(max(cut_durs) if cut_durs else 0.0, 3),
        "min_cut_duration_sec": round(min(cut_durs) if cut_durs else 0.0, 3),
        "camera_move_counts": cam_counts,
        "locked_camera_ratio": locked_cam_ratio,
        "zoom_camera_ratio": zoom_cam_ratio,
        "pan_left_cuts": cam_counts.get("pan_left", 0),
        "pan_right_cuts": cam_counts.get("pan_right", 0),
        "aba_location_returns": aba_returns,
        "base_clips_used": len(all_used),
        "split_screen_cuts": sum(1 for c in cuts if c["mode"] in ("split_hstack", "split_vstack")),
        "split_hstack_cuts": sum(1 for c in cuts if c["mode"] == "split_hstack"),
        "act5_montage_cuts": sum(1 for c in cuts if c["act"] == 5),
        "data_stamp_spans": data_stamp_spans,
        "resolved_data_stamps": resolved_data_stamps,
        "anatomy_callout_spans": anatomy_callout_spans,
        "resolved_anatomy_callouts": resolved_anatomy_callouts,
        "overlay_conflicts_resolved": overlay_conflicts_resolved,
        "cuts": cuts,
    }
    if is_v8:
        edl_out["cameo_cuts"] = sum(1 for c in cuts if c.get("cameo_easter_egg"))
        edl_out["dissolve_6f_cuts"] = sum(1 for c in cuts if c.get("transition_out") == "dissolve_6f")
        edl_out["camera_bridge_cuts"] = sum(
            1
            for c in cuts[:-1]
            if str(c.get("transition_out") or "").strip().lower() not in ("", "hard", "action_impact_cut", "seamless_relay_cut")
        )
    return edl_out


def build_crosscut_edl(
    visual_plan: dict[str, Any],
    sentence_spans: list[dict[str, Any]],
    clip_files: list[Path],
    speech_end_sec: float,
    total_duration_sec: float,
    script_doc: dict[str, Any] | None = None,
    source_window_overrides: dict[int, Any] | None = None,
    virtual_clip_duration_sec: float | None = None,
) -> dict[str, Any]:
    """
    R58 / R63 / R68 NLE Edit Decision List builder:
      - Dispatches to Schema v7/v8 `build_v7_dynamic_edl` (`24.0fps`, `0%` reuse)
        whenever `is_diorama_v7_plan(visual_plan)` or `is_expressive_v8_plan(visual_plan, script_doc)` is True.
      - Dispatches to Schema v6.1 `build_one_to_one_edl` (`0%` clip reuse, `1.00x` framing)
        whenever `visual_plan.get("zero_clip_reuse")` is True or `len(clip_files) >= len(sentence_spans) + 1`.
      - Preserves legacy multi-window interleaving fallback only for legacy synthetic `20-26`-clip fixtures.
    """
    if is_diorama_v7_plan(visual_plan) or is_expressive_v8_plan(visual_plan, script_doc):
        return build_v7_dynamic_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
            source_window_overrides=source_window_overrides,
            virtual_clip_duration_sec=virtual_clip_duration_sec,
        )
    if bool(visual_plan.get("zero_clip_reuse")) or len(clip_files) >= len(sentence_spans) + 1:
        return build_one_to_one_edl(
            visual_plan=visual_plan,
            sentence_spans=sentence_spans,
            clip_files=clip_files,
            speech_end_sec=speech_end_sec,
            total_duration_sec=total_duration_sec,
            script_doc=script_doc,
            virtual_clip_duration_sec=virtual_clip_duration_sec,
        )
    if len(clip_files) < DIORAMA_CLIP_COUNT_MIN:
        raise ValueError(
            f"build_crosscut_edl requires >= {DIORAMA_CLIP_COUNT_MIN} Flow clips (got {len(clip_files)})"
        )
    fps = int(VIDEO_FPS)
    total_frames = min(SHORTS_HARD_CEILING_FRAMES, max(60, int(round(total_duration_sec * fps))))
    speech_frames = min(total_frames - int(round(DIORAMA_OUTRO_SWELL_SEC * fps)), int(round(speech_end_sec * fps)))
    speech_frames = max(30, speech_frames)
    outro_frames = max(30, total_frames - speech_frames)

    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    n_clips = len(clip_files)
    clip_durs = [
        (
            max(0.50, float(virtual_clip_duration_sec))
            if (virtual_clip_duration_sec is not None and (not Path(cf).is_file() or Path(cf).stat().st_size <= 0))
            else (max(0.50, raw_cd) if (raw_cd := float(_clip_duration(Path(cf)))) > 0.05 else 4.0)
        )
        for cf in clip_files
    ]

    # Group 0-based clip indices by Act (1..6)
    act_pools: dict[int, list[int]] = {a: [] for a in range(1, DIORAMA_ACT_COUNT + 1)}
    clip_grammars: dict[int, str] = {}
    for idx in range(n_clips):
        spec = plan_clips[idx] if idx < len(plan_clips) and isinstance(plan_clips[idx], dict) else {}
        act_no = int(spec.get("act") or min(DIORAMA_ACT_COUNT, (idx * DIORAMA_ACT_COUNT) // n_clips + 1))
        act_no = max(1, min(DIORAMA_ACT_COUNT, act_no))
        act_pools[act_no].append(idx)
        clip_grammars[idx] = str(spec.get("grammar") or "arch_cutaway_diorama")
    for a in range(1, DIORAMA_ACT_COUNT + 1):
        if not act_pools[a]:
            act_pools[a] = [min(n_clips - 1, (a - 1) * max(1, n_clips // DIORAMA_ACT_COUNT))]

    # Reserve final clip in Act 6 pool for the sky tilt-up outro card
    outro_clip_idx = act_pools[DIORAMA_ACT_COUNT][-1]

    # Build beat intervals across [0, speech_frames]
    s_act = _sentence_act_map(script_doc or {}, len(sentence_spans))
    raw_beats: list[dict[str, Any]] = []
    for sp in sentence_spans:
        s_idx = int(sp["sentence_index"])
        act_no = s_act.get(s_idx, 1)
        t0 = float(sp["start_sec"])
        t1 = float(sp["end_sec"])
        dur = max(0.35, t1 - t0)
        if act_no == 5 and dur >= 1.4:
            # Act 5 crisis climax: slice sentences into fast rhythmic 0.65s montage beats
            target_sub = round((DIORAMA_ACT5_MONTAGE_CUT_MIN_SEC + DIORAMA_ACT5_MONTAGE_CUT_MAX_SEC) * 0.5, 2)
            k = max(2, min(4, int(round(dur / target_sub))))
        elif dur >= 2.25:
            k = 2
        else:
            k = 1
        for sub_i in range(k):
            b0 = t0 + dur * (sub_i / float(k))
            b1 = t0 + dur * ((sub_i + 1) / float(k))
            raw_beats.append({"act": act_no, "sentence_index": s_idx, "t0": b0, "t1": b1})

    # Tune cut count cleanly into profile-appropriate [cut_min, cut_max - 1] (+1 outro cut)
    from pipeline.config import (
        MICRO_SHORT_CUT_MAX,
        MICRO_SHORT_CUT_MIN,
        MICRO_SHORT_PROFILE,
        SHORTS_90S_CUT_COUNT_MAX,
        SHORTS_90S_CUT_COUNT_MIN,
        SHORTS_90S_PROFILE,
        resolve_shorts_format_profile,
    )

    cc_fmt = resolve_shorts_format_profile(
        visual_plan,
        script_doc,
        {"sentences": sentence_spans, "total_duration_sec": total_duration_sec},
    )
    if cc_fmt == MICRO_SHORT_PROFILE:
        min_speech_cuts = MICRO_SHORT_CUT_MIN - 1
        max_speech_cuts = MICRO_SHORT_CUT_MAX - 1
    elif cc_fmt == SHORTS_90S_PROFILE:
        min_speech_cuts = SHORTS_90S_CUT_COUNT_MIN - 1
        max_speech_cuts = SHORTS_90S_CUT_COUNT_MAX - 1
    else:
        min_speech_cuts = DIORAMA_TARGET_CUT_MIN - 1
        max_speech_cuts = DIORAMA_TARGET_CUT_MAX - 1
    while len(raw_beats) < min_speech_cuts:
        # Split the longest beat
        longest_i = max(range(len(raw_beats)), key=lambda i: raw_beats[i]["t1"] - raw_beats[i]["t0"])
        b = raw_beats[longest_i]
        mid = 0.5 * (b["t0"] + b["t1"])
        if b["t1"] - b["t0"] < 0.70:
            break
        raw_beats[longest_i : longest_i + 1] = [
            {"act": b["act"], "sentence_index": b["sentence_index"], "t0": b["t0"], "t1": mid},
            {"act": b["act"], "sentence_index": b["sentence_index"], "t0": mid, "t1": b["t1"]},
        ]
    while len(raw_beats) > max_speech_cuts:
        # Merge shortest adjacent pair in the same act
        best_i = min(
            range(len(raw_beats) - 1),
            key=lambda i: (0 if raw_beats[i]["act"] == raw_beats[i + 1]["act"] else 100.0)
            + (raw_beats[i + 1]["t1"] - raw_beats[i]["t0"]),
        )
        merged = {
            "act": raw_beats[best_i]["act"],
            "sentence_index": raw_beats[best_i]["sentence_index"],
            "t0": raw_beats[best_i]["t0"],
            "t1": raw_beats[best_i + 1]["t1"],
        }
        raw_beats[best_i : best_i + 2] = [merged]

    # Convert beats to contiguous frame-exact spans covering [0, speech_frames]
    n_b = len(raw_beats)
    speech_dur_s = speech_frames / float(fps)
    boundaries = [0]
    for i in range(1, n_b):
        ideal_t = raw_beats[i]["t0"]
        f_idx = int(round((ideal_t / max(0.1, speech_end_sec)) * speech_frames))
        min_f = boundaries[-1] + 12  # >= 0.40s per cut
        max_f = speech_frames - (n_b - i) * 12
        boundaries.append(max(min_f, min(max_f, f_idx)))
    boundaries.append(speech_frames)

    # Track monotonic source cursors per clip so no source window is ever reused
    cursors = [0.15 for _ in range(n_clips)]
    slice_visits = [0 for _ in range(n_clips)]
    act_rr = {a: 0 for a in range(1, DIORAMA_ACT_COUNT + 1)}
    split_cfg = visual_plan.get("split_screen") if isinstance(visual_plan.get("split_screen"), dict) else {}
    raw_splits = visual_plan.get("split_comparisons") if isinstance(visual_plan.get("split_comparisons"), list) else []
    first_split_comp = raw_splits[0] if raw_splits and isinstance(raw_splits[0], dict) else {}
    act3_seen = 0

    cuts: list[dict[str, Any]] = []
    prev_clip_idx = -1
    for cut_i in range(n_b):
        f0, f1 = boundaries[cut_i], boundaries[cut_i + 1]
        c_frames = max(12, f1 - f0)
        out_dur = c_frames / float(fps)
        beat = raw_beats[cut_i]
        act_no = int(beat["act"])
        pool = list(act_pools[act_no])

        # Select next clip via round-robin interleaving (never same clip back-to-back when pool > 1)
        chosen = pool[act_rr[act_no] % len(pool)]
        act_rr[act_no] += 1
        if chosen == prev_clip_idx and len(pool) > 1:
            chosen = pool[act_rr[act_no] % len(pool)]
            act_rr[act_no] += 1
        # If chosen clip has little remaining footage, pick clip in pool (or global) with most remaining headroom
        rem = (clip_durs[chosen] - 0.15) - cursors[chosen]
        if rem < out_dur * 0.78:
            best_pool = max(pool, key=lambda idx: (clip_durs[idx] - 0.15) - cursors[idx])
            if (clip_durs[best_pool] - 0.15) - cursors[best_pool] >= out_dur * 0.78 and best_pool != prev_clip_idx:
                chosen = best_pool
            else:
                candidates = [idx for idx in range(n_clips) if idx != prev_clip_idx and idx != outro_clip_idx]
                if candidates:
                    chosen = max(candidates, key=lambda idx: (clip_durs[idx] - 0.15) - cursors[idx])

        avail = max(0.45, (clip_durs[chosen] - 0.12) - cursors[chosen])
        speed = 1.00
        if avail < out_dur:
            speed = max(0.75, avail / out_dur)
        src_span = min(avail, out_dur * speed)
        src_s = round(cursors[chosen], 4)
        src_e = round(src_s + src_span, 4)
        cursors[chosen] = round(src_e + 0.05, 4)

        visit_no = slice_visits[chosen]
        slice_visits[chosen] += 1
        crop_zoom = DIORAMA_SLICE_CROPS[min(visit_no, len(DIORAMA_SLICE_CROPS) - 1)]

        mode = "single"
        secondary_clip_idx = None
        secondary_src = None
        if act_no == 3:
            act3_seen += 1
            if act3_seen in (2, 5) and len(pool) >= 2 and out_dur >= 1.2:
                sec_candidates = [idx for idx in pool if idx != chosen]
                sec_idx = sec_candidates[0]
                sec_avail = max(0.45, (clip_durs[sec_idx] - 0.12) - cursors[sec_idx])
                if sec_avail >= out_dur * 0.80:
                    mode = "split_vstack"
                    secondary_clip_idx = sec_idx
                    s2_span = min(sec_avail, out_dur)
                    secondary_src = [round(cursors[sec_idx], 4), round(cursors[sec_idx] + s2_span, 4)]
                    cursors[sec_idx] = round(cursors[sec_idx] + s2_span + 0.05, 4)

        top_lbl = str(first_split_comp.get("top_label") or split_cfg.get("left_label") or "EXPECTED")
        bot_lbl = str(first_split_comp.get("bottom_label") or split_cfg.get("right_label") or "ACTUAL")
        cuts.append(
            {
                "cut_index": cut_i + 1,
                "act": act_no,
                "sentence_index": beat["sentence_index"],
                "mode": mode,
                "out_start_sec": round(f0 / float(fps), 4),
                "out_end_sec": round(f1 / float(fps), 4),
                "frames": c_frames,
                "duration_sec": round(out_dur, 4),
                "clip_index": chosen + 1,
                "clip_file": clip_files[chosen].name,
                "grammar": clip_grammars.get(chosen, "arch_cutaway_diorama"),
                "src_start_sec": src_s,
                "src_end_sec": src_e,
                "crop_zoom": crop_zoom,
                "secondary_clip_index": (secondary_clip_idx + 1 if secondary_clip_idx is not None else None),
                "secondary_clip_file": (clip_files[secondary_clip_idx].name if secondary_clip_idx is not None else None),
                "secondary_src_span": secondary_src,
                "split_labels": ([top_lbl, bot_lbl] if mode == "split_vstack" else None),
                "outro_sky_card": False,
            }
        )
        prev_clip_idx = chosen

    # Append final Act 6 Sky Tilt-Up Outro Card cut
    outro_dur = outro_frames / float(fps)
    outro_avail = max(0.6, clip_durs[outro_clip_idx] - 0.20)
    outro_s = max(0.10, min(cursors[outro_clip_idx], clip_durs[outro_clip_idx] - min(outro_avail, outro_dur + 0.15)))
    outro_e = min(clip_durs[outro_clip_idx] - 0.05, outro_s + min(outro_avail, outro_dur))
    cuts.append(
        {
            "cut_index": len(cuts) + 1,
            "act": DIORAMA_ACT_COUNT,
            "sentence_index": len(sentence_spans),
            "mode": "single",
            "out_start_sec": round(speech_frames / float(fps), 4),
            "out_end_sec": round(total_frames / float(fps), 4),
            "frames": outro_frames,
            "duration_sec": round(outro_dur, 4),
            "clip_index": outro_clip_idx + 1,
            "clip_file": clip_files[outro_clip_idx].name,
            "grammar": clip_grammars.get(outro_clip_idx, "arch_cutaway_diorama"),
            "src_start_sec": round(outro_s, 4),
            "src_end_sec": round(outro_e, 4),
            "crop_zoom": 1.00,
            "secondary_clip_index": None,
            "secondary_clip_file": None,
            "secondary_src_span": None,
            "split_labels": None,
            "outro_sky_card": True,
        }
    )

    return {
        "schema": 6,
        "profile": "neuro_diorama",
        "edl_mode": "legacy_crosscut",
        "zero_clip_reuse": False,
        "max_clip_reuse": _compute_max_clip_reuse(cuts),
        "fps": fps,
        "total_frames": total_frames,
        "total_duration_sec": round(total_frames / float(fps), 3),
        "speech_end_sec": round(speech_frames / float(fps), 3),
        "cut_count": len(cuts),
        "avg_cut_duration_sec": round((total_frames / float(fps)) / max(1, len(cuts)), 3),
        "base_clips_used": len({c["clip_index"] for c in cuts}),
        "split_screen_cuts": sum(1 for c in cuts if c["mode"] in ("split_hstack", "split_vstack")),
        "act5_montage_cuts": sum(1 for c in cuts if c["act"] == 5),
        "cuts": cuts,
    }


def compute_locked_edl_cut_frame_requirements(
    project_id_or_dir: str | Path,
    tts_res: dict[str, Any] | None = None,
    *,
    safety_pad_frames: int = 6,
) -> dict[str, Any]:
    """
    Guard 4 Virtual Master EDL Frame-Requirement Calculator:
      - Computes exact `30fps` (or plan-native FPS) EDL cut durations and Track-V1 transition overlaps
        from `visual_plan.json` + locked TTS timings (`tts_res` or `04_audio/voice_report.json`) even BEFORE
        `03_visuals/flow_native_clips` or `03_visuals/brain_simulator_clips` exist on disk (`0` MP4 files).
      - Returns `{"fps", "total_frames", "total_duration_sec", "edl_frame_map", "cuts"}` where each 1-based
        `clip_index` maps to `req_n_frames = eff_f + ov_f_next + int(safety_pad_frames)` (`max` across cuts).
    """
    from pipeline.config import (
        EXPRESSIVE_V8_DISSOLVE_8_FRAMES,
        EXPRESSIVE_V8_DISSOLVE_FRAMES,
        EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES,
        EXPRESSIVE_V8_WHIP_PAN_FRAMES,
        PROMPT_SCHEMA_VERSION_V8,
    )

    p_dir = Path(project_id_or_dir) if Path(str(project_id_or_dir)).exists() else (PROJECTS_DIR / str(project_id_or_dir))
    vp_path = next(
        (
            p
            for p in (
                p_dir / "03_visuals" / "visual_plan.json",
                p_dir / "02_script" / "visual_plan.json",
                p_dir / "visual_plan.json",
            )
            if p.exists()
        ),
        None,
    )
    if vp_path is None:
        raise FileNotFoundError(f"visual_plan.json not found in {p_dir}")
    visual_plan = json.loads(vp_path.read_text(encoding="utf-8"))
    if isinstance(visual_plan, dict):
        visual_plan = {**visual_plan, "_visuals_dir": str(p_dir / "03_visuals")}

    try:
        _sents, script_doc = load_diorama_script_sentences(p_dir)
    except (FileNotFoundError, ValueError):
        raw_sc_path = next((p for p in (p_dir / "02_script" / "script.json", p_dir / "script.json") if p.exists()), None)
        script_doc = json.loads(raw_sc_path.read_text(encoding="utf-8")) if raw_sc_path else {}

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

    if tts_res is None:
        vr_path = p_dir / "04_audio" / "voice_report.json"
        if not vr_path.exists():
            raise FileNotFoundError(f"voice_report.json not found in {p_dir / '04_audio'}")
        vr = json.loads(vr_path.read_text(encoding="utf-8"))
        wav_p = p_dir / "04_audio" / "audio_master.wav"
        tot_dur = float(vr.get("total_duration_sec") or 0.0)
        if tot_dur <= 0.0 and wav_p.is_file():
            tot_dur = float(_clip_duration(wav_p))
        sentence_spans = list(vr["sentence_spans"])
        speech_end_sec = float(vr["speech_end_sec"])
        total_duration_sec = tot_dur
    else:
        sentence_spans = list(tts_res["sentence_spans"])
        speech_end_sec = float(tts_res["speech_end_sec"])
        total_duration_sec = float(tts_res["total_duration_sec"])

    disk_clips = _resolve_diorama_clip_files(p_dir / "03_visuals")
    disk_by_num: dict[int, Path] = {}
    for cf in disk_clips:
        m_num = re.search(r"(\d+)", cf.stem)
        if m_num:
            disk_by_num[int(m_num.group(1))] = cf

    plan_clips = visual_plan.get("clips") if isinstance(visual_plan.get("clips"), list) else []
    n_target = max(len(plan_clips), max(disk_by_num.keys(), default=0))
    if n_target <= 0:
        raise ValueError(f"visual_plan.json in {p_dir} defines 0 clips")

    clip_files: list[Path] = []
    for idx_1 in range(1, n_target + 1):
        if idx_1 in disk_by_num:
            clip_files.append(disk_by_num[idx_1])
        else:
            spec_c = plan_clips[idx_1 - 1] if (idx_1 - 1 < len(plan_clips) and isinstance(plan_clips[idx_1 - 1], dict)) else {}
            is_sim_clip = (
                str(spec_c.get("grammar") or "").strip() == "brain_simulator_3d"
                or str(spec_c.get("render_engine") or "").strip().lower() == "blender_3d_simulator"
            )
            sub_d = "brain_simulator_clips" if is_sim_clip else "flow_native_clips"
            clip_files.append(p_dir / "03_visuals" / sub_d / f"clip_{idx_1:02d}.mp4")

    edl = build_crosscut_edl(
        visual_plan=visual_plan,
        sentence_spans=sentence_spans,
        clip_files=clip_files,
        speech_end_sec=speech_end_sec,
        total_duration_sec=total_duration_sec,
        script_doc=script_doc,
        virtual_clip_duration_sec=8.0,
    )

    fps = int(edl["fps"])
    is_v8_edl = is_v8 or is_expressive_v8_plan(visual_plan, edl)
    is_v7_edl = is_v8_edl or is_v7 or int(edl.get("schema") or 6) >= PROMPT_SCHEMA_VERSION_V7
    ceiling_frames = (
        int(round(EXPRESSIVE_V8_HARD_CEILING_SEC * fps))
        if is_v8_edl
        else (SHORTS_HARD_CEILING_FRAMES_V7 if is_v7_edl else SHORTS_HARD_CEILING_FRAMES)
    )
    total_frames = min(ceiling_frames, int(edl["total_frames"]))
    allow_alpha = bool((visual_plan or {}).get("allow_alpha_dissolves"))

    def _transition_overlap_frames(tr_raw: str) -> int:
        tr_n = str(tr_raw or "").strip().lower()
        if tr_n == "portal_crash_zoom_10f":
            return int(EXPRESSIVE_V8_PORTAL_ZOOM_FRAMES)
        if tr_n in ("whip_pan_blur_8f", "occlusion_wipe"):
            return int(EXPRESSIVE_V8_WHIP_PAN_FRAMES)
        if allow_alpha:
            if tr_n == "dissolve_15f":
                return 15
            if tr_n == "dissolve_12f":
                return 12
            if tr_n in ("dissolve_8f", "split_screen_wipe", "daisy_chain_bridge"):
                return int(EXPRESSIVE_V8_DISSOLVE_8_FRAMES)
            if tr_n in ("dissolve_6f", "match_cut_bridge"):
                return int(EXPRESSIVE_V8_DISSOLVE_FRAMES)
        return 0

    clamped_cuts: list[tuple[dict[str, Any], int]] = []
    cum_f = 0
    for cut in edl["cuts"]:
        rem = total_frames - cum_f
        if rem <= 0:
            break
        eff_f = min(rem, int(cut["frames"]))
        clamped_cuts.append((cut, eff_f))
        cum_f += eff_f

    pad_f = max(0, int(safety_pad_frames))
    edl_frame_map: dict[int, int] = {}
    for idx_c, (cut_cur, eff_f) in enumerate(clamped_cuts):
        ov_f_next = 0
        if is_v8_edl and idx_c < len(clamped_cuts) - 1:
            cut_nxt, eff_f_nxt = clamped_cuts[idx_c + 1]
            cand_ov = _transition_overlap_frames(str(cut_cur.get("transition_out") or ""))
            if (
                cand_ov > 0
                and cut_cur.get("mode") == "single"
                and cut_nxt.get("mode") == "single"
                and eff_f >= cand_ov + 4
                and eff_f_nxt >= cand_ov + 4
            ):
                ov_f_next = cand_ov
        req_n_frames = int(eff_f) + int(ov_f_next) + pad_f
        c_idx = int(cut_cur["clip_index"])
        edl_frame_map[c_idx] = max(edl_frame_map.get(c_idx, 0), req_n_frames)
        if cut_cur.get("secondary_clip_index") is not None:
            sec_idx = int(cut_cur["secondary_clip_index"])
            edl_frame_map[sec_idx] = max(edl_frame_map.get(sec_idx, 0), req_n_frames)

    total_dur = round(cum_f / float(fps), 3) if cum_f > 0 else round(total_frames / float(fps), 3)
    return {
        "fps": int(fps),
        "total_frames": int(cum_f if cum_f > 0 else total_frames),
        "total_duration_sec": float(total_dur),
        "edl_frame_map": dict(sorted(edl_frame_map.items())),
        "cuts": edl["cuts"],
    }


def lock_audio_durations_onto_visual_plan(
    visual_plan: dict[str, Any],
    sentence_spans: list[tuple[float, float]],
    *,
    enable_extended_durations: bool | None = None,
) -> dict[str, Any]:
    """
    Audio-Before-Flow (`M3`):
      1. Computes exact spoken duration `[t0, t1]` for each clip's `sentence_index .. end_sentence_index`.
      2. Snaps `render_sec` to `FLOW_OMNI_EXTENDED_DURATION_CHOICES` (`3..15s`) when `enable_extended_durations`
         is True (`max(3, min(15, ceil(spoken_dur + 0.6)))`), or `8s` otherwise.
      3. Marks `forbid_slowmo_stretch = True` (`0%` slow-motion stretch) when `render_sec >= spoken_dur`.
    """
    from pipeline.config import (
        DIORAMA_CLIP_RENDER_SEC,
        EXPRESSIVE_V8_FORBID_SLOWMO_STRETCH,
        FLOW_OMNI_ENABLE_EXTENDED_DURATIONS,
        FLOW_OMNI_EXTENDED_DURATION_CHOICES,
    )

    ext_ok = FLOW_OMNI_ENABLE_EXTENDED_DURATIONS if enable_extended_durations is None else bool(enable_extended_durations)
    out_plan = dict(visual_plan)
    out_clips: list[dict[str, Any]] = []
    n_sents = len(sentence_spans)
    for idx, c in enumerate(visual_plan.get("clips") or [], start=1):
        if not isinstance(c, dict):
            continue
        spec = dict(c)
        s0_i = int(spec.get("sentence_index") or min(idx, max(1, n_sents)))
        s1_i = int(spec.get("end_sentence_index") or s0_i)
        s0_clamped = max(1, min(n_sents, s0_i))
        s1_clamped = max(s0_clamped, min(n_sents, s1_i))
        if n_sents > 0:
            t_start = float(sentence_spans[s0_clamped - 1][0])
            t_end = float(sentence_spans[s1_clamped - 1][1])
            spoken_dur = max(0.35, t_end - t_start)
        else:
            spoken_dur = 3.5
        if ext_ok:
            needed = int(math.ceil(spoken_dur + 0.6))
            snapped = min(
                FLOW_OMNI_EXTENDED_DURATION_CHOICES,
                key=lambda d: (0 if d >= needed else 1, abs(d - needed)),
            )
            spec["render_sec"] = int(snapped)
        else:
            spec["render_sec"] = int(spec.get("render_sec") or DIORAMA_CLIP_RENDER_SEC)
        spec["locked_spoken_duration_sec"] = round(spoken_dur, 3)
        spec["forbid_slowmo_stretch"] = bool(
            EXPRESSIVE_V8_FORBID_SLOWMO_STRETCH and float(spec["render_sec"]) >= spoken_dur
        )
        out_clips.append(spec)
    out_plan["clips"] = out_clips
    out_plan["audio_before_flow_locked"] = True
    return out_plan


def split_sentences_at_keyword_beats(
    sentence_spans: list[tuple[float, float]],
    sentences: list[str],
    *,
    target_beat_sec: float | None = None,
) -> list[dict[str, Any]]:
    """
    Sub-Sentence Keyword Impact Cutter (`M6` / `R58-K`):
    Splits any spoken sentence span longer than `target_beat_sec * 1.45` at natural clause/keyword pivots
    so visual cuts land every `~2.0s` (`1.6–2.4s`) on spoken action verbs, numbers, or contrast pivots.
    """
    from pipeline.config import EXPRESSIVE_V8_KEYWORD_BEAT_TARGET_SEC

    beat_target = float(target_beat_sec or EXPRESSIVE_V8_KEYWORD_BEAT_TARGET_SEC)
    beats: list[dict[str, Any]] = []
    for s_idx, ((t0, t1), text) in enumerate(zip(sentence_spans, sentences), start=1):
        dur = max(0.20, float(t1) - float(t0))
        clean_txt = str(text or "").strip()
        if dur <= beat_target * 1.45:
            beats.append(
                {
                    "sentence_index": s_idx,
                    "sub_beat_index": 1,
                    "start_sec": round(float(t0), 4),
                    "end_sec": round(float(t1), 4),
                    "duration_sec": round(dur, 4),
                    "text": clean_txt,
                }
            )
            continue
        raw_clauses = [p.strip() for p in _KEYWORD_BEAT_SPLIT_RE.split(clean_txt) if p and p.strip()]
        n_target = max(2, int(round(dur / max(1.2, beat_target))))
        if len(raw_clauses) < 2:
            words = clean_txt.split()
            chunk_sz = max(2, int(math.ceil(len(words) / float(n_target))))
            raw_clauses = [" ".join(words[i : i + chunk_sz]) for i in range(0, len(words), chunk_sz)]
        elif len(raw_clauses) > n_target:
            merged: list[str] = []
            for cl in raw_clauses:
                if merged and len(merged[-1].split()) < 4:
                    merged[-1] = f"{merged[-1]}, {cl}"
                else:
                    merged.append(cl)
            raw_clauses = merged
        word_counts = [max(1, len(c.split())) for c in raw_clauses]
        total_w = float(sum(word_counts))
        cur_t = float(t0)
        for b_i, (cl_txt, wc) in enumerate(zip(raw_clauses, word_counts), start=1):
            b_dur = (float(t1) - cur_t) if b_i == len(raw_clauses) else dur * (wc / total_w)
            nxt_t = cur_t + max(0.20, b_dur)
            beats.append(
                {
                    "sentence_index": s_idx,
                    "sub_beat_index": b_i,
                    "start_sec": round(cur_t, 4),
                    "end_sec": round(nxt_t, 4),
                    "duration_sec": round(nxt_t - cur_t, 4),
                    "text": cl_txt,
                }
            )
            cur_t = nxt_t
    return beats


def build_dual_harvest_edl_windows(clip_dur_sec: float = 8.0) -> tuple[tuple[float, float], tuple[float, float]]:
    """
    Returns non-overlapping early (`A₁`) and late (`A₂`) NLE harvest windows inside a single 8s source clip (`M6`),
    allowing `A₁ -> B -> A₂` cross-cutting without frame reuse.
    """
    from pipeline.config import EXPRESSIVE_V8_DUAL_HARVEST_WINDOWS_SEC

    (a0, a1), (b0, b1) = EXPRESSIVE_V8_DUAL_HARVEST_WINDOWS_SEC
    safe_eof = max(2.5, float(clip_dur_sec) - 0.15)
    w1 = (round(min(a0, safe_eof - 0.5), 3), round(min(a1, safe_eof - 0.25), 3))
    w2_start = max(w1[1] + 0.60, min(b0, safe_eof - 1.20))
    w2_end = max(w2_start + 0.50, min(b1, safe_eof))
    return w1, (round(w2_start, 3), round(w2_end, 3))


def verify_state_swap_hist_corr(frame_a_bgr: np.ndarray, frame_b_bgr: np.ndarray) -> dict[str, Any]:
    """
    Verifies background color/lighting continuity (`hist_corr >= EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR` = `0.90`)
    across a `T2` Same-Framing State-Swap Jump Cut (`M8`).
    """
    from pipeline.config import EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR

    if frame_a_bgr is None or frame_b_bgr is None or frame_a_bgr.size == 0 or frame_b_bgr.size == 0:
        return {"passed": False, "hist_corr": 0.0, "threshold": EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR}
    hsv_a = cv2.cvtColor(frame_a_bgr, cv2.COLOR_BGR2HSV)
    hsv_b = cv2.cvtColor(frame_b_bgr, cv2.COLOR_BGR2HSV)
    hist_a = cv2.calcHist([hsv_a], [0, 1], None, [24, 24], [0, 180, 0, 256])
    hist_b = cv2.calcHist([hsv_b], [0, 1], None, [24, 24], [0, 180, 0, 256])
    cv2.normalize(hist_a, hist_a, 0, 1, cv2.NORM_MINMAX)
    cv2.normalize(hist_b, hist_b, 0, 1, cv2.NORM_MINMAX)
    corr = float(cv2.compareHist(hist_a, hist_b, cv2.HISTCMP_CORREL))
    return {
        "passed": corr >= float(EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR),
        "hist_corr": round(corr, 4),
        "threshold": float(EXPRESSIVE_V8_STATE_SWAP_MIN_HIST_CORR),
    }


def resolve_spatial_metric_stamps(
    script_doc: dict[str, Any] | None,
    sentence_spans: list[tuple[float, float]],
) -> list[dict[str, Any]]:
    """
    Resolves up to 3 post-composite 3D-tracked diegetic metric stamps (`M9`, e.g., `15 MIN`, `4X LONGER`, `88%`)
    aligned to their spoken `sentence_index` window without injecting AI text into Google Flow.
    """
    raw_stamps = (script_doc or {}).get("spatial_metric_stamps") or []
    resolved: list[dict[str, Any]] = []
    n_sents = len(sentence_spans)
    for item in raw_stamps[:3]:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or item.get("text") or "").strip().upper()
        if not label:
            continue
        s_idx = int(item.get("sentence_index") or 1)
        if 1 <= s_idx <= n_sents:
            t0, t1 = sentence_spans[s_idx - 1]
        else:
            t0, t1 = float(item.get("start_sec") or 0.0), float(item.get("end_sec") or 2.0)
        resolved.append(
            {
                "label": label[:18],
                "sentence_index": s_idx,
                "start_sec": round(float(t0), 3),
                "end_sec": round(float(t1), 3),
                "anchor_xy_norm": tuple(item.get("anchor_xy_norm") or (0.50, 0.26)),
            }
        )
    return resolved

