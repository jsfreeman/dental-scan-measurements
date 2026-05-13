"""
Visualise fitted cylinders for each case and technique.

For each case, generates a PNG with three panels:
  Left:   3-D view of all cylinders (gold standard + 3 techniques) in the aligned
          coordinate frame, colour-coded by technique.
  Centre: Bar chart of angular error per implant per technique.
  Right:  Bar chart of translational offset per implant per technique.

Usage:
    python visualize.py --config config/trial.yaml [--outdir images]
"""

import argparse
import pathlib
import sys

import matplotlib
matplotlib.use("Agg")          # write files without needing a display
import matplotlib.pyplot as plt
import matplotlib.patches as mpatches
from matplotlib.backends.backend_pdf import PdfPages
import numpy as np
import yaml

from src.loader import load_mesh
from src.cylinder_fit import extract_cylinders, Cylinder
from src.alignment import align_cylinders
from src.metrics import angular_error, translational_offset


# ---------------------------------------------------------------------------
# Visual style
# ---------------------------------------------------------------------------

# Gold standard colour (fixed) and a rotating palette for techniques
_GOLD_COLOR = "#111111"
_COLOR_PALETTE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
]


def _build_color_map(technique_names: list[str]) -> dict[str, str]:
    """Assign a colour from the palette to each technique name, in sorted order."""
    return {name: _COLOR_PALETTE[i % len(_COLOR_PALETTE)]
            for i, name in enumerate(sorted(technique_names))}

# Visual parameters for cylinder drawing
CYLINDER_DRAW_HEIGHT_MM = 5.0   # approximate scan-body height used for drawing only
CYLINDER_THETA_STEPS    = 40    # angular resolution for the cylinder surface mesh
CYLINDER_WALL_ALPHA     = 0.25  # transparency of the cylinder surface
AXIS_LINE_ALPHA         = 0.9   # transparency of the axis line


def _perp_basis(v: np.ndarray):
    """Return two unit vectors perpendicular to v (same method as cylinder_fit.py)."""
    v = v / np.linalg.norm(v)
    helper = np.array([1.0, 0.0, 0.0]) if abs(v[0]) < 0.9 else np.array([0.0, 1.0, 0.0])
    e1 = np.cross(v, helper)
    e1 /= np.linalg.norm(e1)
    e2 = np.cross(v, e1)
    return e1, e2


def _draw_cylinder(ax, cyl: Cylinder, color: str, label: str = None):
    """
    Draw a cylinder on a 3-D matplotlib axis.

    Renders:
      - A translucent cylindrical surface (helps see orientation at a glance).
      - A solid axis line extending slightly beyond the cylinder ends.
      - A filled circle at the centre point.
    """
    C, A, R = cyl.center, cyl.axis / np.linalg.norm(cyl.axis), cyl.radius
    H  = CYLINDER_DRAW_HEIGHT_MM
    e1, e2 = _perp_basis(A)

    theta  = np.linspace(0, 2 * np.pi, CYLINDER_THETA_STEPS)
    t_vals = np.array([-H / 2, H / 2])
    Theta, T = np.meshgrid(theta, t_vals)

    # Parametric cylinder surface: C + t·A + r·cos(θ)·e1 + r·sin(θ)·e2
    X = C[0] + T * A[0] + R * np.cos(Theta) * e1[0] + R * np.sin(Theta) * e2[0]
    Y = C[1] + T * A[1] + R * np.cos(Theta) * e1[1] + R * np.sin(Theta) * e2[1]
    Z = C[2] + T * A[2] + R * np.cos(Theta) * e1[2] + R * np.sin(Theta) * e2[2]

    ax.plot_surface(X, Y, Z, color=color, alpha=CYLINDER_WALL_ALPHA, linewidth=0)

    # Axis line: extends half a cylinder height beyond each end cap
    p1 = C - A * (H / 2 + 1.0)
    p2 = C + A * (H / 2 + 1.0)
    ax.plot(
        [p1[0], p2[0]], [p1[1], p2[1]], [p1[2], p2[2]],
        color=color, linewidth=2.5, alpha=AXIS_LINE_ALPHA, label=label,
    )

    # Centre dot
    ax.scatter(*C, color=color, s=60, zorder=10, depthshade=False)


