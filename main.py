"""
dental-scan-measurements — main entry point

Compares STL/PLY mesh files from multiple intra-oral scanning techniques against
a Desktop Scanner gold standard, then writes angular and translational error
measurements to CSV.

Usage
-----
    python main.py --config config/trial.yaml

The config file (YAML) must contain:
    output_csv            : path for the per-implant results CSV
    output_interimplant_csv : path for the inter-implant distance CSV
    cases                 : list of case entries, each with:
        name              : case identifier (used in output)
        n_implants        : number of implant scan bodies in each file
        desktop_scanner   : relative path to the gold-standard STL
        techniques        : dict mapping technique name → relative path (STL or PLY)
"""

import argparse
import pathlib
import sys

import yaml

from src.loader import load_mesh
from src.cylinder_fit import extract_cylinders
from src.alignment import align_cylinders
from src.metrics import angular_error, translational_offset, interimplant_distance_errors
from src.reporter import write_results

# Required top-level keys in the config file
_REQUIRED_CONFIG_KEYS = {"output_csv", "output_interimplant_csv", "cases"}

# Required keys within each case entry
_REQUIRED_CASE_KEYS = {"name", "n_implants", "desktop_scanner", "techniques"}


def _validate_config(config: dict) -> None:
    """
    Validate the parsed config dict and raise descriptive errors for missing or
    invalid fields before any files are opened.
    """
    missing = _REQUIRED_CONFIG_KEYS - config.keys()
    if missing:
        raise ValueError(f"Config is missing required keys: {missing}")

    if not isinstance(config["cases"], list) or len(config["cases"]) == 0:
        raise ValueError("Config 'cases' must be a non-empty list.")

    for idx, case in enumerate(config["cases"]):
        label = f"cases[{idx}]"

        missing_case = _REQUIRED_CASE_KEYS - case.keys()
        if missing_case:
            raise ValueError(f"{label} is missing required keys: {missing_case}")

        if not isinstance(case["n_implants"], int) or case["n_implants"] < 1:
            raise ValueError(
                f"{label}.n_implants must be a positive integer; "
                f"got {case['n_implants']!r}."
            )

        if not isinstance(case["techniques"], dict) or len(case["techniques"]) == 0:
            raise ValueError(f"{label}.techniques must be a non-empty dict.")


def _check_files_exist(config: dict, base_dir: pathlib.Path) -> None:
    """
    Verify that every mesh file referenced in the config actually exists on disk.
    Reports all missing files at once rather than failing on the first one.
    """
    missing = []

    for case in config["cases"]:
        gold_path = base_dir / case["desktop_scanner"]
        if not gold_path.exists():
            missing.append(str(gold_path))

        for name, rel_path in case["techniques"].items():
            tech_path = base_dir / rel_path
            if not tech_path.exists():
                missing.append(f"{str(tech_path)}  (technique: {name})")

    if missing:
        lines = "\n  ".join(missing)
        raise FileNotFoundError(
            f"The following mesh files referenced in the config were not found:\n  {lines}"
        )


