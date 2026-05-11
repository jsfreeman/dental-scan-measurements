"""
Rigid-body alignment of two cylinder sets via Kabsch SVD.

For N implants we try all N! correspondences and keep the one that
minimises the RMSE of the aligned cylinder centres.  This is feasible
for the expected N ≤ 6  (720 permutations maximum).
"""

from itertools import permutations

import numpy as np

from .cylinder_fit import Cylinder


def _kabsch(P: np.ndarray, Q: np.ndarray):
    """
    Find rotation R and translation t that best aligns Q onto P.
    Returns (R, t) such that  Q @ R.T + t  ≈  P.
    Both P and Q are (N, 3) arrays of corresponding points.
    """
    mu_P = P.mean(axis=0)
    mu_Q = Q.mean(axis=0)
    P_c = P - mu_P
    Q_c = Q - mu_Q

    H = Q_c.T @ P_c  # 3×3 cross-covariance
    U, _, Vt = np.linalg.svd(H)

    # Correct for reflection
    d = np.linalg.det(Vt.T @ U.T)
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T

    t = mu_P - mu_Q @ R.T
    return R, t


def _rmse(P: np.ndarray, Q_aligned: np.ndarray) -> float:
    return float(np.sqrt(((P - Q_aligned) ** 2).sum(axis=1).mean()))


def align_cylinders(gold: list[Cylinder], tech: list[Cylinder]):
    """
    Find the best correspondence between tech and gold cylinders, compute
    the Kabsch rigid transform, and return aligned tech cylinders.

    Returns
    -------
    aligned_tech : list[Cylinder]
        Tech cylinders reordered and transformed to the gold coordinate frame,
        in the same order as `gold`.
    R : (3, 3) ndarray  — rotation matrix
    t : (3,)  ndarray   — translation vector
    perm : tuple         — index permutation applied to tech before aligning
    rmse : float         — centre RMSE after alignment (mm)
    """
    n = len(gold)
    assert len(tech) == n, f"Cylinder count mismatch: gold={n}, tech={len(tech)}"

    gold_centers = np.array([c.center for c in gold])
    tech_centers = np.array([c.center for c in tech])

    best_rmse = np.inf
    best_perm = tuple(range(n))
    best_R = np.eye(3)
    best_t = np.zeros(3)

    for perm in permutations(range(n)):
        Q = tech_centers[list(perm)]
        R, t = _kabsch(gold_centers, Q)
        Q_aligned = Q @ R.T + t
        err = _rmse(gold_centers, Q_aligned)
        if err < best_rmse:
            best_rmse = err
            best_perm = perm
            best_R = R
            best_t = t

    # Build aligned cylinder list in gold order
    aligned_tech = []
    for i in range(n):
        src = tech[best_perm[i]]
        aligned_center = src.center @ best_R.T + best_t
        aligned_axis = src.axis @ best_R.T  # rotate axis (no translation)
        aligned_tech.append(Cylinder(center=aligned_center,
                                     axis=aligned_axis,
                                     radius=src.radius))

    return aligned_tech, best_R, best_t, best_perm, best_rmse
