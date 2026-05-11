"""
Cylinder extraction from dental scan meshes.

Each STL/PLY file contains N implant scan bodies — small cylindrical titanium
markers that screw onto each implant and protrude above the gum line.  We need
to locate each scan body and fit a cylinder to it so we can compare its position
and orientation across different scanning techniques.

Extraction strategy
-------------------
1. Try splitting the mesh into connected components (disconnected mesh islands).
   Dental CAD exports often produce one mesh body per scan body, so this is the
   preferred path.  We take the N largest components.
2. If fewer than N components are found (e.g. photogrammetry meshes that include
   surrounding gum tissue as one continuous surface), fall back to K-means spatial
   clustering with K = N.  Because the scan bodies are spatially well-separated,
   K-means reliably partitions the point cloud into one cluster per scan body.

Cylinder fitting (per cluster)
-------------------------------
Uses PCA to find the dominant axis direction, then fits a circle algebraically in
the plane perpendicular to that axis to recover the cylinder centre and radius.
This is deterministic and fast, and works well when the cluster is dominated by
the cylindrical scan body surface.
"""

from dataclasses import dataclass

import numpy as np
import trimesh
from scipy.cluster.vq import kmeans2

# Minimum number of points required to attempt a cylinder fit.
# Below this the SVD and circle fit are unreliable.
_MIN_CLUSTER_POINTS = 20