def _make_legend_patches(technique_names: list[str],
                         color_map: dict[str, str]) -> list[mpatches.Patch]:
    """Build coloured legend patches for the 3-D plot."""
    patches = [
        mpatches.Patch(color=_GOLD_COLOR, label="Gold Standard (Desktop)")
    ]
    for name in technique_names:
        patches.append(mpatches.Patch(color=color_map[name], label=name.replace("_", " ")))
    return patches


def _plot_3d(ax, gold_cyls: list[Cylinder],
             aligned_by_technique: dict[str, list[Cylinder]],
             color_map: dict[str, str]):
    """
    Plot all cylinders (gold + each technique) on a shared 3-D axis.
    Cylinders are already in the aligned (gold) coordinate frame.
    """
    # Draw gold-standard cylinders first so they are visually prominent
    for cyl in gold_cyls:
        _draw_cylinder(ax, cyl, color=_GOLD_COLOR)

    # Draw each technique's cylinders
    for tech_name, cyls in aligned_by_technique.items():
        for cyl in cyls:
            _draw_cylinder(ax, cyl, color=color_map[tech_name])

    # Axis labels and equal aspect ratio
    ax.set_xlabel("X (mm)", fontsize=8)
    ax.set_ylabel("Y (mm)", fontsize=8)
    ax.set_zlabel("Z (mm)", fontsize=8)
    ax.tick_params(labelsize=7)

    # Set a viewing angle that shows all cylinders well
    ax.view_init(elev=20, azim=-60)

    # Force equal aspect ratio by padding to a cubic bounding box
    all_centers = np.array([c.center for c in gold_cyls] +
                           [c.center for cyls in aligned_by_technique.values()
                            for c in cyls])
    mid   = all_centers.mean(axis=0)
    span  = (all_centers.max(axis=0) - all_centers.min(axis=0)).max() / 2 + 8
    ax.set_xlim(mid[0] - span, mid[0] + span)
    ax.set_ylim(mid[1] - span, mid[1] + span)
    ax.set_zlim(mid[2] - span, mid[2] + span)


def _plot_error_bars(ax_ang, ax_trans,
                     gold_cyls: list[Cylinder],
                     aligned_by_technique: dict[str, list[Cylinder]],
                     n: int,
                     color_map: dict[str, str]):
    """
    Plot per-implant angular error and translational offset as grouped bar charts.
    """
    technique_names = list(aligned_by_technique.keys())
    n_tech  = len(technique_names)
    x       = np.arange(1, n + 1)                # implant IDs 1..N
    width   = 0.8 / n_tech                        # bar width within each implant group
    offsets = np.linspace(-(n_tech - 1) / 2, (n_tech - 1) / 2, n_tech) * width

    for i, tech_name in enumerate(technique_names):
        cyls  = aligned_by_technique[tech_name]
        color = color_map[tech_name]

        ang_errs   = [angular_error(gold_cyls[j].axis, cyls[j].axis) for j in range(n)]
        trans_errs = [translational_offset(gold_cyls[j].center, cyls[j].center) for j in range(n)]

        ax_ang.bar(
            x + offsets[i], ang_errs,
            width=width, color=color, alpha=0.85,
            label=tech_name.replace("_", " "),
        )
        ax_trans.bar(
            x + offsets[i], trans_errs,
            width=width, color=color, alpha=0.85,
        )

    for ax, ylabel, title in [
        (ax_ang,   "Degrees (°)",  "Angular Error vs. Gold Standard"),
        (ax_trans, "mm",           "Translational Offset vs. Gold Standard"),
    ]:
        ax.set_xlabel("Implant ID", fontsize=9)
        ax.set_ylabel(ylabel, fontsize=9)
        ax.set_title(title, fontsize=10, fontweight="bold")
        ax.set_xticks(x)
        ax.tick_params(labelsize=8)
        ax.yaxis.grid(True, linestyle="--", alpha=0.5)
        ax.set_axisbelow(True)

    ax_ang.legend(fontsize=7, loc="upper right")


