"""
dental-scan-measurements  —  main entry point

Usage:
    python main.py --config config/trial.yaml
"""

import argparse
import pathlib

import yaml

from src.loader import load_mesh
from src.cylinder_fit import extract_cylinders
from src.alignment import align_cylinders
from src.metrics import angular_error, translational_offset, interimplant_distance_errors
from src.reporter import write_results


def process_case(case: dict, base_dir: pathlib.Path):
    """
    Process one case: load gold standard, then compare each technique.
    Returns (implant_records, interimplant_records).
    """
    name = case["name"]
    n = case["n_implants"]
    print(f"\n{'='*60}")
    print(f"Case: {name}  ({n} implants)")
    print(f"{'='*60}")

    # --- Gold standard ---
    gold_path = base_dir / case["desktop_scanner"]
    print(f"\n[Gold standard]  {gold_path.name}")
    gold_mesh = load_mesh(str(gold_path))
    gold_cyls = extract_cylinders(gold_mesh, n)

    implant_rows = []
    interimplant_rows = []

    for technique_name, rel_path in case["techniques"].items():
        tech_path = base_dir / rel_path
        print(f"\n[{technique_name}]  {tech_path.name}")

        tech_mesh = load_mesh(str(tech_path))
        tech_cyls_original = extract_cylinders(tech_mesh, n)

        aligned_tech, R, t, perm, rmse = align_cylinders(gold_cyls, tech_cyls_original)
        print(f"    Alignment RMSE (centres): {rmse:.4f} mm")

        for i, (gold_c, tech_c) in enumerate(zip(gold_cyls, aligned_tech)):
            ang_err = angular_error(gold_c.axis, tech_c.axis)
            trans_err = translational_offset(gold_c.center, tech_c.center)

            implant_rows.append({
                "case":                   name,
                "technique":              technique_name,
                "implant_id":             i + 1,
                "angular_error_deg":      round(ang_err, 4),
                "translational_offset_mm": round(trans_err, 4),
                # Technique cylinder (aligned to gold frame)
                "tech_axis_x":   round(float(tech_c.axis[0]), 6),
                "tech_axis_y":   round(float(tech_c.axis[1]), 6),
                "tech_axis_z":   round(float(tech_c.axis[2]), 6),
                "tech_center_x": round(float(tech_c.center[0]), 4),
                "tech_center_y": round(float(tech_c.center[1]), 4),
                "tech_center_z": round(float(tech_c.center[2]), 4),
                "tech_radius_mm": round(float(tech_c.radius), 4),
                # Gold standard cylinder
                "gold_axis_x":   round(float(gold_c.axis[0]), 6),
                "gold_axis_y":   round(float(gold_c.axis[1]), 6),
                "gold_axis_z":   round(float(gold_c.axis[2]), 6),
                "gold_center_x": round(float(gold_c.center[0]), 4),
                "gold_center_y": round(float(gold_c.center[1]), 4),
                "gold_center_z": round(float(gold_c.center[2]), 4),
                "gold_radius_mm": round(float(gold_c.radius), 4),
            })

        pair_records = interimplant_distance_errors(gold_cyls, tech_cyls_original, perm)
        for rec in pair_records:
            interimplant_rows.append({
                "case":      name,
                "technique": technique_name,
                **rec,
            })

    return implant_rows, interimplant_rows


def main():
    parser = argparse.ArgumentParser(description="Dental scan accuracy measurement")
    parser.add_argument("--config", required=True, help="Path to YAML config file")
    args = parser.parse_args()

    config_path = pathlib.Path(args.config).resolve()
    base_dir = config_path.parent.parent  # config/ is one level below project root

    with open(config_path) as f:
        config = yaml.safe_load(f)

    all_implant_rows = []
    all_interimplant_rows = []

    for case in config["cases"]:
        imp, interp = process_case(case, base_dir)
        all_implant_rows.extend(imp)
        all_interimplant_rows.extend(interp)

    write_results(
        all_implant_rows,
        all_interimplant_rows,
        implant_csv=str(base_dir / config["output_csv"]),
        interimplant_csv=str(base_dir / config["output_interimplant_csv"]),
    )


if __name__ == "__main__":
    main()
