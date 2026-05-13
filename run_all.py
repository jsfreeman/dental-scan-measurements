"""
run_all.py — run the full dental scan measurement pipeline in one command.

Runs the three steps in order:
  1. main.py      — fit cylinders, align, write CSVs
  2. visualize.py — generate per-case PNG charts
  3. analyze.py   — statistical analysis and summary chart

Usage:
    python run_all.py
    python run_all.py --config config/trial.yaml
"""

import argparse
import pathlib
import subprocess
import sys
import time

import yaml


def _step(label: str, cmd: list, project_root: pathlib.Path) -> None:
    width = 65
    print(f"\n{'=' * width}")
    print(f"  {label}")
    print(f"{'=' * width}\n")
    result = subprocess.run(cmd, cwd=project_root)
    if result.returncode != 0:
        print(f"\nERROR: step failed with exit code {result.returncode}.",
              file=sys.stderr)
        sys.exit(result.returncode)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run the full dental scan measurement pipeline.",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="Example:\n  python run_all.py --config config/trial.yaml",
    )
    parser.add_argument(
        "--config", default="config/trial.yaml", metavar="FILE",
        help="Path to the YAML config file (default: config/trial.yaml).",
    )
    args = parser.parse_args()

    config_path = pathlib.Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: config file not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    project_root = pathlib.Path(__file__).parent
    py = sys.executable   # same Python interpreter that launched this script

    with open(config_path) as f:
        config = yaml.safe_load(f)

    n_cases = len(config.get("cases", []))
    print(f"Starting pipeline: {n_cases} case(s) from {config_path.name}")

    t0 = time.time()

    _step("Step 1/3 — Measure accuracy",
          [py, "main.py", "--config", args.config], project_root)

    _step("Step 2/3 — Generate visualisations",
          [py, "visualize.py", "--config", args.config], project_root)

    _step("Step 3/3 — Statistical analysis",
          [py, "analyze.py"], project_root)

    elapsed = time.time() - t0

    # -----------------------------------------------------------------------
    # Report produced files
    # -----------------------------------------------------------------------
    produced = []

    xlsx = project_root / "results.xlsx"
    if xlsx.exists():
        produced.append(xlsx)

    images_dir = project_root / "images"
    if images_dir.exists():
        produced.extend(sorted(images_dir.glob("*.pdf")))
        produced.extend(sorted(images_dir.glob("*.png")))

    width = 65
    print(f"\n{'=' * width}")
    print(f"  PIPELINE COMPLETE  ({elapsed / 60:.1f} min)")
    print(f"{'=' * width}")
    print(f"\n{len(produced)} file(s) produced:\n")
    for p in produced:
        size = p.stat().st_size
        size_str = f"{size / 1024:.0f} KB" if size < 1_000_000 else f"{size / 1_048_576:.1f} MB"
        print(f"  {p.relative_to(project_root)}  ({size_str})")
    print()


if __name__ == "__main__":
    main()
