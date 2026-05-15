"""
Nexus-as-gold sensitivity analysis.

Reads per-implant cylinder data from results.xlsx and re-derives all accuracy
metrics treating Nexus photogrammetry as the gold standard instead of the
Desktop Scanner.

Because all cylinders in results.xlsx are already expressed in the Desktop
Scanner coordinate frame (each technique was Kabsch-aligned to Desktop), and
implant_id already encodes consistent cross-technique correspondences (both
TRIOS and Nexus were matched to the same Desktop implant ordering), we can:
  1. Use Nexus cylinder positions as the new reference per case.
  2. Apply a small Kabsch re-alignment of each technique to Nexus (within
     the Desktop frame) to minimise the global rigid-body residual vs Nexus.
  3. Report per-implant angular + translational errors against Nexus.

Cases without Nexus data are skipped.
"""

import pathlib

import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

EXCEL_PATH = "results.xlsx"
OUT_PNG    = "images/analysis_nexus_gold.png"

_PALETTE = ["#1f77b4", "#ff7f0e", "#2ca02c", "#d62728", "#9467bd"]


# ---------------------------------------------------------------------------
# Kabsch algorithm
# ---------------------------------------------------------------------------

def _kabsch(P: np.ndarray, Q: np.ndarray):
    """Return (R, t) such that  Q @ R.T + t  minimises RMSE(P, Q_aligned)."""
    mu_P = P.mean(axis=0)
    mu_Q = Q.mean(axis=0)
    H    = (Q - mu_Q).T @ (P - mu_P)
    U, _, Vt = np.linalg.svd(H)
    d = np.linalg.det(Vt.T @ U.T)
    D = np.diag([1.0, 1.0, d])
    R = Vt.T @ D @ U.T
    t = mu_P - mu_Q @ R.T
    return R, t


def _angular_error_deg(a: np.ndarray, b: np.ndarray) -> np.ndarray:
    """Unsigned angle (degrees) between paired (N,3) direction arrays."""
    a = a / np.linalg.norm(a, axis=1, keepdims=True)
    b = b / np.linalg.norm(b, axis=1, keepdims=True)
    dot = np.clip(np.abs(np.einsum("ij,ij->i", a, b)), 0.0, 1.0)
    return np.degrees(np.arccos(dot))


# ---------------------------------------------------------------------------
# Build comparison dataset
# ---------------------------------------------------------------------------

def _build_datasets(df: pd.DataFrame):
    """
    Returns (per_implant_df, inter_implant_df) with Nexus as gold standard.

    Techniques in output: Desktop, TRIOS, Shinning  (Nexus is the reference).
    """
    nexus    = df[df["technique"] == "Nexus"]
    trios    = df[df["technique"] == "TRIOS"]
    shinning = df[df["technique"] == "Shinning"]

    # Desktop Scanner cylinders live in the gold_* columns of any technique row.
    desktop = trios[["case", "implant_id",
                      "gold_axis_x", "gold_axis_y", "gold_axis_z",
                      "gold_center_x", "gold_center_y", "gold_center_z"]].copy()
    desktop = desktop.rename(columns={
        "gold_axis_x":   "tech_axis_x",   "gold_axis_y":   "tech_axis_y",
        "gold_axis_z":   "tech_axis_z",   "gold_center_x": "tech_center_x",
        "gold_center_y": "tech_center_y", "gold_center_z": "tech_center_z",
    })
    desktop["technique"] = "Desktop"

    compare = pd.concat([
        desktop,
        trios[["case", "technique", "implant_id",
               "tech_axis_x", "tech_axis_y", "tech_axis_z",
               "tech_center_x", "tech_center_y", "tech_center_z"]],
        shinning[["case", "technique", "implant_id",
                  "tech_axis_x", "tech_axis_y", "tech_axis_z",
                  "tech_center_x", "tech_center_y", "tech_center_z"]],
    ], ignore_index=True)

    cases = sorted(df["case"].unique())
    per_records   = []
    inter_records = []

    for case in cases:
        nex_case = nexus[nexus["case"] == case].sort_values("implant_id")
        if nex_case.empty:
            print(f"  Skipping {case} — no Nexus data")
            continue

        nex_centers = nex_case[["tech_center_x", "tech_center_y", "tech_center_z"]].values
        nex_axes    = nex_case[["tech_axis_x", "tech_axis_y", "tech_axis_z"]].values
        n           = len(nex_centers)

        for tech in ["Desktop", "TRIOS", "Shinning"]:
            tc = compare[(compare["case"] == case) &
                         (compare["technique"] == tech)].sort_values("implant_id")
            if tc.empty:
                continue

            tech_centers = tc[["tech_center_x", "tech_center_y", "tech_center_z"]].values
            tech_axes    = tc[["tech_axis_x",   "tech_axis_y",   "tech_axis_z"]].values
            implant_ids  = tc["implant_id"].values

            # Kabsch re-alignment within the Desktop frame: align tech to Nexus
            if len(tech_centers) >= 2:
                R, t        = _kabsch(nex_centers, tech_centers)
                aln_centers = tech_centers @ R.T + t
                aln_axes    = tech_axes    @ R.T
            else:
                aln_centers = tech_centers
                aln_axes    = tech_axes

            ang_errs   = _angular_error_deg(aln_axes, nex_axes)
            trans_errs = np.linalg.norm(aln_centers - nex_centers, axis=1)

            for j, imp_id in enumerate(implant_ids):
                per_records.append({
                    "case":                    case,
                    "technique":               tech,
                    "implant_id":              imp_id,
                    "angular_error_deg":       float(ang_errs[j]),
                    "translational_offset_mm": float(trans_errs[j]),
                })

            # Inter-implant: raw pairwise distances — no alignment needed
            for i in range(n):
                for j in range(i + 1, n):
                    tech_d = float(np.linalg.norm(tech_centers[i] - tech_centers[j]))
                    nex_d  = float(np.linalg.norm(nex_centers[i]  - nex_centers[j]))
                    inter_records.append({
                        "case":          case,
                        "technique":     tech,
                        "pair":          f"{i+1}-{j+1}",
                        "dist_error_mm": abs(tech_d - nex_d),
                    })

    return pd.DataFrame(per_records), pd.DataFrame(inter_records)


