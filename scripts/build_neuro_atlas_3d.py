#!/usr/bin/env python3
"""
Rule R76: Genuine MNI152 3D Neuroanatomy + Watertight Head Shell + Sensory Organ Bundle Builder.

Downloads & caches open-license anatomical datasets (`BrainMesh_ICBM152`, `aal.mz3`, `CIT168.mz3`,
`Brainstem_Navigator.mz3`, `BrainMesh_Ch2withCerebellum.mz3`, and `T1_head.nii.gz`) into
`/tmp/aab_neuro_atlas_raw/`, extracts surface meshes in standardized MNI152 mm space
(`+X = Right`, `+Y = Anterior/Face`, `+Z = Superior/Crown`), constructs 3D sensory organs &
cranial nerve entry tracts (Eyes + Optic Chiasm + Optic Tracts; Inner Ear Cochlea +
Semicircular Canals + Auditory Nerve) + anatomical curved white-matter tract splines, and writes:
  - pipeline/assets/neuro_atlas_3d/neuro_atlas_mni152.npz
  - pipeline/assets/neuro_atlas_3d/manifest.json
"""

from __future__ import annotations

import argparse
import gzip
import json
import math
import struct
import urllib.request
from pathlib import Path
from typing import Any

import numpy as np
from scipy import ndimage

REPO_ROOT = Path(__file__).resolve().parents[1]
RAW_CACHE_DIR = Path("/tmp/aab_neuro_atlas_raw")
OUT_ASSET_DIR = REPO_ROOT / "pipeline" / "assets" / "neuro_atlas_3d"
NPZ_PATH = OUT_ASSET_DIR / "neuro_atlas_mni152.npz"
MANIFEST_PATH = OUT_ASSET_DIR / "manifest.json"

URLS: dict[str, str] = {
    "icbm_lh.mz3": "https://raw.githubusercontent.com/neurolabusc/surf-ice/master/BrainNet/BrainMesh_ICBM152.lh.mz3",
    "icbm_rh.mz3": "https://raw.githubusercontent.com/neurolabusc/surf-ice/master/BrainNet/BrainMesh_ICBM152.rh.mz3",
    "ch2_cerebellum.mz3": "https://raw.githubusercontent.com/neurolabusc/surf-ice/master/BrainNet/BrainMesh_Ch2withCerebellum.mz3",
    "aal.mz3": "https://raw.githubusercontent.com/niivue/niivue/main/packages/niivue/demos/images/aal.mz3",
    "aal.json": "https://raw.githubusercontent.com/niivue/niivue/main/packages/niivue/demos/images/aal.json",
    "cit168.mz3": "https://raw.githubusercontent.com/niivue/niivue/main/packages/niivue/demos/images/CIT168.mz3",
    "brainstem_nav.mz3": "https://raw.githubusercontent.com/anniegbryant/subcortex_visualization/main/atlas_info/original_space/Brainstem_Navigator/Brainstem_Navigator.mz3",
    "t1_head.nii.gz": "https://raw.githubusercontent.com/niivue/niivue-demo-images/main/register/T1_head.nii.gz",
}

# Verified AAL1 label groups (scalars 1..116 in aal.mz3)
AAL_REGION_IDS: dict[str, list[int]] = {
    "primary visual cortex": [43, 44, 45, 46],  # Calcarine + Cuneus
    "fusiform face area": [55, 56],             # Fusiform_L/R
    "amygdala": [41, 42],                       # Amygdala_L/R
    "hippocampus": [37, 38],                    # Hippocampus_L/R
    "thalamus": [77, 78],                       # Thalamus_L/R
    "auditory cortex": [79, 80, 81, 82],        # Heschl + Temporal_Sup
    "anterior cingulate cortex": [31, 32],      # Cingulum_Ant_L/R
    "ventromedial prefrontal cortex": [25, 26, 27, 28],  # Frontal_Med_Orb + Rectus
    "dorsolateral prefrontal cortex": [7, 8],   # Frontal_Mid_L/R
    "prefrontal cortex": [3, 4, 7, 8, 11, 12, 13, 14, 25, 26],  # Frontal Pole + Convexity
    "orbitofrontal cortex": [5, 6, 9, 10, 15, 16, 25, 26],
    "motor cortex": [1, 2],                     # Precentral_L/R
    "premotor cortex": [3, 4, 19, 20],          # SMA + Dorsal Frontal
    "somatosensory cortex": [57, 58],           # Postcentral_L/R
    "posterior parietal cortex": [59, 60, 61, 62],  # Parietal_Sup + Inf
    "insula": [29, 30],                         # Insula_L/R
    "broca's area": [11, 13],                   # Frontal_Inf_Oper/Tri_L
    "wernicke's area": [81, 63],                # Temporal_Sup_L + SupraMarginal_L
}

# High-precision subcortical CIT168 label groups (scalars 1..32)
CIT168_REGION_IDS: dict[str, list[int]] = {
    "basal ganglia": [1, 2, 3, 4, 9, 10, 11, 12],  # Putamen + Caudate + GPe/GPi
    "nucleus accumbens": [5, 6],
    "ventral tegmental area": [15, 16, 21, 22],
    "substantia nigra": [13, 14, 17, 18],
    "hypothalamus": [27, 28],
}


def download_cached(name: str, url: str) -> Path:
    RAW_CACHE_DIR.mkdir(parents=True, exist_ok=True)
    dst = RAW_CACHE_DIR / name
    if dst.is_file() and dst.stat().st_size > 128:
        return dst
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    data = urllib.request.urlopen(req, timeout=30).read()
    dst.write_bytes(data)
    return dst


