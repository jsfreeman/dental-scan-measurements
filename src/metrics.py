"""
Error metrics comparing aligned technique cylinders to the gold standard.

Two metrics are reported for each implant:

  angular_error (degrees)
    The angle between the implant axis as captured by the technique and as
    captured by the Desktop Scanner.  Clinically this represents the tilt error
    of the implant scan body — how accurately the scanner reproduced the implant's
    angulation.  A cylinder axis has no inherent "positive" direction, so we use
    the absolute value of the dot product (|cos θ|) to handle sign ambiguity.

  translational_offset (mm)
    The Euclidean distance between the cylinder centre as captured by the technique
    (after rigid alignment to the gold frame) and the gold-standard centre.  This
    represents position error after the global coordinate systems have been aligned
    — the residual that cannot be explained by a rigid shift or rotation of the
    whole scan.  It therefore captures relative displacement errors between implants.

A third metric is reported for each pair of implants:

  inter-implant distance error (mm)
    The difference in the centre-to-centre distance between two implants as
    measured by the technique vs. the gold standard.  This metric is computed from
    the original (pre-alignment) coordinates and is therefore completely independent
    of the alignment step, providing a complementary view of relative accuracy.
"""

import warnings

import numpy as np

from .cylinder_fit import Cylinder


def angular_error(a1: np.ndarray, a2: np.ndarray) -> float:
    """
    Angle in degrees between two cylinder axes.

    Cylinder axes are direction-agnostic (the vector and its negative represent
    the same axis), so we use |a1 · a2| instead of a1 · a2, which gives the
    acute angle between the two axes in [0°, 90°].

    Parameters
    ----------
    a1, a2 : axis vectors (need not be unit vectors — normalised internally)

    Returns
    -------
    Angle in degrees in the range [0, 90].

    Raises
    ------
    ValueError — if either vector has zero length.
    """
    norm1 = np.linalg.norm(a1)
    norm2 = np.linalg.norm(a2)

    if norm1 == 0.0:
        raise ValueError("First axis vector has zero length.")
    if norm2 == 0.0:
        raise ValueError("Second axis vector has zero length.")

    a1 = a1 / norm1
    a2 = a2 / norm2

    # Clamp to [-1, 1] to guard against floating-point values slightly outside
    # the domain of arccos (e.g. 1.0000000002 due to numerical rounding).
    cos_theta = np.clip(abs(np.dot(a1, a2)), 0.0, 1.0)

    return float(np.degrees(np.arccos(cos_theta)))


def translational_offset(c_gold: np.ndarray, c_tech_aligned: np.ndarray) -> float:
    """
    Euclidean distance between a gold-standard cylinder centre and the corresponding
    technique cylinder centre after rigid alignment (mm).

    Because the rigid alignment minimises the total RMSE across all N implants,
    this residual distance cannot be reduced by any global rotation or translation —
    it represents the true relative position error of this individual implant.

    Parameters
    ----------
    c_gold         : (3,) gold-standard centre
    c_tech_aligned : (3,) technique centre transformed into the gold frame

    Returns
    -------
    Distance in mm.
    """
    return float(np.linalg.norm(c_gold - c_tech_aligned))


def interimplant_distance_errors(
    gold: list[Cylinder],
    tech_original: list[Cylinder],
    perm: tuple,
) -> list[dict]:
    """
    For every pair of implants (i, j), compute the difference in centre-to-centre
    distance between the gold standard and the technique.

    This metric is computed from the original (pre-alignment) technique coordinates.
    Because rigid transforms preserve Euclidean distances, the inter-implant
    distances are the same before and after alignment, so this metric is fully
    independent of the alignment step.

    Parameters
    ----------
    gold          : gold-standard cylinders in matched order (gold[i] is implant i)
    tech_original : technique cylinders in their original extracted order
    perm          : correspondence tuple — tech_original[perm[i]] corresponds to gold[i]

    Returns
    -------
    List of dicts, one per implant pair (i, j) with i < j:
        implant_i, implant_j    : 1-based implant indices
        gold_dist_mm            : centre-to-centre distance in the gold standard (mm)
        tech_dist_mm            : same distance in the technique scan (mm)
        dist_error_mm           : |gold_dist_mm − tech_dist_mm| (mm)

    Raises
    ------
    ValueError — if perm length does not match the number of cylinders.
    """
    n = len(gold)

    if len(perm) != n:
        raise ValueError(
            f"Permutation length {len(perm)} does not match "
            f"the number of gold cylinders {n}."
        )

    if len(tech_original) < n:
        raise ValueError(
            f"tech_original has only {len(tech_original)} cylinders; expected {n}."
        )

    records = []
    for i in range(n):
        for j in range(i + 1, n):
            d_gold = float(np.linalg.norm(gold[i].center - gold[j].center))

            # Use the permutation to identify which tech cylinder matches each gold cylinder
            d_tech = float(np.linalg.norm(
                tech_original[perm[i]].center - tech_original[perm[j]].center
            ))

            records.append({
                "implant_i":     i + 1,
                "implant_j":     j + 1,
                "gold_dist_mm":  round(d_gold, 4),
                "tech_dist_mm":  round(d_tech, 4),
                "dist_error_mm": round(abs(d_gold - d_tech), 4),
            })

    return records
