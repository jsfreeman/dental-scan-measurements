"""
CSV output — writes per-implant and inter-implant results to disk.
"""

import pathlib

import pandas as pd


def write_results(
    implant_records: list[dict],
    interimplant_records: list[dict],
    implant_csv: str,
    interimplant_csv: str,
) -> None:
    """
    Write measurement results to two CSV files.

    Parameters
    ----------
    implant_records      : list of row dicts for the per-implant table
    interimplant_records : list of row dicts for the inter-implant distance table
    implant_csv          : output path for the per-implant CSV
    interimplant_csv     : output path for the inter-implant CSV

    Raises
    ------
    ValueError      — if either record list is empty.
    OSError         — if the output directory does not exist or is not writable.
    """
    if not implant_records:
        raise ValueError("implant_records is empty — nothing to write.")
    if not interimplant_records:
        raise ValueError("interimplant_records is empty — nothing to write.")

    # Ensure parent directories exist
    for path_str in (implant_csv, interimplant_csv):
        parent = pathlib.Path(path_str).parent
        if not parent.exists():
            raise OSError(
                f"Output directory does not exist: {parent}. "
                "Create it or update the output path in the config."
            )

    implant_df      = pd.DataFrame(implant_records)
    interimplant_df = pd.DataFrame(interimplant_records)

    implant_df.to_csv(implant_csv, index=False)
    interimplant_df.to_csv(interimplant_csv, index=False)

    print(f"\nResults written:")
    print(f"  {implant_csv}  ({len(implant_df)} rows)")
    print(f"  {interimplant_csv}  ({len(interimplant_df)} rows)")
