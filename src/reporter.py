"""
Excel output — writes per-implant and inter-implant results plus a summary
sheet to a single results.xlsx workbook.
"""

import pathlib

import numpy as np
import pandas as pd


def _guide_df() -> pd.DataFrame:
    """Build the Column Guide reference table — one row per column across all sheets."""
    rows = [
        # ------------------------------------------------------------------
        # Per Implant sheet
        # ------------------------------------------------------------------
        ("Per Implant", "case",
         "Patient case identifier (matches the name field in the config file)."),
        ("Per Implant", "technique",
         "Scanning technique (e.g. TRIOS, Nexus, Shinning)."),
        ("Per Implant", "implant_id",
         "1-based implant index within the case. Implants are sorted by X then Y "
         "position of their fitted centre, so the numbering is spatially consistent "
         "across techniques but is not clinically meaningful."),
        ("Per Implant", "angular_error_deg",
         "Angle in degrees between the technique cylinder axis and the gold-standard "
         "axis for the same implant, after rigid alignment of the two scans. Because "
         "a cylinder axis has no inherent direction, the acute angle (0–90°) is "
         "always reported. Smaller values indicate better angular accuracy."),
        ("Per Implant", "translational_offset_mm",
         "Euclidean distance in mm between the technique cylinder centre and the "
         "gold-standard centre, measured after rigid alignment. This residual cannot "
         "be reduced by any global rotation or translation — it represents true "
         "relative position error of the individual implant. Smaller is better."),
        ("Per Implant", "tech_axis_x",
         "X component of the fitted technique cylinder axis (unit vector) expressed "
         "in the gold-standard coordinate frame after alignment."),
        ("Per Implant", "tech_axis_y",
         "Y component of the technique axis unit vector (gold frame)."),
        ("Per Implant", "tech_axis_z",
         "Z component of the technique axis unit vector (gold frame)."),
        ("Per Implant", "tech_center_x",
         "X coordinate (mm) of the fitted technique cylinder centre in the "
         "gold-standard coordinate frame after alignment."),
        ("Per Implant", "tech_center_y",
         "Y coordinate (mm) of the technique cylinder centre (gold frame)."),
        ("Per Implant", "tech_center_z",
         "Z coordinate (mm) of the technique cylinder centre (gold frame)."),
        ("Per Implant", "tech_radius_mm",
         "Fitted radius (mm) of the technique cylinder. Nominal scan-body radius "
         "is ~2.46 mm. Values significantly outside this range indicate a poor fit."),
        ("Per Implant", "gold_axis_x",
         "X component of the gold-standard (Desktop Scanner) cylinder axis unit vector."),
        ("Per Implant", "gold_axis_y",
         "Y component of the gold-standard axis unit vector."),
        ("Per Implant", "gold_axis_z",
         "Z component of the gold-standard axis unit vector."),
        ("Per Implant", "gold_center_x",
         "X coordinate (mm) of the gold-standard cylinder centre."),
        ("Per Implant", "gold_center_y",
         "Y coordinate (mm) of the gold-standard cylinder centre."),
        ("Per Implant", "gold_center_z",
         "Z coordinate (mm) of the gold-standard cylinder centre."),
        ("Per Implant", "gold_radius_mm",
         "Fitted radius (mm) of the gold-standard cylinder."),
        ("Per Implant", "tech_fit_rmse_mm",
         "Cylinder fit quality: mean distance (mm) of technique mesh surface points "
         "from the fitted cylinder wall. < 0.10 mm = excellent fit, > 0.50 mm = poor. "
         "High values suggest the cluster contained non-cylindrical geometry or that "
         "the wrong number of implants was specified."),
        ("Per Implant", "tech_elongation_ratio",
         "Cylinder fit quality: PCA eigenvalue ratio λ₁ / (λ₂ + λ₃) for the "
         "technique point cluster. Measures how strongly elongated (cylindrical) the "
         "cluster shape is. > 5 = strongly cylindrical (reliable axis), "
         "2–5 = moderate, < 2 = weakly cylindrical (unreliable axis direction)."),
        ("Per Implant", "gold_fit_rmse_mm",
         "Same fit RMSE metric as tech_fit_rmse_mm, but for the gold-standard cylinder."),
        ("Per Implant", "gold_elongation_ratio",
         "Same elongation ratio as tech_elongation_ratio, but for the gold-standard."),

        # ------------------------------------------------------------------
        # Inter-Implant sheet
        # ------------------------------------------------------------------
        ("Inter-Implant", "case",
         "Patient case identifier."),
        ("Inter-Implant", "technique",
         "Scanning technique."),
        ("Inter-Implant", "implant_i",
         "1-based index of the first implant in the pair (i < j)."),
        ("Inter-Implant", "implant_j",
         "1-based index of the second implant in the pair."),
        ("Inter-Implant", "gold_dist_mm",
         "Centre-to-centre distance (mm) between implants i and j as measured by "
         "the gold-standard Desktop Scanner."),
        ("Inter-Implant", "tech_dist_mm",
         "Centre-to-centre distance (mm) between the same implant pair as measured "
         "by the comparison technique."),
        ("Inter-Implant", "dist_error_mm",
         "Absolute difference |gold_dist_mm − tech_dist_mm| in mm. Computed from "
         "original (pre-alignment) coordinates — rigid transforms preserve distances, "
         "so this metric is completely independent of the alignment step and is the "
         "most reliable indicator of relative accuracy between implants."),

        # ------------------------------------------------------------------
        # Summary sheet
        # ------------------------------------------------------------------
        ("Summary", "technique",
         "Scanning technique."),
        ("Summary", "n_implants",
         "Total number of individual implant measurements for this technique "
         "(cases × implants per case)."),
        ("Summary", "angular_error_mean_deg",   "Mean angular error across all implants (degrees)."),
        ("Summary", "angular_error_std_deg",    "Standard deviation of angular error (degrees, ddof=1)."),
        ("Summary", "angular_error_median_deg", "Median angular error (degrees)."),
        ("Summary", "angular_error_min_deg",    "Minimum angular error observed (degrees)."),
        ("Summary", "angular_error_max_deg",    "Maximum angular error observed (degrees)."),
        ("Summary", "translational_offset_mean_mm",   "Mean translational offset (mm)."),
        ("Summary", "translational_offset_std_mm",    "Standard deviation of translational offset (mm, ddof=1)."),
        ("Summary", "translational_offset_median_mm", "Median translational offset (mm)."),
        ("Summary", "translational_offset_min_mm",    "Minimum translational offset observed (mm)."),
        ("Summary", "translational_offset_max_mm",    "Maximum translational offset observed (mm)."),
        ("Summary", "n_implant_pairs",
         "Total number of implant-pair distance measurements for this technique."),
        ("Summary", "interimplant_dist_error_mean_mm",   "Mean inter-implant distance error (mm)."),
        ("Summary", "interimplant_dist_error_std_mm",    "Standard deviation of inter-implant distance error (mm, ddof=1)."),
        ("Summary", "interimplant_dist_error_median_mm", "Median inter-implant distance error (mm)."),
        ("Summary", "interimplant_dist_error_min_mm",    "Minimum inter-implant distance error observed (mm)."),
        ("Summary", "interimplant_dist_error_max_mm",    "Maximum inter-implant distance error observed (mm)."),
    ]
    return pd.DataFrame(rows, columns=["Sheet", "Column", "Description"])