@dataclass
class Cylinder:
    center: np.ndarray  # 3-D point on the cylinder axis (mm)
    axis: np.ndarray    # unit direction vector along the cylinder axis
    radius: float       # cylinder radius (mm)


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _orthogonal_basis(v: np.ndarray):
    """
    Return two orthonormal vectors (e1, e2) that span the plane perpendicular to v.

    We pick a helper vector that is not collinear with v to avoid a degenerate
    cross product, then use two successive cross products to build the basis.
    """
    v = v / np.linalg.norm(v)
    # Choose a reference vector that is not (nearly) parallel to v
    helper = np.array([1.0, 0.0, 0.0]) if abs(v[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(v, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(v, e1)   # already unit length since v and e1 are orthonormal
    return e1, e2


def _fit_circle_algebraic(pts_2d: np.ndarray):
    """
    Fit a circle to 2-D points using the algebraic (linear least-squares) method.

    Derivation
    ----------
    The circle equation  (x-cx)² + (y-cy)² = r²  expands to:
        x² + y²  =  2·cx·x  +  2·cy·y  +  (r² - cx² - cy²)

    Setting  A = 2·cx,  B = 2·cy,  C = r² - cx² - cy²  gives the linear system
        [x  y  1] · [A  B  C]ᵀ  =  x² + y²

    which we solve in the least-squares sense, then recover cx, cy, r.

    Parameters
    ----------
    pts_2d : (N, 2) array of 2-D points

    Returns
    -------
    cx, cy : circle centre in the 2-D projected plane
    radius  : circle radius (mm); clamped to 0 if the fit yields a negative r².
    """
    if len(pts_2d) < 3:
        raise ValueError(
            f"At least 3 points are required for circle fitting; got {len(pts_2d)}."
        )

    x, y = pts_2d[:, 0], pts_2d[:, 1]
    A = np.column_stack([x, y, np.ones(len(x))])
    b = x ** 2 + y ** 2

    params, _, _, _ = np.linalg.lstsq(A, b, rcond=None)

    cx = params[0] / 2.0
    cy = params[1] / 2.0
    r_sq = cx ** 2 + cy ** 2 + params[2]

    if r_sq < 0:
        # This can occur when the projected points are nearly collinear (degenerate
        # cluster).  Clamp to zero; the caller should treat this as a warning.
        radius = 0.0
    else:
        radius = float(np.sqrt(r_sq))

    return cx, cy, radius


def fit_cylinder_to_points(points: np.ndarray) -> Cylinder:
    """
    Fit a cylinder to an (N, 3) point cloud using PCA + algebraic circle fit.

    Steps
    -----
    1. PCA on the centred point cloud — the first principal component (direction of
       maximum variance) is the cylinder axis.
    2. Project each point onto the plane perpendicular to the axis.
    3. Fit a circle to the 2-D projected points to recover the cross-section centre
       and radius.
    4. Reconstruct the 3-D cylinder centre by adding the 2-D circle offset to the
       3-D centroid.

    Parameters
    ----------
    points : (N, 3) array — surface points belonging to one scan body

    Returns
    -------
    Cylinder with centre, unit axis vector, and radius.

    Raises
    ------
    ValueError — if fewer than _MIN_CLUSTER_POINTS points are supplied.
    """
    if len(points) < _MIN_CLUSTER_POINTS:
        raise ValueError(
            f"Need at least {_MIN_CLUSTER_POINTS} points to fit a cylinder; "
            f"got {len(points)}."
        )

    centroid = points.mean(axis=0)
    centered = points - centroid

    # SVD of the centred matrix: rows of Vt are the principal components in
    # descending order of explained variance.  The first row is the cylinder axis.
    _, _, Vt = np.linalg.svd(centered, full_matrices=False)
    axis = Vt[0]  # unit vector (SVD guarantees this)

    # Decompose each centred point into components parallel and perpendicular to axis
    projections = centered @ axis          # scalar distance along axis for each point
    parallel    = np.outer(projections, axis)
    perpendicular = centered - parallel    # lies in the plane perpendicular to axis

    # Express the perpendicular components in a 2-D coordinate system
    e1, e2 = _orthogonal_basis(axis)
    pts_2d = np.column_stack([perpendicular @ e1, perpendicular @ e2])

    cx_2d, cy_2d, radius = _fit_circle_algebraic(pts_2d)

    if radius == 0.0:
        import warnings
        warnings.warn(
            "Circle fit produced radius ≈ 0 — cluster may be degenerate. "
            "Check that n_implants matches the actual number of scan bodies."
        )

    # The 3-D cylinder centre is the centroid shifted by the 2-D circle offset
    center = centroid + cx_2d * e1 + cy_2d * e2

    return Cylinder(center=center, axis=axis, radius=radius)


# ---------------------------------------------------------------------------
# Cluster extraction
# ---------------------------------------------------------------------------

def _clusters_from_components(mesh: trimesh.Trimesh, n: int):
    """
    Split the mesh on connected-component boundaries and return point arrays for
    the N largest components.

    Returns None if fewer than N disconnected components exist, signalling that
    the K-means fallback should be used.
    """
    parts = mesh.split(only_watertight=False)

    if len(parts) < n:
        return None  # not enough separate bodies — caller will use K-means

    # Prefer larger components (more triangles = more geometric detail)
    parts = sorted(parts, key=lambda m: len(m.faces), reverse=True)

    clusters = []
    for part in parts[:n]:
        # Sample proportional to face count so denser meshes get more points,
        # but always keep at least 500 points for a stable cylinder fit.
        n_pts = max(500, len(part.faces) * 2)
        pts, _ = trimesh.sample.sample_surface(part, n_pts)
        clusters.append(pts)

    return clusters


def _clusters_from_kmeans(mesh: trimesh.Trimesh, n: int, n_sample: int = 30_000):
    """
    Sample the mesh surface uniformly and cluster into N spatial groups with K-means.

    This is the fallback when the mesh is a single connected body (common in
    photogrammetry outputs that include surrounding gum tissue).  Because implant
    scan bodies are spatially well-separated — typically 5–15 mm apart — K-means
    with K = N partitions them reliably.

    Parameters
    ----------
    mesh     : the mesh to cluster
    n        : number of clusters (= number of implants)
    n_sample : target number of surface sample points; clamped to a sensible range

    Returns
    -------
    List of N (M_i, 3) point arrays, one per cluster.
    """
    # Cap the sample count at twice the face count (there's no benefit sampling
    # more points than the mesh can support) but always sample at least 1 000.
    n_sample = min(n_sample, max(len(mesh.faces) * 2, 1000))
    points, _ = trimesh.sample.sample_surface(mesh, n_sample)

    points = points.astype(np.float64)  # kmeans2 requires float64

    try:
        _, labels = kmeans2(points, n, nit=30, minit="points", seed=42)
    except Exception as exc:
        raise RuntimeError(
            f"K-means clustering failed with n={n} clusters on "
            f"{len(points)} points: {exc}"
        ) from exc

    clusters = [points[labels == i] for i in range(n)]

    # Guard: discard any cluster that is too small to fit a cylinder
    valid = [c for c in clusters if len(c) >= _MIN_CLUSTER_POINTS]

    if len(valid) < n:
        raise RuntimeError(
            f"K-means produced only {len(valid)} usable clusters (≥ "
            f"{_MIN_CLUSTER_POINTS} points) out of {n} expected. "
            "The mesh may not contain enough distinct scan-body geometry, "
            "or n_implants in the config is incorrect."
        )

    return valid


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def extract_cylinders(mesh: trimesh.Trimesh, n: int) -> list[Cylinder]:
    """
    Extract N cylinders from a mesh that represents N implant scan bodies.

    Parameters
    ----------
    mesh : the loaded mesh (STL or PLY)
    n    : number of implants / scan bodies expected in this mesh

    Returns
    -------
    List of N Cylinder objects, sorted by centre position (X then Y) for a
    consistent ordering that is stable across runs.

    Raises
    ------
    ValueError  — if n < 1.
    RuntimeError — if fewer than n clusters can be extracted.
    """
    if n < 1:
        raise ValueError(f"n_implants must be ≥ 1; got {n}.")

    print(f"    Extracting {n} cylinders from mesh ({len(mesh.faces):,} triangles)...")

    # --- Step 1: try connected components (fast path for CAD-exported meshes) ---
    clusters = _clusters_from_components(mesh, n)

    if clusters is not None:
        print(f"    Strategy: connected components ({len(clusters)} bodies found).")
    else:
        # --- Step 2: fall back to K-means spatial clustering ---
        print(f"    Fewer than {n} connected components — falling back to K-means.")
        clusters = _clusters_from_kmeans(mesh, n)

    # Fit one cylinder per cluster
    cylinders = []
    for idx, cluster in enumerate(clusters):
        try:
            cyl = fit_cylinder_to_points(cluster)
        except ValueError as exc:
            raise RuntimeError(
                f"Cylinder fit failed for cluster {idx + 1}/{n}: {exc}"
            ) from exc
        cylinders.append(cyl)

    # Sort by centre (X then Y) so implant numbering is spatially consistent
    # across different scans of the same case.
    cylinders.sort(key=lambda c: (round(c.center[0], 1), round(c.center[1], 1)))

    return cylinders
