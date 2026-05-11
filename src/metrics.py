"""
Error metrics comparing aligned technique cylinders to the gold standard.
"""

import numpy as np

from .cylinder_fit import Cylinder


def angular_error(a1: np.ndarray, a2: np.ndarray) -> float:
    """
    Angle in degrees between two cylinder axes.
    Handles sign ambiguity: axes are direction-agnostic, so we take |cos θ|.
    """
    a1 = a1 / np.linalg.norm(a1)
    a2 = a2 / np.linalg.norm(a2)
    cos_theta = np.clip(abs(np.dot(a1, a2)), 0.0, 1.0)
    return float(np.degrees(np.arccos(cos_theta)))


def translational_offset(c_gold: np.ndarray, c_tech_aligned: np.ndarray) -> float:
    """Euclidean distance between aligned cylinder centres (mm)."""
    return float(np.linalg.norm(c_gold - c_tech_aligned))


def interimplant_distance_errors(
    gold: list[Cylinder],
    tech_original: list[Cylinder],
    perm: tuple,
) -> list[dict]:
    """
    For every pair (i, j) compute the difference in centre-to-centre distance
    between gold standard and technique.  Uses original (pre-alignment) tech
    centres — inter-implant distances are rigid-transform invariant.

    Parameters
    ----------
    gold          : gold standard cylinders (ordered)
    tech_original : technique cylinders in their original order
    perm          : correspondence mapping — tech[perm[i]] corresponds to gold[i]

    Returns a list of dicts, one per implant pair.
    """
    n = len(gold)
    records = []
    for i in range(n):
        for j in range(i + 1, n):
            d_gold = float(np.linalg.norm(gold[i].center - gold[j].center))
            d_tech = float(np.linalg.norm(
                tech_original[perm[i]].center - tech_original[perm[j]].center
            ))
            records.append({
                "implant_i": i + 1,
                "implant_j": j + 1,
                "gold_dist_mm": round(d_gold, 4),
                "tech_dist_mm": round(d_tech, 4),
                "dist_error_mm": round(abs(d_gold - d_tech), 4),
            })
    return records
