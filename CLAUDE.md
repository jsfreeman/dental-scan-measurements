# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this project does

Measures how accurately three intra-oral scanning techniques (TRIOS intraoral scanner, Nexus photogrammetry, Shinning photogrammetry) reproduce the position and orientation of dental implants relative to a Desktop Scanner gold standard. Each patient ("case") has N implant scan bodies; all techniques are compared by fitting cylinders to those scan bodies and computing angular and translational error.

## Running the pipeline

```bash
# Full pipeline (recommended) — measures, visualises, analyses in sequence
python run_all.py --config config/trial.yaml

# Individual steps
python main.py --config config/trial.yaml       # cylinder fitting + alignment → results.xlsx
python main.py --config config/trial.yaml --segmentation kmeans  # force K-means segmentation
python visualize.py --config config/trial.yaml  # per-case 3-D + bar charts → images/case_charts.pdf
python analyze.py                               # statistics + box plots → images/analysis.png

# Sensitivity analysis: Nexus as gold standard instead of Desktop Scanner
python analyze_nexus_gold.py
```

`analyze.py` reads `results.xlsx` from the project root (not a CSV). The config path resolves mesh file paths relative to `config_path.parent.parent` (i.e., the project root, not the config directory).

## Architecture

The pipeline is a straight linear chain with no shared state between steps:

```
config/trial.yaml
       │
       ▼
main.py  ──► src/loader.py        load STL/PLY → trimesh.Trimesh
         ──► src/cylinder_fit.py  extract N cylinders per mesh
         ──► src/alignment.py     Kabsch SVD alignment to gold standard
         ──► src/metrics.py       angular error + translational offset
         ──► src/reporter.py      write results.xlsx (3 sheets)
       │
       ▼
visualize.py  reads config + meshes directly (re-runs cylinder extraction)
analyze.py    reads results.xlsx; writes images/analysis.png
```

`analyze_nexus_gold.py` is a standalone sensitivity-analysis script that reads `results.xlsx` and re-derives all metrics using Nexus as the reference instead of Desktop Scanner.

## Cylinder extraction: the most important algorithm

`src/cylinder_fit.py:extract_cylinders()` is the heart of the pipeline. It:

1. **Splits mesh into connected components** (preferred path). Takes the N largest components — for Desktop/TRIOS this isolates cylindrical shafts (5 sub-components per scan body; the 5 largest are the N shafts).
2. **Falls back to K-means** if fewer than N connected components exist (rare; photogrammetry meshes can be a single body).
3. **Fits a cylinder to each cluster** via PCA (axis = first principal component) + algebraic circle fit (center + radius) on the projection perpendicular to the axis.

**Critical known issue — Shinning STL files contain closed solid geometry:** Desktop, TRIOS, and Nexus meshes are open outer-shell meshes (all surface points are on the outer cylindrical surface, minimum radial distance from axis ≥ 2.06 mm). Shinning meshes are closed solids that include inner hollow geometry (hex connection cavity). About 12% of Shinning surface points are at radius < 2.3 mm from the cylinder axis — these inner-surface points bias the algebraic circle fit, pulling the fitted center ~0.4 mm away from the true outer cylinder axis in a direction determined by the hex orientation angle (which differs per implant). This produces apparent translational errors that are a measurement artifact.

**Corrected results after filtering Shinning to outer surface (modal-radius filter):**
- Shinning translational error: 0.050 mm (vs 0.085 mm reported, artifact-inflated)
- Shinning angular error: 2.25° (vs 2.44°)
- Both match TRIOS (0.051 mm / 2.37°) — the two techniques are actually equivalent

**The fix (not yet implemented in the pipeline):** One of these approaches:
1. **Normal-vector filter** — after sampling, keep only points where `face_normal · (point − centroid) > 0` (outward-facing). Two extra lines; requires consistent mesh normals.
2. **Convex hull sampling** — replace `trimesh.sample.sample_surface(part, n)` with `trimesh.sample.sample_surface(part.convex_hull, n)`. One-line change; geometrically guaranteed to include only outer surface; preferred.
3. **Modal-radius filter** — compute rough PCA radii, find histogram mode, keep points within ±15% of mode. Slightly more code but no mesh topology assumptions.

## Alignment: Kabsch SVD with N! correspondence search

`src/alignment.py:align_cylinders()` finds the optimal rigid transform (R, t) mapping technique cylinders to gold-standard cylinders. It:
- Tries every permutation of N cylinders (N! brute force)
- For each permutation, runs Kabsch SVD to find optimal rotation + translation
- Keeps the permutation with lowest RMSE

