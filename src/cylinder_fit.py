"""
Cylinder extraction from dental scan meshes.

Strategy:
  1. Try splitting the mesh into connected components; if ≥ N found, use the N largest.
  2. Otherwise fall back to K-means spatial clustering with K = N.
  3. Fit one cylinder per cluster using PCA (axis) + algebraic circle fit (center, radius).
"""

from dataclasses import dataclass

import numpy as np
import trimesh
from scipy.cluster.vq import kmeans2


@dataclass
class Cylinder:
    center: np.ndarray  # 3-D point on axis (mm)
    axis: np.ndarray    # unit direction vector
    radius: float       # mm


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _orthogonal_basis(v: np.ndarray):
    """Return two unit vectors that span the plane perpendicular to v."""
    v = v / np.linalg.norm(v)
    t = np.array([1.0, 0.0, 0.0]) if abs(v[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(v, t)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(v, e1)
    return e1, e2


def _fit_circle_algebraic(pts_2d: np.ndarray):
    """
    Algebraic least-squares circle fit to 2-D points.
    Solves  x² + y² = A·x + B·y + C  in the least-squares sense.
    Returns (cx, cy, radius).
    """
    x, y = pts_2d[:, 0], pts_2d[:, 1]
    A = np.column_stack([x, y, np.ones(len(x))])
    b = x ** 2 + y ** 2
    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)
    cx = params[0] / 2.0
    cy = params[1] / 2.0
    r_sq = cx ** 2 + cy ** 2 + params[2]
    radius = float(np.sqrt(max(r_sq, 0.0)))
    return cx, cy, radius


def fit_cylinder_to_points(points: np.ndarray) -> Cylinder:
    """
    Fit a cylinder to an (N, 3) point array using PCA + algebraic circle fit.
    """
    centroid = points.mean(axis=0)
    centered = points - centroid

    # PCA: first principal component = axis of maximum variance = cylinder axis
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    axis = Vt[0]  # unit vector

    # Project points perpendicular to axis
    projections = centered @ axis            # scalar projections along axis
    parallel = np.outer(projections, axis)
    perpendicular = centered - parallel      # (N, 3) vectors in the plane

    # Express perpendicular components in a 2-D basis
    e1, e2 = _orthogonal_basis(axis)
    pts_2d = np.column_stack([perpendicular @ e1, perpendicular @ e2])

    cx_2d, cy_2d, radius = _fit_circle_algebraic(pts_2d)

    # Reconstruct 3-D center: centroid shifted by circle centre offset
    center = centroid + cx_2d * e1 + cy_2d * e2

    return Cylinder(center=center, axis=axis, radius=radius)


# ---------------------------------------------------------------------------
# Cluster extraction
# ---------------------------------------------------------------------------

def _clusters_from_components(mesh: trimesh.Trimesh, n: int):
    """
    Split mesh by connected components and return point arrays for the N largest.
    Returns None if fewer than N components are found.
    """
    parts = mesh.split(only_watertight=False)
    if len(parts) < n:
        return None
    # Sort by face count, descending
    parts = sorted(parts, key=lambda m: len(m.faces), reverse=True)
    clusters = []
    for part in parts[:n]:
        pts, _ = trimesh.sample.sample_surface(part, max(500, len(part.faces) * 2))
        clusters.append(pts)
    return clusters


def _clusters_from_kmeans(mesh: trimesh.Trimesh, n: int, n_sample: int = 30_000):
    """
    Sample the mesh surface and K-means cluster into N spatial groups.
    """
    n_sample = min(n_sample, max(len(mesh.faces) * 2, 1000))
    points, _ = trimesh.sample.sample_surface(mesh, n_sample)

    # kmeans2 requires float64
    points = points.astype(np.float64)
    _, labels = kmeans2(points, n, nit=30, minit="points", seed=42)

    clusters = [points[labels == i] for i in range(n)]
    # Discard empty clusters (shouldn't happen but guard anyway)
    clusters = [c for c in clusters if len(c) >= 10]
    return clusters


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_cylinders(mesh: trimesh.Trimesh, n: int) -> list[Cylinder]:
    """
    Extract N cylinders from a mesh representing N implant scan bodies.

    Tries connected-component splitting first; falls back to K-means clustering.
    Fits one cylinder per cluster via PCA + algebraic circle fit.
    """
    print(f"    Extracting {n} cylinders from mesh ({len(mesh.faces):,} triangles)...")

    clusters = _clusters_from_components(mesh, n)
    if clusters is not None:
        print(f"    Used connected components ({len(clusters)} found).")
    else:
        print(f"    Fewer than {n} components — using K-means clustering.")
        clusters = _clusters_from_kmeans(mesh, n)

    if len(clusters) < n:
        raise RuntimeError(
            f"Could only extract {len(clusters)} clusters, expected {n}. "
            "Check that n_implants in the config matches the file."
        )

    cylinders = [fit_cylinder_to_points(c) for c in clusters]

    # Consistent ordering: sort by cylinder center coordinates (X then Y then Z)
    cylinders.sort(key=lambda c: (round(c.center[0], 1), round(c.center[1], 1)))

    return cylinders