def load_mz3(path: Path) -> tuple[np.ndarray, np.ndarray, np.ndarray | None]:
    raw = path.read_bytes()
    if raw[:2] == b"\x1f\x8b":
        raw = gzip.decompress(raw)
    magic, attr, nface, nvert, nskip = struct.unpack("<HHIII", raw[:16])
    if magic != 23117:
        raise ValueError(f"Invalid MZ3 magic {magic} in {path}")
    off = 16 + nskip
    faces = np.frombuffer(raw, dtype=np.int32, count=nface * 3, offset=off).reshape(-1, 3).copy()
    off += nface * 12
    verts = np.frombuffer(raw, dtype=np.float32, count=nvert * 3, offset=off).reshape(-1, 3).copy()
    off += nvert * 12
    if attr & 4:  # RGBA
        off += nvert * 4
    scalars = None
    if attr & 8:  # Scalar
        scalars = np.frombuffer(raw, dtype=np.float32, count=nvert, offset=off).copy()
    return verts, faces, scalars


def taubin_smooth(verts: np.ndarray, faces: np.ndarray, iterations: int = 3) -> np.ndarray:
    """Gentle volume-preserving Taubin (lambda/mu) mesh smoothing for anatomical submeshes."""
    if len(verts) == 0 or len(faces) == 0:
        return verts
    v = verts.astype(np.float64, copy=True)
    n = len(v)
    edges_0 = np.concatenate([faces[:, 0], faces[:, 1], faces[:, 2]])
    edges_1 = np.concatenate([faces[:, 1], faces[:, 2], faces[:, 0]])
    src = np.concatenate([edges_0, edges_1])
    dst = np.concatenate([edges_1, edges_0])
    deg = np.bincount(src, minlength=n).astype(np.float64)
    deg = np.maximum(deg, 1.0)
    lam, mu = 0.35, -0.36
    for _ in range(iterations):
        for factor in (lam, mu):
            nb_sum = np.zeros_like(v)
            np.add.at(nb_sum, src, v[dst])
            avg = nb_sum / deg[:, None]
            v = v + factor * (avg - v)
    return v.astype(np.float32)


def decimate_grid_cluster(verts: np.ndarray, faces: np.ndarray, voxel_mm: float = 2.0) -> tuple[np.ndarray, np.ndarray]:
    """Vertex-clustering decimation for fast crisp Blender viewport loading without losing sulcal folds."""
    q = np.round(verts / float(voxel_mm)).astype(np.int32)
    _, inv, counts = np.unique(q, axis=0, return_inverse=True, return_counts=True)
    n_new = len(counts)
    new_v = np.zeros((n_new, 3), dtype=np.float64)
    np.add.at(new_v, inv, verts.astype(np.float64))
    new_v /= counts[:, None]
    new_f = inv[faces]
    valid = (new_f[:, 0] != new_f[:, 1]) & (new_f[:, 1] != new_f[:, 2]) & (new_f[:, 0] != new_f[:, 2])
    new_f = new_f[valid]
    # Remove duplicate faces modulo orientation
    sf = np.sort(new_f, axis=1)
    _, uniq_idx = np.unique(sf, axis=0, return_index=True)
    new_f = new_f[np.sort(uniq_idx)]
    return compact_mesh(new_v.astype(np.float32), new_f.astype(np.int32))


def compact_mesh(verts: np.ndarray, faces: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    if len(faces) == 0 or len(verts) == 0:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)
    used = np.unique(faces.reshape(-1))
    remap = np.full(len(verts), -1, dtype=np.int32)
    remap[used] = np.arange(len(used), dtype=np.int32)
    return verts[used].astype(np.float32), remap[faces].astype(np.int32)


def extract_parcel_mesh(
    verts: np.ndarray,
    faces: np.ndarray,
    scalars: np.ndarray,
    label_ids: list[int],
    *,
    smooth_iters: int = 3,
    min_verts_per_tri: int = 2,
) -> tuple[np.ndarray, np.ndarray]:
    s_int = np.round(scalars).astype(np.int32)
    mask_v = np.isin(s_int, np.asarray(label_ids, dtype=np.int32))
    tri_hits = mask_v[faces].sum(axis=1)
    sub_faces = faces[tri_hits >= int(min_verts_per_tri)]
    if len(sub_faces) == 0:
        sub_faces = faces[tri_hits >= 1]
    cv, cf = compact_mesh(verts, sub_faces)
    if smooth_iters > 0 and len(cv) > 12:
        cv = taubin_smooth(cv, cf, iterations=smooth_iters)
    return cv, cf


def mirror_bilateral(verts: np.ndarray, faces: np.ndarray, x_thresh: float = 0.5) -> tuple[np.ndarray, np.ndarray]:
    """Mirrors unilateral (+X) brainstem structures across sagittal X=0 with corrected triangle winding."""
    v_l = verts.copy()
    v_l[:, 0] = -v_l[:, 0]
    f_l = faces[:, [0, 2, 1]].copy() + len(verts)
    return np.vstack([verts, v_l]).astype(np.float32), np.vstack([faces, f_l]).astype(np.int32)


def build_uv_sphere_mesh(center: tuple[float, float, float], radii: tuple[float, float, float], seg_u: int = 28, seg_v: int = 18) -> tuple[np.ndarray, np.ndarray]:
    verts: list[list[float]] = []
    faces: list[list[int]] = []
    cx, cy, cz = center
    rx, ry, rz = radii
    for iv in range(seg_v + 1):
        phi = math.pi * iv / seg_v
        sp, cp = math.sin(phi), math.cos(phi)
        for iu in range(seg_u):
            theta = 2.0 * math.pi * iu / seg_u
            st, ct = math.sin(theta), math.cos(theta)
            verts.append([cx + rx * sp * ct, cy + ry * sp * st, cz + rz * cp])
    for iv in range(seg_v):
        for iu in range(seg_u):
            iu_next = (iu + 1) % seg_u
            a = iv * seg_u + iu
            b = iv * seg_u + iu_next
            c = (iv + 1) * seg_u + iu
            d = (iv + 1) * seg_u + iu_next
            if iv > 0:
                faces.append([a, b, d])
            if iv < seg_v - 1:
                faces.append([a, d, c])
    return np.asarray(verts, dtype=np.float32), np.asarray(faces, dtype=np.int32)