def process_case(case: dict, base_dir: pathlib.Path):
    """
    Process one case: extract gold-standard cylinders, then compare each technique.

    For each technique file:
      1. Load the mesh.
      2. Extract N cylinders (connected components, or K-means fallback).
      3. Find the best rigid alignment to the gold-standard cylinders (Kabsch SVD).
      4. Compute per-implant angular and translational error.
      5. Compute inter-implant distance errors (alignment-independent).

    Returns
    -------
    implant_rows      : list of row dicts for the per-implant CSV
    interimplant_rows : list of row dicts for the inter-implant CSV
    """
    name = case["name"]
    n    = case["n_implants"]

    print(f"\n{'='*60}")
    print(f"Case: {name}  ({n} implants)")
    print(f"{'='*60}")

    # --- Load and process the gold-standard Desktop Scanner file ---
    gold_path = base_dir / case["desktop_scanner"]
    print(f"\n[Gold standard]  {gold_path.name}")
    gold_mesh = load_mesh(str(gold_path))
    gold_cyls = extract_cylinders(gold_mesh, n)

    implant_rows     = []
    interimplant_rows = []

    # --- Process each comparison technique ---
    for technique_name, rel_path in case["techniques"].items():
        tech_path = base_dir / rel_path
        print(f"\n[{technique_name}]  {tech_path.name}")

        tech_mesh         = load_mesh(str(tech_path))
        tech_cyls_original = extract_cylinders(tech_mesh, n)

        # Align the technique cylinders to the gold-standard coordinate frame
        aligned_tech, R, t, perm, rmse = align_cylinders(gold_cyls, tech_cyls_original)
        print(f"    Alignment RMSE (centres): {rmse:.4f} mm")

        # Per-implant error metrics
        for i, (gold_c, tech_c) in enumerate(zip(gold_cyls, aligned_tech)):
            ang_err   = angular_error(gold_c.axis, tech_c.axis)
            trans_err = translational_offset(gold_c.center, tech_c.center)

            implant_rows.append({
                "case":                    name,
                "technique":               technique_name,
                "implant_id":              i + 1,
                # Primary accuracy metrics
                "angular_error_deg":       round(ang_err, 4),
                "translational_offset_mm": round(trans_err, 4),
                # Technique cylinder parameters (transformed into gold frame)
                "tech_axis_x":    round(float(tech_c.axis[0]), 6),
                "tech_axis_y":    round(float(tech_c.axis[1]), 6),
                "tech_axis_z":    round(float(tech_c.axis[2]), 6),
                "tech_center_x":  round(float(tech_c.center[0]), 4),
                "tech_center_y":  round(float(tech_c.center[1]), 4),
                "tech_center_z":  round(float(tech_c.center[2]), 4),
                "tech_radius_mm": round(float(tech_c.radius), 4),
                # Gold-standard cylinder parameters for reference
                "gold_axis_x":    round(float(gold_c.axis[0]), 6),
                "gold_axis_y":    round(float(gold_c.axis[1]), 6),
                "gold_axis_z":    round(float(gold_c.axis[2]), 6),
                "gold_center_x":  round(float(gold_c.center[0]), 4),
                "gold_center_y":  round(float(gold_c.center[1]), 4),
                "gold_center_z":  round(float(gold_c.center[2]), 4),
                "gold_radius_mm": round(float(gold_c.radius), 4),
            })

        # Inter-implant distance errors (uses original tech centres — alignment-invariant)
        pair_records = interimplant_distance_errors(gold_cyls, tech_cyls_original, perm)
        for rec in pair_records:
            interimplant_rows.append({"case": name, "technique": technique_name, **rec})

    return implant_rows, interimplant_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Measure accuracy of intra-oral scanning techniques vs. Desktop Scanner gold standard.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python main.py --config config/trial.yaml",
    )
    parser.add_argument(
        "--config",
        required=True,
        metavar="FILE",
        help="Path to the YAML configuration file.",
    )
    args = parser.parse_args()

    # Resolve the config path and derive the project root from it
    config_path = pathlib.Path(args.config).resolve()

    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    # The config lives in  <project_root>/config/  so the project root is one level up
    base_dir = config_path.parent.parent

    # Load and validate the config
    with open(config_path) as f:
        config = yaml.safe_load(f)

    try:
        _validate_config(config)
        _check_files_exist(config, base_dir)
    except (ValueError, FileNotFoundError) as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(1)

    # Process all cases and collect results
    all_implant_rows      = []
    all_interimplant_rows = []

    for case in config["cases"]:
        try:
            imp, interp = process_case(case, base_dir)
        except Exception as exc:
            print(
                f"\nERROR processing case '{case.get('name', '?')}': {exc}",
                file=sys.stderr,
            )
            sys.exit(1)

        all_implant_rows.extend(imp)
        all_interimplant_rows.extend(interp)

    # Write output CSVs
    try:
        write_results(
            all_implant_rows,
            all_interimplant_rows,
            implant_csv=str(base_dir / config["output_csv"]),
            interimplant_csv=str(base_dir / config["output_interimplant_csv"]),
        )
    except (ValueError, OSError) as exc:
        print(f"ERROR writing results: {exc}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