# ---------------------------------------------------------------------------
# Per-case visualisation
# ---------------------------------------------------------------------------

def visualise_case(case: dict, base_dir: pathlib.Path, pdf: PdfPages,
                   color_map: dict[str, str],
                   case_num: int = 0, n_cases: int = 0):
    """
    Run the pipeline for one case and add a page to the PDF.

    Layout:
      [3-D cylinder view] | [angular error chart] | [translational offset chart]
    """
    name   = case["name"]
    n      = case["n_implants"]
    prefix = f"[Case {case_num}/{n_cases}] " if case_num else ""
    print(f"\n{prefix}{name}  ({n} implants)")

    # Load and process gold standard
    gold_mesh = load_mesh(str(base_dir / case["desktop_scanner"]))
    gold_cyls = extract_cylinders(gold_mesh, n)

    # Align each technique and collect results
    aligned_by_technique: dict[str, list[Cylinder]] = {}

    for tech_name, rel_path in case["techniques"].items():
        print(f"  [{tech_name}]")
        tech_mesh  = load_mesh(str(base_dir / rel_path))
        tech_cyls  = extract_cylinders(tech_mesh, n)
        aligned, *_ = align_cylinders(gold_cyls, tech_cyls)
        aligned_by_technique[tech_name] = aligned

    # --- Build figure ---
    fig = plt.figure(figsize=(18, 6))
    fig.suptitle(
        f"Case {name} — Cylinder comparison across scanning techniques\n"
        f"(Black = Desktop Scanner gold standard, coloured = comparison techniques)",
        fontsize=12, fontweight="bold", y=1.01,
    )

    # 3-D plot occupies the left third
    ax3d = fig.add_subplot(1, 3, 1, projection="3d")
    ax3d.set_title("3-D cylinder view (aligned frame)", fontsize=10, fontweight="bold")
    _plot_3d(ax3d, gold_cyls, aligned_by_technique, color_map)
    ax3d.legend(
        handles=_make_legend_patches(list(aligned_by_technique.keys()), color_map),
        fontsize=7, loc="upper left",
    )

    # Error charts occupy centre and right
    ax_ang   = fig.add_subplot(1, 3, 2)
    ax_trans = fig.add_subplot(1, 3, 3)
    _plot_error_bars(ax_ang, ax_trans, gold_cyls, aligned_by_technique, n, color_map)

    plt.tight_layout()
    pdf.savefig(fig, bbox_inches="tight")
    plt.close(fig)
    print(f"  Added to PDF.")


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(
        description="Generate cylinder visualisations for each case in a config file.",
    )
    parser.add_argument(
        "--config", required=True, metavar="FILE",
        help="Path to the YAML configuration file.",
    )
    parser.add_argument(
        "--outdir", default="images", metavar="DIR",
        help="Directory to write PNG files into (default: images/).",
    )
    args = parser.parse_args()

    config_path = pathlib.Path(args.config).resolve()
    if not config_path.exists():
        print(f"ERROR: config not found: {config_path}", file=sys.stderr)
        sys.exit(1)

    base_dir = config_path.parent.parent
    outdir   = base_dir / args.outdir
    outdir.mkdir(exist_ok=True)

    with open(config_path) as f:
        config = yaml.safe_load(f)

    n_cases  = len(config["cases"])
    pdf_path = outdir / "case_charts.pdf"
    print(f"Generating {n_cases} case chart(s) -> {pdf_path}")

    all_techniques = sorted({
        tech_name
        for case in config["cases"]
        for tech_name in case["techniques"]
    })
    color_map = _build_color_map(all_techniques)

    with PdfPages(pdf_path) as pdf:
        for i, case in enumerate(config["cases"], 1):
            try:
                visualise_case(case, base_dir, pdf, color_map, case_num=i, n_cases=n_cases)
            except Exception as exc:
                print(f"ERROR on case '{case.get('name', '?')}': {exc}", file=sys.stderr)
                sys.exit(1)

    print(f"\nDone. {n_cases} page(s) written to {pdf_path}")


if __name__ == "__main__":
    main()