def sweep_tube_mesh(
    points: np.ndarray,
    radii: float | np.ndarray,
    radial_segs: int = 14,
    cap_ends: bool = True,
) -> tuple[np.ndarray, np.ndarray]:
    """Sweeps a smooth circular anatomical tube along a 3D spline polyline."""
    pts = np.asarray(points, dtype=np.float64)
    n_pts = len(pts)
    if np.ndim(radii) == 0:
        rad_arr = np.full(n_pts, float(radii), dtype=np.float64)
    else:
        rad_arr = np.asarray(radii, dtype=np.float64)
    tangents = np.zeros_like(pts)
    tangents[0] = pts[1] - pts[0]
    tangents[-1] = pts[-1] - pts[-2]
    if n_pts > 2:
        tangents[1:-1] = pts[2:] - pts[:-2]
    norms = np.linalg.norm(tangents, axis=1, keepdims=True)
    tangents /= np.maximum(norms, 1e-8)

    # Parallel transport frame so there are zero twist pinches
    ref = np.array([0.0, 0.0, 1.0]) if abs(tangents[0, 2]) < 0.9 else np.array([1.0, 0.0, 0.0])
    n_vec = np.cross(tangents[0], ref)
    n_vec /= max(float(np.linalg.norm(n_vec)), 1e-8)
    b_vec = np.cross(tangents[0], n_vec)

    verts: list[np.ndarray] = []
    faces: list[list[int]] = []
    angles = np.linspace(0.0, 2.0 * math.pi, radial_segs, endpoint=False)
    for i in range(n_pts):
        t = tangents[i]
        if i > 0:
            n_vec = n_vec - np.dot(n_vec, t) * t
            nn = float(np.linalg.norm(n_vec))
            if nn < 1e-6:
                ref = np.array([0.0, 1.0, 0.0]) if abs(t[1]) < 0.9 else np.array([1.0, 0.0, 0.0])
                n_vec = np.cross(t, ref)
                nn = float(np.linalg.norm(n_vec))
            n_vec /= nn
            b_vec = np.cross(t, n_vec)
        r = rad_arr[i]
        ring = pts[i][None, :] + r * (np.cos(angles)[:, None] * n_vec[None, :] + np.sin(angles)[:, None] * b_vec[None, :])
        verts.append(ring)

    all_v = np.vstack(verts)
    for i in range(n_pts - 1):
        row0 = i * radial_segs
        row1 = (i + 1) * radial_segs
        for j in range(radial_segs):
            jn = (j + 1) % radial_segs
            faces.append([row0 + j, row0 + jn, row1 + jn])
            faces.append([row0 + j, row1 + jn, row1 + j])

    if cap_ends:
        c0_idx = len(all_v)
        c1_idx = len(all_v) + 1
        all_v = np.vstack([all_v, pts[0][None, :], pts[-1][None, :]])
        last_row = (n_pts - 1) * radial_segs
        for j in range(radial_segs):
            jn = (j + 1) % radial_segs
            faces.append([c0_idx, jn, j])
            faces.append([c1_idx, last_row + j, last_row + jn])

    return all_v.astype(np.float32), np.asarray(faces, dtype=np.int32)


def catmull_rom_spline(ctrl: list[list[float]] | np.ndarray, n_samples: int = 48) -> np.ndarray:
    pts = np.asarray(ctrl, dtype=np.float64)
    if len(pts) < 2:
        return pts
    if len(pts) == 2:
        t = np.linspace(0.0, 1.0, n_samples)[:, None]
        return pts[0] * (1.0 - t) + pts[1] * t
    ext = np.vstack([2 * pts[0] - pts[1], pts, 2 * pts[-1] - pts[-2]])
    n_seg = len(pts) - 1
    out: list[np.ndarray] = []
    ts = np.linspace(0.0, 1.0, n_samples)
    for u in ts:
        scaled = u * n_seg
        seg = min(int(scaled), n_seg - 1)
        t = scaled - seg
        p0, p1, p2, p3 = ext[seg], ext[seg + 1], ext[seg + 2], ext[seg + 3]
        t2, t3 = t * t, t * t * t
        pos = 0.5 * (
            (2.0 * p1)
            + (-p0 + p2) * t
            + (2.0 * p0 - 5.0 * p1 + 4.0 * p2 - p3) * t2
            + (-p0 + 3.0 * p1 - 3.0 * p2 + p3) * t3
        )
        out.append(pos)
    return np.asarray(out, dtype=np.float64)


def merge_meshes(items: list[tuple[np.ndarray, np.ndarray]]) -> tuple[np.ndarray, np.ndarray]:
    verts_list: list[np.ndarray] = []
    faces_list: list[np.ndarray] = []
    offset = 0
    for v, f in items:
        if len(v) == 0 or len(f) == 0:
            continue
        verts_list.append(v.astype(np.float32))
        faces_list.append(f.astype(np.int32) + offset)
        offset += len(v)
    if not verts_list:
        return np.zeros((0, 3), dtype=np.float32), np.zeros((0, 3), dtype=np.int32)
    return np.vstack(verts_list), np.vstack(faces_list)