N! is feasible for dental studies (N ≤ 8 → 40,320 permutations, each requiring a 3×3 SVD; total < 1 ms). Cylinders are sorted by center X then Y before output to ensure consistent ordering across runs.

**Alignment RMSE > 1.0 mm** triggers a warning (`_RMSE_WARNING_THRESHOLD_MM`). Cases with high RMSE are commented out in `config/trial.yaml` with a note — do not silently re-enable them.

## Output: results.xlsx

Three sheets:
- **Per Implant** — one row per implant × technique × case. Contains `angular_error_deg`, `translational_offset_mm`, raw cylinder axes and centers for both technique and gold (both in the gold coordinate frame after alignment), plus fit quality metrics (`tech_fit_rmse_mm`, `tech_elongation_ratio`).
- **Inter-Implant** — pairwise center-to-center distance errors. Uses pre-alignment technique centers (rigid transforms preserve distances, so pre/post alignment gives identical values). This metric is independent of alignment and is the most reliable accuracy indicator.
- **Summary** — descriptive statistics per technique.

`reporter.py` ignores the CSV paths in the config and always writes `results.xlsx` to the project root.

## Statistical analysis (analyze.py)

Reads `results.xlsx`. Key design decisions:
- Techniques and their display colors are derived dynamically from the data — there are no hardcoded technique names anywhere in `analyze.py` or `visualize.py`.
- Box plots show mean labels (not median). The box and whiskers show the standard box plot quartiles; the labeled value is the mean.
- Pairwise Wilcoxon tests use Bonferroni correction; Friedman test for overall effect.
- All three metrics (angular, translational, inter-implant) are analyzed; individual-implant data points are overlaid on box plots.

## Config file structure

```yaml
output_csv: results_implants.csv              # ignored by reporter (kept for legacy)
output_interimplant_csv: results_interimplant.csv  # ignored by reporter

cases:
  - name: "s1"
    n_implants: 6                             # must match actual scan body count
    desktop_scanner: "trial/Desktop Scanner/s1-86846.stl"
    techniques:
      TRIOS:    "trial/Intraoral Scanner (TRIOS)/s1-86846.stl"
      Nexus:    "trial/Nexus/s1-86846 N.ply"  # PLY supported
      Shinning: "trial/Intraoral Photogrammetry (Shinning)/s1-86846 S.stl"
```

Paths are relative to the project root (`config_path.parent.parent`). Cases with missing files or high alignment RMSE should be commented out with an explanatory note — see `config/trial.yaml` for examples.

## Fit quality metrics (in results.xlsx Per Implant sheet)

| Column | Meaning | Good | Poor |
|--------|---------|------|------|
| `tech_fit_rmse_mm` | Mean distance of surface points from fitted cylinder wall | < 0.10 mm | > 0.50 mm |
| `tech_elongation_ratio` | PCA eigenvalue ratio λ₁/(λ₂+λ₃) | > 5 | < 2 |

Shinning's current (unfixed) fit RMSE is systematically ~0.158 mm vs ~0.119 mm for other techniques, and radius is ~2.396 mm vs ~2.462 mm — both diagnostics of the inner-surface contamination described above. After the convex hull fix, Shinning RMSE drops to ~0.076 mm and radius recovers to ~2.459 mm.

## Key findings to preserve when modifying the analysis

- **Angular error**: Nexus has ~7° mean error vs ~2.4° for TRIOS/Shinning (vs Desktop gold). Swapping to Nexus gold reverses this completely — Desktop/TRIOS/Shinning all measure ~7° against Nexus. This means Nexus systematically captures axis orientation differently from the other three techniques (which cluster within 2.5° of each other).
- **Translational error**: Rankings are stable regardless of gold standard choice. Nexus ≈ Desktop ≈ TRIOS < Shinning (with artifact) / Shinning ≈ TRIOS (corrected).
- **TRIOS angular error** correlates with arch span (Spearman ρ = 0.56, p = 0.004) and implant count.
- **Shinning translational error** correlation with arch span is not significant (ρ = 0.38, p = 0.071).

## Git / data management

- STL, PLY, and PDF files are tracked via Git LFS (see `.gitattributes`).
- Generated outputs (`results.xlsx`, `results_implants.csv`, `results_interimplant.csv`, `images/`, `tmp_output.txt`) are gitignored — reproduce with `run_all.py`.
- `notes/` is gitignored.
- `analyze_nexus_gold.py` is a one-off analysis script, not part of the main pipeline.