def _summary_df(implant_df: pd.DataFrame, interimplant_df: pd.DataFrame) -> pd.DataFrame:
    """Build one summary row per technique with key descriptive statistics."""
    rows = []
    for tech in sorted(implant_df["technique"].unique()):
        imp  = implant_df[implant_df["technique"] == tech]
        pair = interimplant_df[interimplant_df["technique"] == tech]

        def stats(series, dp=3):
            return (round(series.mean(), dp), round(series.std(ddof=1), dp),
                    round(np.median(series), dp),
                    round(series.min(), dp), round(series.max(), dp))

        ang   = stats(imp["angular_error_deg"])
        trans = stats(imp["translational_offset_mm"], dp=4)
        dist  = stats(pair["dist_error_mm"], dp=4)

        rows.append({
            "technique":                         tech,
            "n_implants":                        len(imp),
            "angular_error_mean_deg":            ang[0],
            "angular_error_std_deg":             ang[1],
            "angular_error_median_deg":          ang[2],
            "angular_error_min_deg":             ang[3],
            "angular_error_max_deg":             ang[4],
            "translational_offset_mean_mm":      trans[0],
            "translational_offset_std_mm":       trans[1],
            "translational_offset_median_mm":    trans[2],
            "translational_offset_min_mm":       trans[3],
            "translational_offset_max_mm":       trans[4],
            "n_implant_pairs":                   len(pair),
            "interimplant_dist_error_mean_mm":   dist[0],
            "interimplant_dist_error_std_mm":    dist[1],
            "interimplant_dist_error_median_mm": dist[2],
            "interimplant_dist_error_min_mm":    dist[3],
            "interimplant_dist_error_max_mm":    dist[4],
        })
    return pd.DataFrame(rows)


def write_results(
    implant_records: list[dict],
    interimplant_records: list[dict],
    implant_csv: str,
    interimplant_csv: str,
) -> None:
    """
    Write measurement results to results.xlsx with three sheets:
      - Per Implant    : one row per implant per technique per case
      - Inter-Implant  : one row per implant pair per technique per case
      - Summary        : descriptive statistics aggregated per technique

    The Excel file is written to the same directory as implant_csv.

    Parameters
    ----------
    implant_records      : list of row dicts for the per-implant table
    interimplant_records : list of row dicts for the inter-implant table
    implant_csv          : used only to locate the output directory
    interimplant_csv     : used only to locate the output directory

    Raises
    ------
    ValueError  — if either record list is empty.
    OSError     — if the output directory does not exist or is not writable.
    """
    if not implant_records:
        raise ValueError("implant_records is empty — nothing to write.")
    if not interimplant_records:
        raise ValueError("interimplant_records is empty — nothing to write.")

    out_dir = pathlib.Path(implant_csv).parent
    if not out_dir.exists():
        raise OSError(
            f"Output directory does not exist: {out_dir}. "
            "Create it or update the output path in the config."
        )

    implant_df      = pd.DataFrame(implant_records)
    interimplant_df = pd.DataFrame(interimplant_records)
    summary_df      = _summary_df(implant_df, interimplant_df)
    guide_df        = _guide_df()

    xlsx_path = out_dir / "results.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        guide_df.to_excel(writer,        sheet_name="Column Guide",  index=False)
        implant_df.to_excel(writer,      sheet_name="Per Implant",   index=False)
        interimplant_df.to_excel(writer, sheet_name="Inter-Implant", index=False)
        summary_df.to_excel(writer,      sheet_name="Summary",       index=False)

    print(f"\nResults written to {xlsx_path}")
    print(f"  Column Guide  : {len(guide_df)} columns documented")
    print(f"  Per Implant   : {len(implant_df)} rows")
    print(f"  Inter-Implant : {len(interimplant_df)} rows")
    print(f"  Summary       : {len(summary_df)} technique(s)")
