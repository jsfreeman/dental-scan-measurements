"""
Rigid-body alignment of two cylinder sets using the Kabsch SVD algorithm.

Problem
-------
Two scans of the same mouth are captured in different coordinate frames — each
scanner has its own origin and orientation.  Before we can compare the implant
cylinders from a technique scan to those of the gold-standard Desktop Scanner,
we must find the rigid transform (rotation + translation) that best maps one
coordinate frame onto the other.

We also do not know in advance which cylinder in the technique file corresponds
to which cylinder in the gold-standard file (their spatial ordering may differ).
We solve both problems together by trying every possible correspondence (N!
permutations) and keeping the one that yields the lowest alignment error.

Algorithm
---------
For each candidate correspondence (permutation σ of the N technique cylinders):
  1. Extract the N cylinder centres from both sets.
  2. Run the Kabsch algorithm to find the optimal rotation R and translation t
     that minimises the RMSE between the paired gold and transformed tech centres.
  3. Record the RMSE for this permutation.
Return the permutation with the lowest RMSE and apply the corresponding transform
to the full cylinder set (centres and axis vectors).

Scalability
-----------
N! grows quickly, but for dental implant studies N is typically 2–6.
  N=4 → 24 permutations, N=6 → 720 permutations.
Each permutation requires one SVD (3×3 matrix) — the full search takes < 1 ms
even for N=6, so brute force is appropriate here.
"""

from itertools import permutations

import numpy as np

from .cylinder_fit import Cylinder

# If the best-fit alignment RMSE exceeds this threshold (mm), the correspondence
# may be wrong or the scans may not represent the same case.
_RMSE_WARNING_THRESHOLD_MM = 1.0


def _kabsch(P: np.ndarray, Q: np.ndarray):
    """
    Kabsch algorithm: find the rotation R and translation t that best aligns Q onto P.

    Returns (R, t) such that  Q @ R.T + t  minimises RMSE(P, Q_aligned).

    Parameters
    ----------
    P : (N, 3) — target points (gold standard centres)
    Q : (N, 3) — source points (technique centres, already reordered by permutation)

    Algorithm
    ---------
    1. Centre both point sets at their respective centroids.
    2. Form the 3×3 cross-covariance matrix H = Qc.T @ Pc.
    3. SVD: H = U Σ Vᵀ.
    4. R = Vᵀᵀ D Uᵀ  where D = diag(1, 1, det(VᵀᵀUᵀ)) corrects for reflections.
    5. t = centroid(P) − centroid(Q) @ Rᵀ.
    """
    mu_P = P.mean(axis=0)
    mu_Q = Q.mean(axis=0)
    P_c  = P - mu_P
    Q_c  = Q - mu_Q

    # Cross-covariance between the two centred point sets
    H = Q_c.T @ P_c  # (3, 3)

    U, _, Vt = np.linalg.svd(H)

    # det(Vᵀᵀ Uᵀ) is +1 for a proper rotation, −1 for an improper one (reflection).
    # The diagonal correction matrix D forces a proper rotation.
    d = np.linalg.det(Vt.T @ U.T)
    D = np.diag([1.0, 1.0, d])

    R = Vt.T @ D @ U.T           # (3, 3) rotation matrix
    t = mu_P - mu_Q @ R.T        # (3,)   translation vector

    return R, t


def _rmse(P: np.ndarray, Q_aligned: np.ndarray) -> float:
    """Root-mean-square error between two (N, 3) point arrays (mm)."""
    return float(np.sqrt(((P - Q_aligned) ** 2).sum(axis=1).mean()))


def align_cylinders(gold: list[Cylinder], tech: list[Cylinder]):
    """
    Find the best correspondence between technique and gold-standard cylinders,
    compute the Kabsch rigid transform, and return the aligned technique cylinders.

    Parameters
    ----------
    gold : list of N Cylinder objects — gold-standard (Desktop Scanner)
    tech : list of N Cylinder objects — technique scan to align

    Returns
    -------
    aligned_tech : list[Cylinder]
        Technique cylinders reordered and transformed into the gold coordinate frame,
        in the same order as `gold` (i.e. aligned_tech[i] corresponds to gold[i]).
    R    : (3, 3) ndarray — rotation matrix applied to the technique scan
    t    : (3,)   ndarray — translation vector applied to the technique scan
    perm : tuple           — the winning permutation index; tech[perm[i]] → gold[i]
    rmse : float           — centre RMSE after alignment (mm)

    Raises
    ------
    ValueError  — if gold and tech contain different numbers of cylinders.
    RuntimeError — if no valid alignment can be found (should not happen in practice).
    """
    n = len(gold)

    if len(tech) != n:
        raise ValueError(
            f"Cannot align cylinder sets of different sizes: "
            f"gold has {n}, technique has {len(tech)}."
        )

    if n == 0:
        raise ValueError("Cylinder lists are empty — nothing to align.")

    gold_centers = np.array([c.center for c in gold])   # (N, 3)
    tech_centers = np.array([c.center for c in tech])   # (N, 3)

    # --- Search all N! correspondences ---
    best_rmse = np.inf
    best_perm = tuple(range(n))
    best_R    = np.eye(3)
    best_t    = np.zeros(3)

    for perm in permutations(range(n)):
        Q = tech_centers[list(perm)]       # reorder tech centres by this permutation
        R, t = _kabsch(gold_centers, Q)
        Q_aligned = Q @ R.T + t
        err = _rmse(gold_centers, Q_aligned)

        if err < best_rmse:
            best_rmse = err
            best_perm = perm
            best_R    = R
            best_t    = t

    if best_rmse == np.inf:
        raise RuntimeError("Alignment search produced no valid result.")


    # --- Apply the winning transform to axes and centres ---
    aligned_tech = []
    for i in range(n):
        src = tech[best_perm[i]]
        # Centres transform with rotation + translation
        aligned_center = src.center @ best_R.T + best_t
        # Axes are direction vectors — rotate only, no translation
        aligned_axis   = src.axis @ best_R.T
        aligned_tech.append(
            Cylinder(center=aligned_center, axis=aligned_axis, radius=src.radius)
        )

    return aligned_tech, best_R, best_t, best_perm, best_rmse
