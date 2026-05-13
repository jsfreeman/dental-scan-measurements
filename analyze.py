"""
Statistical analysis of dental scan accuracy measurements.

Loads results_implants.csv and results_interimplant.csv and produces:
  - Descriptive statistics per technique
  - Outlier detection (IQR method)
  - Friedman test (non-parametric repeated-measures: same implants, 3 techniques)
  - Pairwise Wilcoxon signed-rank tests with Bonferroni correction
  - Correlation between angular and translational error
  - A composite analysis figure (images/analysis.png)

Usage:
    python analyze.py
"""

import pathlib
import sys

# Force UTF-8 output so special characters survive the Windows terminal
sys.stdout.reconfigure(encoding="utf-8")

import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from scipy import stats

# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

RESULTS_XLSX = "results.xlsx"
OUT_IMAGE    = "images/analysis.png"

_PALETTE = [
    "#1f77b4",  # blue
    "#ff7f0e",  # orange
    "#2ca02c",  # green
    "#d62728",  # red
    "#9467bd",  # purple
    "#8c564b",  # brown
]

ALPHA = 0.05   # significance threshold


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def section(title: str):
    print(f"\n{'='*65}")
    print(f"  {title}")
    print(f"{'='*65}")


def subsection(title: str):
    print(f"\n--- {title} ---")


def iqr_outliers(values: np.ndarray, labels: list):
    """Flag values outside 1.5 x IQR. Returns list of (label, value) tuples."""
    q1, q3 = np.percentile(values, [25, 75])
    iqr = q3 - q1
    lo, hi = q1 - 1.5 * iqr, q3 + 1.5 * iqr
    return [(lbl, val) for lbl, val in zip(labels, values)
            if val < lo or val > hi]


def interpret_p(p: float) -> str:
    if p < 0.001:
        return "p < 0.001 ***"
    if p < 0.01:
        return f"p = {p:.3f} **"
    if p < 0.05:
        return f"p = {p:.3f} *"
    return f"p = {p:.3f} (ns)"


def pairwise_wilcoxon(df: pd.DataFrame, metric: str, techniques: list,
                      technique_labels: dict):
    """
    Pairwise Wilcoxon signed-rank tests with Bonferroni correction.
    Uses paired data: the same implants measured by each technique.
    """
    pairs = [
        (techniques[i], techniques[j])
        for i in range(len(techniques))
        for j in range(i + 1, len(techniques))
    ]
    n_comparisons   = len(pairs)
    bonferroni_alpha = ALPHA / n_comparisons

    results = []
    for a, b in pairs:
        vals_a = df[df["technique"] == a].sort_values(["case", "implant_id"])[metric].values
        vals_b = df[df["technique"] == b].sort_values(["case", "implant_id"])[metric].values
        stat, p = stats.wilcoxon(vals_a, vals_b)
        results.append({
            "pair":   f"{technique_labels[a]}  vs  {technique_labels[b]}",
            "W":      stat,
            "p":      p,
            "p_corr": min(p * n_comparisons, 1.0),
            "sig":    p < bonferroni_alpha,
        })
    return results, bonferroni_alpha


# ---------------------------------------------------------------------------
# Main analysis
# ---------------------------------------------------------------------------