# ---------------------------------------------------------------------------
# Plotting helpers
# ---------------------------------------------------------------------------

def _box_strip(ax, data_list, labels, colors, mean_fmt: str, ylabel: str, title: str,
               unit: str = ""):
    bp = ax.boxplot(data_list, patch_artist=True, widths=0.5,
                    medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color)
        patch.set_alpha(0.7)
    for i, (vals, color) in enumerate(zip(data_list, colors), start=1):
        ax.scatter(np.random.normal(i, 0.06, len(vals)), vals,
                   color=color, zorder=5, s=30, alpha=0.9,
                   edgecolors="white", linewidths=0.5)
        mean_val = float(np.mean(vals))
        ax.text(i + 0.28, mean_val, f"{mean_val:{mean_fmt}}{unit}",
                fontsize=7, va="center", fontweight="bold", color=color)
    ax.set_xticks(range(1, len(labels) + 1))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel(ylabel, fontsize=9)
    ax.set_title(title, fontsize=10, fontweight="bold")
    ax.yaxis.grid(True, linestyle="--", alpha=0.4)
    ax.set_axisbelow(True)


def _comparison_table(ax,
                       df_desk: pd.DataFrame, df_i_desk: pd.DataFrame,
                       per_nex: pd.DataFrame, inter_nex: pd.DataFrame):
    """
    Render a side-by-side comparison table showing mean errors under each gold standard.

    Rows:  TRIOS, Shinning  (techniques that appear under BOTH gold standards)
           Nexus (vs Desktop)  — how Nexus compares to Desktop gold
           Desktop (vs Nexus)  — how Desktop compares to Nexus gold
    """
    ax.axis("off")

    col_labels = [
        "Technique",
        "Angular\nvs Desktop gold",  "Angular\nvs Nexus gold",
        "Trans\nvs Desktop gold",    "Trans\nvs Nexus gold",
        "Inter-impl\nvs Desktop gold", "Inter-impl\nvs Nexus gold",
    ]

    def _mean(df, tech, col):
        vals = df[df["technique"] == tech][col]
        return f"{vals.mean():.2f}°" if col == "angular_error_deg" else f"{vals.mean():.3f}mm"

    rows = [
        # Shared techniques (appear in both)
        ["TRIOS",
         _mean(df_desk,  "TRIOS",    "angular_error_deg"),
         _mean(per_nex,  "TRIOS",    "angular_error_deg"),
         _mean(df_desk,  "TRIOS",    "translational_offset_mm"),
         _mean(per_nex,  "TRIOS",    "translational_offset_mm"),
         _mean(df_i_desk,"TRIOS",    "dist_error_mm"),
         _mean(inter_nex,"TRIOS",    "dist_error_mm")],
        ["Shinning",
         _mean(df_desk,  "Shinning", "angular_error_deg"),
         _mean(per_nex,  "Shinning", "angular_error_deg"),
         _mean(df_desk,  "Shinning", "translational_offset_mm"),
         _mean(per_nex,  "Shinning", "translational_offset_mm"),
         _mean(df_i_desk,"Shinning", "dist_error_mm"),
         _mean(inter_nex,"Shinning", "dist_error_mm")],
        # Nexus accuracy vs Desktop gold
        ["Nexus (vs Desktop)",
         _mean(df_desk,  "Nexus",    "angular_error_deg"),
         "—  (reference)",
         _mean(df_desk,  "Nexus",    "translational_offset_mm"),
         "—  (reference)",
         _mean(df_i_desk,"Nexus",    "dist_error_mm"),
         "—  (reference)"],
        # Desktop accuracy vs Nexus gold
        ["Desktop (vs Nexus)",
         "—  (reference)",
         _mean(per_nex,  "Desktop",  "angular_error_deg"),
         "—  (reference)",
         _mean(per_nex,  "Desktop",  "translational_offset_mm"),
         "—  (reference)",
         _mean(inter_nex,"Desktop",  "dist_error_mm")],
    ]

    tbl = ax.table(cellText=rows, colLabels=col_labels, loc="center", cellLoc="center")
    tbl.auto_set_font_size(False)
    tbl.set_fontsize(8.5)
    tbl.scale(1, 1.9)

    for j in range(len(col_labels)):
        tbl[0, j].set_facecolor("#dddddd")
        tbl[0, j].set_text_props(fontweight="bold")

    # Highlight Desktop and Nexus reference rows
    for j in range(len(col_labels)):
        tbl[3, j].set_facecolor("#f0f4ff")
        tbl[4, j].set_facecolor("#f0f4ff")

    ax.set_title("Mean errors: Desktop gold vs Nexus gold — do rankings change?",
                 fontsize=10, fontweight="bold", pad=14)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main():
    df   = pd.read_excel(EXCEL_PATH, sheet_name="Per Implant")
    df_i = pd.read_excel(EXCEL_PATH, sheet_name="Inter-Implant")

    print("Building Nexus-as-gold dataset …")
    per_nex, inter_nex = _build_datasets(df)

    techniques = ["Desktop", "TRIOS", "Shinning"]
    colors     = [_PALETTE[i] for i in range(len(techniques))]

    # --- Console summary ---
    print("\n=== Nexus as Gold Standard ===\n")
    for tech in techniques:
        t = per_nex[per_nex["technique"] == tech]
        d = inter_nex[inter_nex["technique"] == tech]
        print(f"  {tech:10s}  "
              f"ang  mean={t['angular_error_deg'].mean():.2f}°  "
              f"med={t['angular_error_deg'].median():.2f}°  "
              f"max={t['angular_error_deg'].max():.2f}°  |  "
              f"trans mean={t['translational_offset_mm'].mean():.3f}mm  "
              f"med={t['translational_offset_mm'].median():.3f}mm  "
              f"max={t['translational_offset_mm'].max():.3f}mm  |  "
              f"inter mean={d['dist_error_mm'].mean():.3f}mm")

    print("\n=== Desktop as Gold Standard (from Excel) ===\n")
    for tech in sorted(df["technique"].unique()):
        t = df[df["technique"] == tech]
        d = df_i[df_i["technique"] == tech]
        print(f"  {tech:22s}  "
              f"ang  mean={t['angular_error_deg'].mean():.2f}°  "
              f"med={t['angular_error_deg'].median():.2f}°  "
              f"max={t['angular_error_deg'].max():.2f}°  |  "
              f"trans mean={t['translational_offset_mm'].mean():.3f}mm  "
              f"med={t['translational_offset_mm'].median():.3f}mm  |  "
              f"inter mean={d['dist_error_mm'].mean():.3f}mm")

    # --- Figure: 2 rows × 3 cols ---
    fig = plt.figure(figsize=(18, 10))
    fig.suptitle(
        "Sensitivity analysis: Nexus photogrammetry as gold standard\n"
        "(Desktop Scanner, TRIOS and Shinning compared to Nexus; "
        "bottom table contrasts both gold standards)",
        fontsize=12, fontweight="bold",
    )

    ax1 = fig.add_subplot(2, 3, 1)
    ax2 = fig.add_subplot(2, 3, 2)
    ax3 = fig.add_subplot(2, 3, 3)

    data_ang   = [per_nex[per_nex["technique"] == t]["angular_error_deg"].values
                  for t in techniques]
    data_trans = [per_nex[per_nex["technique"] == t]["translational_offset_mm"].values
                  for t in techniques]
    data_inter = [inter_nex[inter_nex["technique"] == t]["dist_error_mm"].values
                  for t in techniques]

    _box_strip(ax1, data_ang,   techniques, colors, ".2f",
               "Degrees (°)", "Angular Error vs Nexus", unit="°")
    _box_strip(ax2, data_trans, techniques, colors, ".3f",
               "mm", "Translational Offset vs Nexus")
    _box_strip(ax3, data_inter, techniques, colors, ".3f",
               "mm", "Inter-Implant Distance Error vs Nexus")

    ax_tbl = fig.add_subplot(2, 1, 2)
    _comparison_table(ax_tbl, df, df_i, per_nex, inter_nex)

    plt.tight_layout()
    pathlib.Path("images").mkdir(exist_ok=True)
    fig.savefig(OUT_PNG, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"\nSaved: {OUT_PNG}")


if __name__ == "__main__":
    main()
