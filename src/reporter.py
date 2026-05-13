"""
Excel output — writes per-implant and inter-implant results plus a summary
sheet to a single results.xlsx workbook.
"""

import pathlib

import numpy as np
import pandas as pd


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

    xlsx_path = out_dir / "results.xlsx"
    with pd.ExcelWriter(xlsx_path, engine="openpyxl") as writer:
        implant_df.to_excel(writer,      sheet_name="Per Implant",   index=False)
        interimplant_df.to_excel(writer, sheet_name="Inter-Implant", index=False)
        summary_df.to_excel(writer,      sheet_name="Summary",       index=False)

    print(f"\nResults written to {xlsx_path}")
    print(f"  Per Implant   : {len(implant_df)} rows")
    print(f"  Inter-Implant : {len(interimplant_df)} rows")
    print(f"  Summary       : {len(summary_df)} technique(s)")