def analyze():
    base = pathlib.Path(__file__).parent

    print(f"Loading {RESULTS_XLSX}...")
    df   = pd.read_excel(base / RESULTS_XLSX, sheet_name="Per Implant")
    df_i = pd.read_excel(base / RESULTS_XLSX, sheet_name="Inter-Implant")

    techniques = sorted(df["technique"].unique())
    technique_colors = {t: _PALETTE[i % len(_PALETTE)] for i, t in enumerate(techniques)}
    technique_labels = {t: t for t in techniques}

    n_per_tech = df.groupby("technique").size().to_dict()
    print(f"Loaded: {len(df)} implant rows, {len(df_i)} implant-pair rows, "
          f"{df['case'].nunique()} cases, {len(techniques)} techniques.\n")

    section("DATASET OVERVIEW")
    print(f"  Total implant measurements : {len(df)}")
    print(f"  Cases                      : {sorted(df['case'].unique())}")
    print(f"  Techniques                 : {techniques}")
    print(f"  Implants per technique     : {list(n_per_tech.values())[0]}")

    # -----------------------------------------------------------------------
    # Descriptive statistics
    # -----------------------------------------------------------------------
    section("DESCRIPTIVE STATISTICS")

    for metric, unit in [("angular_error_deg", "deg"),
                          ("translational_offset_mm", "mm")]:
        subsection(metric.replace("_", " ").title())
        rows = []
        for tech in techniques:
            v = df[df["technique"] == tech][metric].values
            rows.append({
                "Technique": technique_labels[tech],
                "Mean":      f"{v.mean():.3f} {unit}",
                "Std":       f"{v.std(ddof=1):.3f}",
                "Median":    f"{np.median(v):.3f}",
                "Min":       f"{v.min():.3f}",
                "Max":       f"{v.max():.3f}",
            })
        print(pd.DataFrame(rows).to_string(index=False))

    subsection("Inter-implant distance error")
    rows = []
    for tech in techniques:
        v = df_i[df_i["technique"] == tech]["dist_error_mm"].values
        rows.append({
            "Technique": technique_labels[tech],
            "Mean":      f"{v.mean():.3f} mm",
            "Std":       f"{v.std(ddof=1):.3f}",
            "Median":    f"{np.median(v):.3f}",
            "Min":       f"{v.min():.4f}",
            "Max":       f"{v.max():.3f}",
        })
    print(pd.DataFrame(rows).to_string(index=False))

    # -----------------------------------------------------------------------
    # Normality (Shapiro-Wilk)
    # -----------------------------------------------------------------------
    section("NORMALITY TESTS (Shapiro-Wilk)")
    print("  p < 0.05 suggests non-normal distribution.")
    print(f"  {'Technique':<30} {'Metric':<30} {'W':>6}  Result")
    for tech in techniques:
        for metric in ("angular_error_deg", "translational_offset_mm"):
            v = df[df["technique"] == tech][metric].values
            w, p = stats.shapiro(v)
            flag = "NON-NORMAL *" if p < ALPHA else "normal"
            print(f"  {technique_labels[tech]:<30} {metric:<30} {w:.3f}  {interpret_p(p)}  -> {flag}")

    # -----------------------------------------------------------------------
    # Outlier detection
    # -----------------------------------------------------------------------
    section("OUTLIER DETECTION (1.5 x IQR rule)")

    any_outliers = False
    for metric, unit in [("angular_error_deg", "deg"),
                          ("translational_offset_mm", "mm")]:
        labels = (df["technique"] + " / " + df["case"] + " / implant " +
                  df["implant_id"].astype(str)).tolist()
        outliers = iqr_outliers(df[metric].values, labels)
        if outliers:
            any_outliers = True
            print(f"\n  {metric} (global):")
            for lbl, val in outliers:
                print(f"    [!]  {lbl}: {val:.4f} {unit}")

    if not any_outliers:
        print("  No global outliers detected.")

    print("\n  Per-technique outliers:")
    found = False
    for tech in techniques:
        for metric, unit in [("angular_error_deg", "deg"),
                              ("translational_offset_mm", "mm")]:
            sub = df[df["technique"] == tech]
            labels = ("case " + sub["case"] + " implant " +
                      sub["implant_id"].astype(str)).tolist()
            outliers = iqr_outliers(sub[metric].values, labels)
            if outliers:
                found = True
                for lbl, val in outliers:
                    print(f"    [!]  {technique_labels[tech]} / {metric}: {lbl} = {val:.4f} {unit}")
    if not found:
        print("  None.")

    # -----------------------------------------------------------------------
    # Friedman test
    # -----------------------------------------------------------------------
    section("FRIEDMAN TEST (repeated measures across 3 techniques)")
    print("  Tests whether at least one technique differs significantly.")
    print("  Used because: same implants measured by all 3 techniques (paired data).\n")

    for metric, unit in [("angular_error_deg", "deg"),
                          ("translational_offset_mm", "mm")]:
        groups = [
            df[df["technique"] == t].sort_values(["case", "implant_id"])[metric].values
            for t in techniques
        ]
        stat, p = stats.friedmanchisquare(*groups)
        verdict = "Significant difference detected." if p < ALPHA else "No significant difference."
        print(f"  {metric}:")
        print(f"    chi2 = {stat:.3f},  {interpret_p(p)}")
        print(f"    -> {verdict}\n")

    groups_i = [
        df_i[df_i["technique"] == t].sort_values(["case", "implant_i", "implant_j"])["dist_error_mm"].values
        for t in techniques
    ]
    stat, p = stats.friedmanchisquare(*groups_i)
    verdict = "Significant difference detected." if p < ALPHA else "No significant difference."
    print(f"  inter-implant distance error:")
    print(f"    chi2 = {stat:.3f},  {interpret_p(p)}")
    print(f"    -> {verdict}")

    # -----------------------------------------------------------------------
    # Pairwise Wilcoxon
    # -----------------------------------------------------------------------
    section("PAIRWISE WILCOXON SIGNED-RANK TESTS (Bonferroni corrected)")

    for metric in ("angular_error_deg", "translational_offset_mm"):
        results, bonf_alpha = pairwise_wilcoxon(df, metric, techniques, technique_labels)
        print(f"\n  {metric}  (Bonferroni alpha = {bonf_alpha:.4f}):")
        for r in results:
            sig = " <- SIGNIFICANT" if r["sig"] else ""
            print(f"    {r['pair']}")
            print(f"      W = {r['W']:.1f},  raw {interpret_p(r['p'])},  "
                  f"corrected p = {r['p_corr']:.4f}{sig}")

    # -----------------------------------------------------------------------
    # Correlation
    # -----------------------------------------------------------------------
    section("CORRELATION: Angular Error vs. Translational Offset")
    rho, p = stats.spearmanr(df["angular_error_deg"], df["translational_offset_mm"])
    strength = ("weak" if abs(rho) < 0.3 else "moderate" if abs(rho) < 0.6 else "strong")
    print(f"  Spearman rho = {rho:.3f},  {interpret_p(p)}")
    print(f"  -> {strength.capitalize()} correlation: angular and translational errors are "
          f"{'largely independent.' if strength == 'weak' else 'related.'}")

    # -----------------------------------------------------------------------
    # Summary conclusions
    # -----------------------------------------------------------------------
    section("SUMMARY CONCLUSIONS")

    ang_means   = {t: df[df["technique"] == t]["angular_error_deg"].mean() for t in techniques}
    trans_means = {t: df[df["technique"] == t]["translational_offset_mm"].mean() for t in techniques}
    dist_means  = {t: df_i[df_i["technique"] == t]["dist_error_mm"].mean() for t in techniques}
    best_ang    = min(ang_means,   key=ang_means.get)
    worst_ang   = max(ang_means,   key=ang_means.get)
    best_trans  = min(trans_means, key=trans_means.get)
    best_dist   = min(dist_means,  key=dist_means.get)

    print(f"""
  1. ANGULAR ACCURACY (implant tilt)
     Best:  {technique_labels[best_ang]} (mean {ang_means[best_ang]:.2f} deg)
     Worst: {technique_labels[worst_ang]} (mean {ang_means[worst_ang]:.2f} deg)
     Ratio: ~{ang_means[worst_ang]/ang_means[best_ang]:.1f}x higher error in worst vs best technique.

  2. TRANSLATIONAL ACCURACY (implant position)
     Best:  {technique_labels[best_trans]} (mean {trans_means[best_trans]:.4f} mm)
     All techniques:""")
    for t in techniques:
        print(f"       {technique_labels[t]}: {trans_means[t]:.4f} mm")
    print(f"""
  3. INTER-IMPLANT DISTANCES
     Best:  {technique_labels[best_dist]} (mean {dist_means[best_dist]:.4f} mm)
     All techniques:""")
    for t in techniques:
        print(f"       {technique_labels[t]}: {dist_means[t]:.4f} mm")
    print(f"""
  4. SAMPLE SIZE
     n = {list(n_per_tech.values())[0]} implants per technique across {df['case'].nunique()} cases.
""")

    # -----------------------------------------------------------------------
    # Figure
    # -----------------------------------------------------------------------
    section("GENERATING ANALYSIS FIGURE")

    colors       = [technique_colors[t] for t in techniques]
    short_labels = techniques
    n_tech       = len(techniques)

    fig = plt.figure(figsize=(18, 10))
    fig.suptitle(
        "Statistical Analysis — Intra-oral Scanning Technique Accuracy",
        fontsize=14, fontweight="bold", y=1.01,
    )

    # 1. Box + strip: angular error
    ax1 = fig.add_subplot(2, 3, 1)
    data_ang = [df[df["technique"] == t]["angular_error_deg"].values for t in techniques]
    bp = ax1.boxplot(data_ang, patch_artist=True, widths=0.5,
                     medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp["boxes"], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    for i, (vals, color) in enumerate(zip(data_ang, colors), start=1):
        ax1.scatter(np.random.normal(i, 0.06, len(vals)), vals,
                    color=color, zorder=5, s=35, alpha=0.9,
                    edgecolors="white", linewidths=0.5)
        ax1.text(i + 0.28, np.mean(vals), f"{np.mean(vals):.2f}°",
                 fontsize=7, va="center", fontweight="bold", color=color)
    ax1.set_xticks(range(1, n_tech + 1)); ax1.set_xticklabels(short_labels, fontsize=9)
    ax1.set_ylabel("Degrees", fontsize=9)
    ax1.set_title("Angular Error vs. Gold Standard", fontsize=10, fontweight="bold")
    ax1.yaxis.grid(True, linestyle="--", alpha=0.4); ax1.set_axisbelow(True)

    # 2. Box + strip: translational offset
    ax2 = fig.add_subplot(2, 3, 2)
    data_trans = [df[df["technique"] == t]["translational_offset_mm"].values for t in techniques]
    bp2 = ax2.boxplot(data_trans, patch_artist=True, widths=0.5,
                      medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp2["boxes"], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    for i, (vals, color) in enumerate(zip(data_trans, colors), start=1):
        ax2.scatter(np.random.normal(i, 0.06, len(vals)), vals,
                    color=color, zorder=5, s=35, alpha=0.9,
                    edgecolors="white", linewidths=0.5)
        ax2.text(i + 0.28, np.mean(vals), f"{np.mean(vals):.3f}",
                 fontsize=7, va="center", fontweight="bold", color=color)
    ax2.set_xticks(range(1, n_tech + 1)); ax2.set_xticklabels(short_labels, fontsize=9)
    ax2.set_ylabel("mm", fontsize=9)
    ax2.set_title("Translational Offset vs. Gold Standard", fontsize=10, fontweight="bold")
    ax2.yaxis.grid(True, linestyle="--", alpha=0.4); ax2.set_axisbelow(True)

    # 3. Box + strip: inter-implant distance error
    ax3 = fig.add_subplot(2, 3, 3)
    data_inter = [df_i[df_i["technique"] == t]["dist_error_mm"].values for t in techniques]
    bp3 = ax3.boxplot(data_inter, patch_artist=True, widths=0.5,
                      medianprops=dict(color="white", linewidth=2))
    for patch, color in zip(bp3["boxes"], colors):
        patch.set_facecolor(color); patch.set_alpha(0.7)
    for i, (vals, color) in enumerate(zip(data_inter, colors), start=1):
        ax3.scatter(np.random.normal(i, 0.06, len(vals)), vals,
                    color=color, zorder=5, s=20, alpha=0.9,
                    edgecolors="white", linewidths=0.5)
        ax3.text(i + 0.28, np.mean(vals), f"{np.mean(vals):.3f}",
                 fontsize=7, va="center", fontweight="bold", color=color)
    ax3.set_xticks(range(1, n_tech + 1)); ax3.set_xticklabels(short_labels, fontsize=9)
    ax3.set_ylabel("mm", fontsize=9)
    ax3.set_title("Inter-implant Distance Error", fontsize=10, fontweight="bold")
    ax3.yaxis.grid(True, linestyle="--", alpha=0.4); ax3.set_axisbelow(True)

    # 4. Scatter: angular vs translational, coloured by technique
    ax4 = fig.add_subplot(2, 3, 4)
    for tech, color in zip(techniques, colors):
        sub = df[df["technique"] == tech]
        ax4.scatter(sub["angular_error_deg"], sub["translational_offset_mm"],
                    color=color, label=technique_labels[tech],
                    s=60, alpha=0.85, edgecolors="white", linewidths=0.5)
    ax4.set_xlabel("Angular Error (deg)", fontsize=9)
    ax4.set_ylabel("Translational Offset (mm)", fontsize=9)
    ax4.set_title("Angular vs. Translational Error\n(each dot = one implant)",
                  fontsize=10, fontweight="bold")
    ax4.legend(fontsize=7)
    ax4.yaxis.grid(True, linestyle="--", alpha=0.4); ax4.set_axisbelow(True)
    rho, pval = stats.spearmanr(df["angular_error_deg"], df["translational_offset_mm"])
    ax4.text(0.05, 0.95, f"Spearman rho = {rho:.2f}\n{interpret_p(pval)}",
             transform=ax4.transAxes, fontsize=8, va="top",
             bbox=dict(boxstyle="round,pad=0.3", facecolor="lightyellow", alpha=0.8))

    # 5. Per-case mean angular error
    ax5 = fig.add_subplot(2, 3, 5)
    cases  = sorted(df["case"].unique())
    x      = np.arange(len(cases))
    bar_w  = 0.8 / n_tech
    for i, (tech, color) in enumerate(zip(techniques, colors)):
        means = [df[(df["technique"] == tech) & (df["case"] == c)]["angular_error_deg"].mean()
                 for c in cases]
        ax5.bar(x + i * bar_w, means, bar_w, color=color,
                label=technique_labels[tech], alpha=0.8)
    ax5.set_xticks(x + bar_w * (n_tech - 1) / 2); ax5.set_xticklabels([f"Case {c}" for c in cases], fontsize=9)
    ax5.set_ylabel("Mean Angular Error (deg)", fontsize=9)
    ax5.set_title("Angular Error by Case", fontsize=10, fontweight="bold")
    ax5.legend(fontsize=7); ax5.yaxis.grid(True, linestyle="--", alpha=0.4); ax5.set_axisbelow(True)

    # 6. Per-case mean translational offset
    ax6 = fig.add_subplot(2, 3, 6)
    for i, (tech, color) in enumerate(zip(techniques, colors)):
        means = [df[(df["technique"] == tech) & (df["case"] == c)]["translational_offset_mm"].mean()
                 for c in cases]
        ax6.bar(x + i * bar_w, means, bar_w, color=color,
                label=technique_labels[tech], alpha=0.8)
    ax6.set_xticks(x + bar_w * (n_tech - 1) / 2); ax6.set_xticklabels([f"Case {c}" for c in cases], fontsize=9)
    ax6.set_ylabel("Mean Translational Offset (mm)", fontsize=9)
    ax6.set_title("Translational Offset by Case", fontsize=10, fontweight="bold")
    ax6.legend(fontsize=7); ax6.yaxis.grid(True, linestyle="--", alpha=0.4); ax6.set_axisbelow(True)

    plt.tight_layout()
    out = base / OUT_IMAGE
    out.parent.mkdir(exist_ok=True)
    plt.savefig(out, dpi=150, bbox_inches="tight")
    plt.close(fig)
    print(f"  Saved: {out}")
    print("\nDone.")


if __name__ == "__main__":
    analyze()
