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
import datetime
import pathlib
import subprocess
import sys
import time

import yaml


def _step(label: str, cmd: list, project_root: pathlib.Path, log,
          counts: dict) -> None:
    width = 65
    header = f"\n{'=' * width}\n  {label}\n{'=' * width}\n"
    sys.stdout.write(header)
    sys.stdout.flush()
    log.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]  {label}\n{'=' * width}\n")
    log.flush()

    proc = subprocess.Popen(
        cmd, cwd=project_root,
        stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
    )
    for raw in iter(proc.stdout.readline, b""):
        line = raw.decode("utf-8", errors="replace")
        sys.stdout.write(line)
        sys.stdout.flush()
        log.write(line)
        log.flush()
        if "Warning:" in line or "WARNING:" in line:
            counts["warnings"] += 1
        elif "Error:" in line or "ERROR:" in line:
            counts["errors"] += 1
    proc.wait()

    if proc.returncode != 0:
        msg = f"\nERROR: step failed with exit code {proc.returncode}.\n"
        sys.stderr.write(msg)
        log.write(msg)
        log.flush()
        counts["errors"] += 1
        sys.exit(proc.returncode)


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
    parser.add_argument(
        "--segmentation",
        choices=["components", "kmeans"],
        default="components",
        help="Cylinder segmentation strategy passed to main.py (default: components).",
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

    logs_dir = project_root / "logs"
    logs_dir.mkdir(exist_ok=True)
    log_path = logs_dir / f"pipeline_{datetime.datetime.now():%Y%m%d_%H%M%S}.log"

    banner = f"Starting pipeline: {n_cases} case(s) from {config_path.name}"
    print(banner)
    print(f"Log: {log_path.relative_to(project_root)}")

    t0 = time.time()

    counts = {"warnings": 0, "errors": 0}

    with open(log_path, "w", encoding="utf-8") as log:
        log.write(f"[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]  {banner}\n")
        log.flush()

        _step("Step 1/3 — Measure accuracy",
              [py, "main.py", "--config", args.config, "--segmentation", args.segmentation],
              project_root, log, counts)

        _step("Step 2/3 — Generate visualisations",
              [py, "visualize.py", "--config", args.config],
              project_root, log, counts)

        _step("Step 3/3 — Statistical analysis",
              [py, "analyze.py"], project_root, log, counts)

        elapsed = time.time() - t0

        # -------------------------------------------------------------------
        # Report produced files
        # -------------------------------------------------------------------
        produced = []

        xlsx = project_root / "results.xlsx"
        if xlsx.exists():
            produced.append(xlsx)

        images_dir = project_root / "images"
        if images_dir.exists():
            produced.extend(sorted(images_dir.glob("*.pdf")))
            produced.extend(sorted(images_dir.glob("*.png")))

        width = 65
        summary_lines = [
            f"\n{'=' * width}",
            f"  PIPELINE COMPLETE  ({elapsed / 60:.1f} min)",
            f"{'=' * width}",
            f"\n{len(produced)} file(s) produced:\n",
        ]
        for p in produced:
            size = p.stat().st_size
            size_str = f"{size / 1024:.0f} KB" if size < 1_000_000 else f"{size / 1_048_576:.1f} MB"
            summary_lines.append(f"  {p.relative_to(project_root)}  ({size_str})")
        summary_lines.append(f"\n  Log: {log_path.relative_to(project_root)}")

        w, e = counts["warnings"], counts["errors"]
        warn_str  = f"{w} {'warning' if w == 1 else 'warnings'}"
        error_str = f"{e} {'error' if e == 1 else 'errors'}"
        summary_lines.append(f"  {warn_str}, {error_str}")
        summary_lines.append("")

        summary = "\n".join(summary_lines)
        print(summary)
        log.write(f"\n[{datetime.datetime.now():%Y-%m-%d %H:%M:%S}]{summary}\n")


if __name__ == "__main__":
    main()