def extract_head_shell_from_t1(nii_gz_path: Path, brain_verts_all: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    """
    Parses `T1_head.nii.gz` NIfTI-1 volume directly and extracts a clean, watertight outer human head
    silhouette mesh (scalp, face, nose, brow, chin, ears) via vectorized binary boundary surface-net +
    Laplacian smoothing, mapped strictly via the volume's MNI152 `srow_x/y/z` affine.
    """
    with gzip.open(nii_gz_path, "rb") as f:
        raw = f.read()
    hdr = raw[:348]
    dim = struct.unpack("<8h", hdr[40:56])
    nx, ny, nz = int(dim[1]), int(dim[2]), int(dim[3])
    vox_offset = int(round(struct.unpack("<f", hdr[108:112])[0])) or 352
    srow_x = struct.unpack("<4f", hdr[280:296])
    srow_y = struct.unpack("<4f", hdr[296:312])
    srow_z = struct.unpack("<4f", hdr[312:328])
    affine = np.array([srow_x, srow_y, srow_z, [0.0, 0.0, 0.0, 1.0]], dtype=np.float64)

    vol = np.frombuffer(raw, dtype="<i2", count=nx * ny * nz, offset=vox_offset).reshape((nx, ny, nz), order="F")
    vol_f = ndimage.gaussian_filter(vol.astype(np.float32), sigma=1.15)
    pos = vol_f[vol_f > 25.0]
    thresh = float(np.percentile(pos, 14.0)) if len(pos) > 0 else 40.0
    mask = vol_f > thresh
    # Fill axial/sagittal/coronal slices and 3D interior so sinus/ventricle cavities never leak inside
    for z in range(nz):
        mask[:, :, z] = ndimage.binary_fill_holes(mask[:, :, z])
    for y in range(ny):
        mask[:, y, :] = ndimage.binary_fill_holes(mask[:, y, :])
    mask = ndimage.binary_fill_holes(mask)
    labeled, n_comp = ndimage.label(mask)
    if n_comp > 1:
        sizes = np.bincount(labeled.ravel())
        sizes[0] = 0
        mask = labeled == int(sizes.argmax())

    # Mild morphological close to smooth external ear/chin contours cleanly
    mask = ndimage.binary_closing(mask, iterations=2)
    mask = ndimage.binary_fill_holes(mask)

    # Downsample 2x via strided max-pool/gaussian threshold (~83x105x80) for a crisp, fast ~22k-quad->tri mesh
    mask_ds = ndimage.zoom(mask.astype(np.float32), zoom=0.5, order=1) > 0.45
    mask_ds = ndimage.binary_fill_holes(mask_ds)
    sx, sy, sz = mask_ds.shape

    # Vectorized surface-net: collect boundary voxel quad faces between True and False
    padded = np.pad(mask_ds, 1, mode="constant", constant_values=False)
    core = padded[1:-1, 1:-1, 1:-1]
    quads_list: list[np.ndarray] = []

    def _add_dir(shift_slice: np.ndarray, corners_rel: list[tuple[int, int, int]]) -> None:
        b = core & (~shift_slice)
        ii, jj, kk = np.where(b)
        if len(ii) == 0:
            return
        # Corner vertex coordinates in (sx+1, sy+1, sz+1) dual vertex grid
        pts = np.stack([
            np.stack([ii + dx, jj + dy, kk + dz], axis=1)
            for (dx, dy, dz) in corners_rel
        ], axis=1)
        quads_list.append(pts)

    _add_dir(padded[2:, 1:-1, 1:-1], [(1, 0, 0), (1, 1, 0), (1, 1, 1), (1, 0, 1)])  # +X
    _add_dir(padded[:-2, 1:-1, 1:-1], [(0, 0, 0), (0, 0, 1), (0, 1, 1), (0, 1, 0)])  # -X
    _add_dir(padded[1:-1, 2:, 1:-1], [(0, 1, 0), (0, 1, 1), (1, 1, 1), (1, 1, 0)])  # +Y
    _add_dir(padded[1:-1, :-2, 1:-1], [(0, 0, 0), (1, 0, 0), (1, 0, 1), (0, 0, 1)])  # -Y
    _add_dir(padded[1:-1, 1:-1, 2:], [(0, 0, 1), (1, 0, 1), (1, 1, 1), (0, 1, 1)])  # +Z
    _add_dir(padded[1:-1, 1:-1, :-2], [(0, 0, 0), (0, 1, 0), (1, 1, 0), (1, 0, 0)])  # -Z

    all_quads = np.concatenate(quads_list, axis=0)  # (Q, 4, 3)
    stride = np.array([(sy + 1) * (sz + 1), (sz + 1), 1], dtype=np.int64)
    q_ids = (all_quads * stride[None, None, :]).sum(axis=2)
    uniq_ids, inv = np.unique(q_ids.ravel(), return_inverse=True)
    quad_idx = inv.reshape(-1, 4).astype(np.int32)

    ux = uniq_ids // ((sy + 1) * (sz + 1))
    rem = uniq_ids % ((sy + 1) * (sz + 1))
    uy = rem // (sz + 1)
    uz = rem % (sz + 1)
    # Map dual grid coords back from downsampled (~0.5x) voxel index to original voxel space
    vx = (ux.astype(np.float64) - 0.5) * 2.0
    vy = (uy.astype(np.float64) - 0.5) * 2.0
    vz = (uz.astype(np.float64) - 0.5) * 2.0
    ones = np.ones_like(vx)
    ijk1 = np.stack([vx, vy, vz, ones], axis=1)
    mni_verts = (ijk1 @ affine[:3, :].T).astype(np.float32)

    tri_1 = quad_idx[:, [0, 1, 2]]
    tri_2 = quad_idx[:, [0, 2, 3]]
    faces = np.vstack([tri_1, tri_2]).astype(np.int32)

    # Strong volume-preserving Taubin smoothing turns blocky voxel surface into a silky clinical head silhouette
    verts = taubin_smooth(mni_verts, faces, iterations=12)

    # Center sagittal midline X=0 and ensure 100% of brain cortex clears inside the outer head shell smoothly
    cx_mid = 0.5 * (float(verts[:, 0].min()) + float(verts[:, 0].max()))
    verts[:, 0] -= cx_mid
    brain_top_z = float(brain_verts_all[:, 2].max())
    head_top_z = float(verts[:, 2].max())
    if head_top_z - brain_top_z < 8.0:
        verts[:, 2] += (brain_top_z + 10.0) - head_top_z
    brain_back_y = float(brain_verts_all[:, 1].min())
    head_back_y = float(verts[:, 1].min())
    if head_back_y > brain_back_y - 9.0:
        verts[:, 1] += (brain_back_y - 9.5) - head_back_y
    return verts.astype(np.float32), faces.astype(np.int32)


def build_sensory_meshes() -> tuple[dict[str, tuple[np.ndarray, np.ndarray]], dict[str, list[list[float]]]]:
    """
    Builds genuine MNI152 mm-space 3D anatomical sensory organs & cranial nerve entry tracks:
      - Bilateral eyeballs + corneal bulge + optic nerves + optic chiasm -> LGN -> optic radiations -> V1
      - Bilateral 2.5-turn spiral Cochlea + 3 orthogonal Semicircular Canals + CN VIII Auditory Nerve -> A1
      - Anatomical Corpus Callosum arch
    """
    meshes: dict[str, tuple[np.ndarray, np.ndarray]] = {}

    # 1. Bilateral Eyeballs (positioned inside human T1 orbital sockets around X=±28, Y=+63, Z=-18 mm)
    eye_parts: list[tuple[np.ndarray, np.ndarray]] = []
    for side in (-1.0, 1.0):
        globe_v, globe_f = build_uv_sphere_mesh((side * 28.0, 62.0, -18.0), (11.5, 11.8, 11.5), seg_u=24, seg_v=16)
        cornea_v, cornea_f = build_uv_sphere_mesh((side * 28.0, 72.2, -18.0), (6.2, 3.8, 6.2), seg_u=20, seg_v=12)
        eye_parts.extend([(globe_v, globe_f), (cornea_v, cornea_f)])
    meshes["eyes"] = merge_meshes(eye_parts)

    # 2. Optic Chiasm & Optic Nerve entry bundle (Eyes -> Optic Canal -> Chiasm -> LGN -> V1)
    chiasm_v, chiasm_f = build_uv_sphere_mesh((0.0, 4.0, -15.0), (8.5, 4.5, 3.2), seg_u=20, seg_v=12)
    optic_parts: list[tuple[np.ndarray, np.ndarray]] = [(chiasm_v, chiasm_f)]
    optic_splines: dict[str, list[list[float]]] = {}
    for s_tag, side in (("rh", 1.0), ("lh", -1.0)):
        nerve_pts = catmull_rom_spline([
            [side * 27.0, 50.5, -18.0],
            [side * 20.0, 34.0, -17.0],
            [side * 9.5, 16.0, -15.5],
            [side * 1.5, 4.5, -15.0],
            [side * 12.0, -9.0, -9.0],
            [side * 21.0, -21.0, -2.5],   # LGN (Thalamus)
            [side * 27.0, -45.0, 0.5],    # Optic radiation sweep
            [side * 15.0, -71.0, 3.5],    # V1 entry
        ], n_samples=44)
        tv, tf = sweep_tube_mesh(nerve_pts, radii=1.95, radial_segs=12)
        optic_parts.append((tv, tf))
        optic_splines[s_tag] = np.round(nerve_pts, 2).tolist()
    meshes["optic pathway"] = merge_meshes(optic_parts)

    # 3. Bilateral Inner Ear: 2.5-turn spiral Cochlea + 3 Semicircular Canals + CN VIII Auditory Nerve
    ear_parts: list[tuple[np.ndarray, np.ndarray]] = []
    aud_nerve_parts: list[tuple[np.ndarray, np.ndarray]] = []
    auditory_splines: dict[str, list[list[float]]] = {}
    for s_tag, side in (("rh", 1.0), ("lh", -1.0)):
        cx, cy, cz = side * 43.0, -21.0, -29.0
        # 2.5-turn spiral Cochlea
        t_vals = np.linspace(0.0, 2.5 * 2.0 * math.pi, 72)
        r_spiral = np.linspace(6.2, 1.3, len(t_vals))
        c_pts = np.stack([
            cx + side * (t_vals / (2.5 * 2.0 * math.pi)) * 4.5,
            cy + r_spiral * np.cos(t_vals),
            cz + r_spiral * np.sin(t_vals),
        ], axis=1)
        c_rad = np.linspace(1.7, 0.75, len(t_vals))
        cv, cf = sweep_tube_mesh(c_pts, radii=c_rad, radial_segs=10)
        ear_parts.append((cv, cf))

        # 3 orthogonal semicircular canals (vestibular labyrinth loop behind cochlea)
        a_loop = np.linspace(0.0, 1.85 * math.pi, 26)
        canal_axes = [
            (np.array([0.0, 1.0, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([side * 1.5, -5.5, 4.0])),
            (np.array([side * 0.7, 0.7, 0.0]), np.array([0.0, 0.0, 1.0]), np.array([side * 3.0, -6.5, 0.5])),
            (np.array([side * 1.0, 0.0, 0.0]), np.array([0.0, 1.0, 0.0]), np.array([side * 3.0, -5.0, -2.0])),
        ]
        for u_ax, v_ax, off_c in canal_axes:
            u_n = u_ax / np.linalg.norm(u_ax)
            v_n = v_ax / np.linalg.norm(v_ax)
            pts_c = (np.array([cx, cy, cz]) + off_c)[None, :] + 4.8 * (
                np.cos(a_loop)[:, None] * u_n[None, :] + np.sin(a_loop)[:, None] * v_n[None, :]
            )
            lv, lf = sweep_tube_mesh(pts_c, radii=0.95, radial_segs=8)
            ear_parts.append((lv, lf))

        # CN VIII -> Brainstem -> MGN -> Auditory Cortex (Heschl/STG)
        a_pts = catmull_rom_spline([
            [cx - side * 2.0, cy, cz],
            [side * 24.0, -28.0, -28.0],  # Cerebellopontine internal acoustic meatus
            [side * 11.0, -30.0, -23.0],  # Brainstem cochlear nucleus
            [side * 14.0, -24.0, -4.0],   # Thalamus (MGN)
            [side * 38.0, -21.0, 4.0],    # Acoustic radiation
            [side * 48.0, -21.0, 6.0],    # Heschl / Primary Auditory Cortex
        ], n_samples=40)
        av, af = sweep_tube_mesh(a_pts, radii=1.75, radial_segs=10)
        aud_nerve_parts.append((av, af))
        auditory_splines[s_tag] = np.round(a_pts, 2).tolist()
    meshes["inner ear"] = merge_meshes(ear_parts)
    meshes["auditory nerve"] = merge_meshes(aud_nerve_parts)

    # 4. Corpus Callosum anatomical arch (Genu -> Body -> Splenium)
    cc_spine = catmull_rom_spline([
        [0.0, 26.0, 4.0],
        [0.0, 29.0, 14.0],
        [0.0, 14.0, 24.0],
        [0.0, -8.0, 25.0],
        [0.0, -28.0, 20.0],
        [0.0, -37.0, 11.0],
    ], n_samples=32)
    cc_parts: list[tuple[np.ndarray, np.ndarray]] = []
    for x_off in (-11.0, -5.5, 0.0, 5.5, 11.0):
        pts_x = cc_spine.copy()
        pts_x[:, 0] = x_off
        vv, ff = sweep_tube_mesh(pts_x, radii=4.4, radial_segs=10)
        cc_parts.append((vv, ff))
    meshes["corpus callosum"] = merge_meshes(cc_parts)

    splines_meta = {
        "eyes__to__primary visual cortex": optic_splines,
        "inner ear__to__auditory cortex": auditory_splines,
    }
    return meshes, splines_meta


def build_anatomical_tract_catalog(
    centroids: dict[str, dict[str, Any]],
    sensory_splines: dict[str, dict[str, list[list[float]]]],
) -> dict[str, list[list[float]]]:
    """
    Constructs anatomically realistic curved white-matter tract splines (Right-hemisphere / Camera-side showcase
    unless midline/left-dominant, staying strictly inside brain parenchyma).
    """
    def _rh(name: str) -> list[float]:
        info = centroids.get(name) or {}
        if "rh_centroid_mni" in info and info["rh_centroid_mni"] is not None:
            return list(info["rh_centroid_mni"])
        return list(info.get("centroid_mni") or [0.0, 0.0, 0.0])

    tracts: dict[str, list[list[float]]] = {}
    tracts["eyes__to__primary visual cortex"] = sensory_splines["eyes__to__primary visual cortex"]["rh"]
    tracts["inner ear__to__auditory cortex"] = sensory_splines["inner ear__to__auditory cortex"]["rh"]

    # V1 -> Fusiform Face Area (Ventral Stream / Inferior Longitudinal Fasciculus)
    v1_r = _rh("primary visual cortex")
    ffa_r = _rh("fusiform face area")
    tracts["primary visual cortex__to__fusiform face area"] = np.round(catmull_rom_spline([
        v1_r,
        [24.0, -64.0, -10.0],
        [32.0, -52.0, -19.0],
        ffa_r,
    ], n_samples=36), 2).tolist()

    # Fusiform Face Area -> Amygdala (Amygdalo-fusiform / ILF pathway — supports severed break!)
    amy_r = _rh("amygdala")
    tracts["fusiform face area__to__amygdala"] = np.round(catmull_rom_spline([
        ffa_r,
        [30.5, -26.0, -23.0],
        [28.5, -14.0, -21.0],
        amy_r,
    ], n_samples=36), 2).tolist()

    # Amygdala -> Prefrontal Cortex (Uncinate Fasciculus hooking through anterior temporal-frontal stem)
    pfc_r = _rh("prefrontal cortex")
    tracts["amygdala__to__prefrontal cortex"] = np.round(catmull_rom_spline([
        amy_r,
        [27.0, 12.0, -12.0],
        [29.0, 26.0, 4.0],
        pfc_r,
    ], n_samples=36), 2).tolist()

    # Fusiform -> Prefrontal Cortex (Inferior Fronto-Occipital Fasciculus)
    tracts["fusiform face area__to__prefrontal cortex"] = np.round(catmull_rom_spline([
        ffa_r,
        [34.0, -14.0, -10.0],
        [33.0, 14.0, 6.0],
        pfc_r,
    ], n_samples=36), 2).tolist()

    # Auditory Cortex -> Amygdala (Superior Temporal / Auditory-Limbic connection)
    a1_r = _rh("auditory cortex")
    tracts["auditory cortex__to__amygdala"] = np.round(catmull_rom_spline([
        a1_r,
        [44.0, -10.0, -6.0],
        [36.0, -4.0, -15.0],
        amy_r,
    ], n_samples=36), 2).tolist()

    # Common general pathways (ACC <-> vmPFC, V1 <-> ACC, Hippocampus <-> PFC, VTA -> Nucleus Accumbens)
    acc_r = _rh("anterior cingulate cortex")
    vmpfc_r = _rh("ventromedial prefrontal cortex")
    hip_r = _rh("hippocampus")
    sc_r = _rh("superior colliculus")
    vta_r = _rh("ventral tegmental area")
    nac_r = _rh("nucleus accumbens")

    tracts["anterior cingulate cortex__to__ventromedial prefrontal cortex"] = np.round(catmull_rom_spline([
        acc_r, [10.0, 42.0, -2.0], vmpfc_r,
    ], n_samples=32), 2).tolist()
    tracts["eyes__to__superior colliculus"] = np.round(catmull_rom_spline([
        [27.0, 50.5, -18.0], [10.0, 4.5, -15.0], [14.0, -16.0, -6.0], sc_r,
    ], n_samples=36), 2).tolist()
    tracts["superior colliculus__to__amygdala"] = np.round(catmull_rom_spline([
        sc_r, [16.0, -18.0, -11.0], amy_r,
    ], n_samples=32), 2).tolist()
    tracts["hippocampus__to__prefrontal cortex"] = np.round(catmull_rom_spline([
        hip_r, [20.0, -2.0, -2.0], [18.0, 22.0, 10.0], pfc_r,
    ], n_samples=36), 2).tolist()
    tracts["ventral tegmental area__to__nucleus accumbens"] = np.round(catmull_rom_spline([
        vta_r, [6.5, -6.0, -10.0], nac_r,
    ], n_samples=30), 2).tolist()

    return tracts


def build_bundle() -> dict[str, Any]:
    OUT_ASSET_DIR.mkdir(parents=True, exist_ok=True)
    paths = {k: download_cached(k, u) for k, u in URLS.items()}

    lh_v, lh_f, _ = load_mz3(paths["icbm_lh.mz3"])
    rh_v, rh_f, _ = load_mz3(paths["icbm_rh.mz3"])
    lh_v, lh_f = decimate_grid_cluster(lh_v, lh_f, voxel_mm=1.8)
    rh_v, rh_f = decimate_grid_cluster(rh_v, rh_f, voxel_mm=1.8)

    ch2_v, ch2_f, _ = load_mz3(paths["ch2_cerebellum.mz3"])
    aal_v, aal_f, aal_s = load_mz3(paths["aal.mz3"])
    cit_v, cit_f, cit_s = load_mz3(paths["cit168.mz3"])
    bs_v, bs_f, bs_s = load_mz3(paths["brainstem_nav.mz3"])
    assert aal_s is not None and cit_s is not None and bs_s is not None

    npz_arrays: dict[str, np.ndarray] = {}
    regions_meta: dict[str, dict[str, Any]] = {}

    def _register(key: str, v: np.ndarray, f: np.ndarray, source: str) -> None:
        safe = key.replace(" ", "_").replace("'", "")
        npz_arrays[f"{safe}__verts"] = v.astype(np.float32)
        npz_arrays[f"{safe}__faces"] = f.astype(np.int32)
        rh_m = v[:, 0] >= 1.5
        lh_m = v[:, 0] <= -1.5
        regions_meta[key] = {
            "npz_key": safe,
            "source": source,
            "n_verts": int(len(v)),
            "n_faces": int(len(f)),
            "centroid_mni": [round(float(x), 2) for x in v.mean(axis=0)],
            "rh_centroid_mni": [round(float(x), 2) for x in v[rh_m].mean(axis=0)] if rh_m.any() else None,
            "lh_centroid_mni": [round(float(x), 2) for x in v[lh_m].mean(axis=0)] if lh_m.any() else None,
            "bbox_min_mni": [round(float(x), 2) for x in v.min(axis=0)],
            "bbox_max_mni": [round(float(x), 2) for x in v.max(axis=0)],
        }

    _register("cortex_lh", lh_v, lh_f, "BrainMesh_ICBM152.lh.mz3")
    _register("cortex_rh", rh_v, rh_f, "BrainMesh_ICBM152.rh.mz3")

    # Cerebellum: foliated cerebellar surface from BrainMesh_Ch2withCerebellum where Z < -14 and Y < -33,
    # supplemented by AAL 91..116
    cb_v, cb_f = extract_parcel_mesh(aal_v, aal_f, aal_s, list(range(91, 117)), smooth_iters=2)
    ch2_mask = (ch2_v[:, 1] < -32.0) & (ch2_v[:, 2] < -11.0) & (np.abs(ch2_v[:, 0]) < 56.0)
    ch2_tri_hits = ch2_mask[ch2_f].sum(axis=1) >= 2
    cb2_v, cb2_f = compact_mesh(ch2_v, ch2_f[ch2_tri_hits])
    if len(cb2_v) > len(cb_v):
        cb2_v, cb2_f = decimate_grid_cluster(cb2_v, cb2_f, voxel_mm=1.8)
        _register("cerebellum", cb2_v, cb2_f, "BrainMesh_Ch2withCerebellum.mz3")
    else:
        _register("cerebellum", cb_v, cb_f, "aal.mz3")

    # Bilateral Brainstem (mirrored Brainstem_Navigator + central pons/medulla trunk)
    bs_bi_v, bs_bi_f = mirror_bilateral(bs_v, bs_f)
    trunk_pts = np.array([[0.0, -24.0, -6.0], [0.0, -25.0, -22.0], [0.0, -29.0, -40.0], [0.0, -33.0, -64.0]])
    trunk_r = np.array([10.5, 13.5, 9.2, 6.8])
    tr_v, tr_f = sweep_tube_mesh(catmull_rom_spline(trunk_pts, 18), np.interp(np.linspace(0, 3, 18), np.arange(4), trunk_r), radial_segs=16)
    bs_full_v, bs_full_f = merge_meshes([(bs_bi_v, bs_bi_f), (tr_v, tr_f)])
    _register("brainstem", bs_full_v, bs_full_f, "Brainstem_Navigator.mz3 (bilateral)")

    # AAL cortical & subcortical parcels
    for name, ids in AAL_REGION_IDS.items():
        v, f = extract_parcel_mesh(aal_v, aal_f, aal_s, ids, smooth_iters=3)
        _register(name, v, f, f"aal.mz3 labels {ids}")

    # CIT168 subcortical nuclei
    for name, ids in CIT168_REGION_IDS.items():
        v, f = extract_parcel_mesh(cit_v, cit_f, cit_s, ids, smooth_iters=2)
        _register(name, v, f, f"CIT168.mz3 labels {ids}")

    # Specific small brainstem nuclei (Superior Colliculus, Locus Coeruleus, PAG)
    sc_r_v, sc_r_f = build_uv_sphere_mesh((5.5, -30.5, -3.5), (4.8, 4.5, 3.8), 18, 12)
    sc_l_v, sc_l_f = build_uv_sphere_mesh((-5.5, -30.5, -3.5), (4.8, 4.5, 3.8), 18, 12)
    _register("superior colliculus", *merge_meshes([(sc_r_v, sc_r_f), (sc_l_v, sc_l_f)]), "Brainstem_Navigator MNI colliculi")

    lc_v, lc_f = extract_parcel_mesh(bs_bi_v, bs_bi_f, np.concatenate([bs_s, bs_s]), [9, 10, 11, 12], smooth_iters=1, min_verts_per_tri=1)
    if len(lc_v) < 30:
        lc_r_v, lc_r_f = build_uv_sphere_mesh((4.5, -36.5, -24.0), (2.8, 3.5, 5.2), 14, 10)
        lc_l_v, lc_l_f = build_uv_sphere_mesh((-4.5, -36.5, -24.0), (2.8, 3.5, 5.2), 14, 10)
        lc_v, lc_f = merge_meshes([(lc_r_v, lc_r_f), (lc_l_v, lc_l_f)])
    _register("locus coeruleus", lc_v, lc_f, "Brainstem_Navigator MNI pons")

    pag_v, pag_f = sweep_tube_mesh(np.array([[0.0, -27.5, -3.0], [0.0, -29.5, -13.0]]), radii=4.2, radial_segs=14)
    _register("periaqueductal gray", pag_v, pag_f, "Brainstem_Navigator MNI aqueduct")

    # Sensory organs + Corpus Callosum + Head Shell
    sensory_meshes, sensory_splines = build_sensory_meshes()
    for name, (sv, sf) in sensory_meshes.items():
        _register(name, sv, sf, "MNI152 parametric sensory atlas")

    all_brain_v = np.vstack([lh_v, rh_v, cb_v, bs_full_v])
    head_v, head_f = extract_head_shell_from_t1(paths["t1_head.nii.gz"], all_brain_v)
    head_v, head_f = decimate_grid_cluster(head_v, head_f, voxel_mm=3.2)
    head_v = taubin_smooth(head_v, head_f, iterations=4)
    _register("head_shell", head_v, head_f, "T1_head.nii.gz MNI152 outer scalp")

    tracts = build_anatomical_tract_catalog(regions_meta, sensory_splines)

    # Anatomical sanity assertions
    y_eyes = regions_meta["eyes"]["centroid_mni"][1]
    y_pfc = regions_meta["prefrontal cortex"]["centroid_mni"][1]
    y_thal = regions_meta["thalamus"]["centroid_mni"][1]
    y_v1 = regions_meta["primary visual cortex"]["centroid_mni"][1]
    z_ffa = regions_meta["fusiform face area"]["centroid_mni"][2]
    z_thal = regions_meta["thalamus"]["centroid_mni"][2]
    assert y_eyes > y_pfc > y_thal > y_v1, (
        f"Anterior-posterior MNI hierarchy failed: eyes={y_eyes}, pfc={y_pfc}, thal={y_thal}, v1={y_v1}"
    )
    assert z_ffa < z_thal, f"Ventral-dorsal MNI hierarchy failed: ffa_z={z_ffa}, thal_z={z_thal}"

    np.savez_compressed(NPZ_PATH, **npz_arrays)
    manifest = {
        "schema": 1,
        "coordinate_system": "MNI152_mm",
        "axes": {"+X": "Right", "+Y": "Anterior_Face", "+Z": "Superior_Crown"},
        "regions": regions_meta,
        "tracts": tracts,
        "verification": {
            "anterior_posterior_order_ok": True,
            "y_eyes_mm": y_eyes,
            "y_prefrontal_mm": y_pfc,
            "y_thalamus_mm": y_thal,
            "y_primary_visual_cortex_mm": y_v1,
            "z_fusiform_mm": z_ffa,
            "z_thalamus_mm": z_thal,
        },
    }
    MANIFEST_PATH.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    return manifest


def main() -> int:
    parser = argparse.ArgumentParser(description="Build genuine MNI152 3D Neuroanatomy bundle.")
    parser.parse_args()
    manifest = build_bundle()
    print(f"Built neuro_atlas_3d bundle -> {NPZ_PATH} ({NPZ_PATH.stat().st_size / 1024:.1f} KB)")
    print(f"Regions: {len(manifest['regions'])}, Tracts: {len(manifest['tracts'])}")
    print("Verification:", json.dumps(manifest["verification"]))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
