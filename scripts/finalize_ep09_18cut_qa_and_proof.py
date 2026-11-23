#!/usr/bin/env python3
"""
Extracts visual proof sheets (`ep09_v2_18cut_proof.jpg` and `ep09_v2_taxi_vs_bus_3d_arrows.jpg`)
directly from the assembled `final_shorts_1080x1920.mp4` of `v8_ep09_maguire_london_taxi_hippocampus`
and runs the initial `posthoc-qa` CV pass so we can visually inspect `sheet_01..03.jpg` before signing off.
"""

from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import cv2
import numpy as np

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

PROJECT_ID = "v8_ep09_maguire_london_taxi_hippocampus"
PROJ_DIR = ROOT / "BCI_Shorts_Channel" / "projects" / PROJECT_ID
ART_DIR = Path("/home/canadaofbin/.gemini/antigravity-cli/brain/b57c97a8-6324-4c31-a2bb-16b25e28dd55")


def _grab_frame_at_sec(cap: cv2.VideoCapture, fps: float, sec: float) -> np.ndarray:
    f_idx = max(0, int(round(sec * fps)))
    cap.set(cv2.CAP_PROP_POS_FRAMES, f_idx)
    ok, frame = cap.read()
    if not ok or frame is None:
        raise RuntimeError(f"Failed to read frame at {sec:.2f}s (frame {f_idx})")
    return frame


def main() -> int:
    edl_path = PROJ_DIR / "05_assembly" / "edit_decision_list.json"
    mp4_path = PROJ_DIR / "05_assembly" / "final_shorts_1080x1920.mp4"
    edl = json.loads(edl_path.read_text(encoding="utf-8"))
    cuts = [c for c in (edl.get("cuts") or []) if isinstance(c, dict) and not c.get("outro_sky_card")]
    assert len(cuts) == 18, f"Expected 18 cuts, got {len(cuts)}"

    cap = cv2.VideoCapture(str(mp4_path))
    assert cap.isOpened(), f"Cannot open {mp4_path}"
    fps = float(cap.get(cv2.CAP_PROP_FPS) or 30.0)

    # 1. 18-cut 6x3 contact sheet
    cols, rows = 6, 3
    tw, th, hh = 240, 426, 44
    cell_h = th + hh
    sheet = np.full((rows * cell_h + (rows - 1) * 8, cols * tw + (cols - 1) * 8, 3), (18, 20, 24), dtype=np.uint8)

    act4_frames: list[tuple[str, np.ndarray]] = []
    for idx0, ct in enumerate(cuts):
        t0 = float(ct["out_start_sec"])
        t1 = float(ct["out_end_sec"])
        dur = float(ct["duration_sec"])
        mid_t = t0 + dur * 0.48
        frm = _grab_frame_at_sec(cap, fps, mid_t)
        thumb = cv2.resize(frm, (tw, th), interpolation=cv2.INTER_AREA)
        hdr = np.full((hh, tw, 3), (30, 34, 42), dtype=np.uint8)
        c_no = int(ct["cut_index"])
        g_short = "R80" if ct.get("grammar") == "spatial_3d_arrow_diorama" else ("BRAIN" if ct.get("grammar") == "brain_simulator_3d" else "2.5D")
        lbl = f"#{c_no:02d} {g_short} {dur:.2f}s"
        color = (80, 120, 255) if g_short == "R80" else ((255, 216, 39) if g_short == "BRAIN" else (240, 240, 240))
        cv2.putText(hdr, lbl, (8, 29), cv2.FONT_HERSHEY_SIMPLEX, 0.56, color, 2, cv2.LINE_AA)
        cell = np.vstack([hdr, thumb])
        r_i, c_i = divmod(idx0, cols)
        y_off = r_i * (cell_h + 8)
        x_off = c_i * (tw + 8)
        sheet[y_off : y_off + cell_h, x_off : x_off + tw] = cell

        if c_no in (9, 10, 11, 12):
            titles = {
                9: f"Cut 09 ({dur:.2f}s): London Eye Ascend",
                10: f"Cut 10 ({dur:.2f}s): Taxi #FF2525 Zigzag",
                11: f"Cut 11 ({dur:.2f}s): Red Bus Stop Ascend",
                12: f"Cut 12 ({dur:.2f}s): Bus #FF2525 Straight",
            }
            act4_frames.append((titles[c_no], frm))

    cap.release()
    proof_18 = ART_DIR / "ep09_v2_18cut_proof.jpg"
    cv2.imwrite(str(proof_18), sheet, [int(cv2.IMWRITE_JPEG_QUALITY), 92])

    # 2. Act 4 4-cut assembled MP4 comparison sheet
    a_tiles = []
    for ttl, frm in act4_frames:
        t_im = cv2.resize(frm, (405, 720), interpolation=cv2.INTER_AREA)
        t_hd = np.full((52, 405, 3), (24, 26, 32), dtype=np.uint8)
        cv2.putText(t_hd, ttl, (10, 34), cv2.FONT_HERSHEY_SIMPLEX, 0.54, (255, 255, 255), 2, cv2.LINE_AA)
        a_tiles.append(np.vstack([t_hd, t_im]))
    sep = np.full((772, 12, 3), (16, 18, 22), dtype=np.uint8)
    act4_grid = np.hstack([a_tiles[0], sep, a_tiles[1], sep, a_tiles[2], sep, a_tiles[3]])
    proof_act4 = ART_DIR / "ep09_v2_taxi_vs_bus_3d_arrows.jpg"
    cv2.imwrite(str(proof_act4), act4_grid, [int(cv2.IMWRITE_JPEG_QUALITY), 93])
    print("Saved proofs:", proof_18, proof_act4)

    # 3. Generate viewer strips + initial CV report via posthoc-qa (expected non-zero before semantic signoff)
    subprocess.run(
        ["/home/canadaofbin/hermes-venv/bin/python", "-X", "utf8", "main.py", "posthoc-qa", "--project", PROJECT_ID],
        check=False,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
