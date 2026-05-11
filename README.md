# dental-scan-measurements

A Python pipeline for measuring the accuracy of intra-oral scanning techniques by comparing 3-D mesh files against a Desktop Scanner gold standard.

---

## Background

Dental implant treatment relies on accurate impressions of implant positions.  Several scanning technologies exist — traditional desktop scanners, intra-oral scanners (IOS), and photogrammetry-based systems — each with different accuracy profiles.  This tool automates the geometric comparison between these techniques to help researchers quantify and publish those differences.

Each scan contains one or more **implant scan bodies**: small cylindrical titanium markers that screw onto each implant and protrude above the gum line.  The pipeline locates each scan body, fits a cylinder to it, and compares the cylinder's position and orientation to the gold standard.

---

## How It Works

```
For each case (patient):
  1. Load the Desktop Scanner STL  →  fit N cylinders (gold standard)
  2. For each comparison technique:
     a. Load the STL or PLY file   →  fit N cylinders
     b. Align the two cylinder sets with a Kabsch SVD rigid transform
     c. Measure per-implant error:
           - Angular error (°)        — axis tilt vs. gold standard
           - Translational offset (mm) — centre displacement after alignment
     d. Measure inter-implant distance error (mm) — alignment-independent
  3. Write results to CSV
```

### Cylinder extraction

- **Primary strategy**: split the mesh on connected-component boundaries.  Dental CAD exports (exocad) produce one mesh body per scan body, so each implant is already a separate island.
- **Fallback**: if the mesh is a single connected surface (common in photogrammetry), K-means spatial clustering (K = N) partitions the point cloud into one cluster per scan body.
- **Fitting**: PCA finds the cylinder axis (direction of maximum variance); an algebraic least-squares circle fit on the perpendicular cross-section recovers the centre and radius.

### Alignment (Kabsch SVD)

The two scans live in different coordinate frames.  We find the optimal rigid transform (rotation + translation) that minimises the RMSE of the N cylinder centres.  Because we also don't know in advance which cylinder in one scan corresponds to which in the other, we try all N! correspondences and keep the best.  For N ≤ 6 (720 permutations maximum) this is negligibly fast.

### Error metrics

| Metric | What it measures |
|---|---|
| **Angular error (°)** | Tilt of the implant axis vs. gold standard.  Clinically relevant for prosthetic fit. |
| **Translational offset (mm)** | Residual centre displacement after alignment — captures relative position error between implants. |
| **Inter-implant distance error (mm)** | Difference in centre-to-centre distance vs. gold standard.  Fully alignment-independent. |

---

## Installation

Requires **Python 3.10+**.

```bash
pip install -r requirements.txt
```

Dependencies: `trimesh`, `numpy`, `scipy`, `pandas`, `pyyaml`, `networkx`.

---

## Running

```bash
python main.py --config config/trial.yaml
```

This produces two CSV files in the project root:

| File | Contents |
|---|---|
| `results_implants.csv` | One row per implant per technique — angular error, translational offset, raw cylinder parameters |
| `results_interimplant.csv` | One row per implant pair per technique — inter-implant distance and error |

---

## Configuration

Edit or create a YAML config file modelled on `config/trial.yaml`:

```yaml
output_csv: results_implants.csv
output_interimplant_csv: results_interimplant.csv

cases:
  - name: "PatientA"
    n_implants: 4                          # number of implant scan bodies in each file
    desktop_scanner: "data/A/desktop.stl"  # gold standard (path relative to project root)
    techniques:
      Intraoral_Scanner:      "data/A/ios.stl"
      Nexus_Photogrammetry:   "data/A/nexus.ply"
      Shinning_Photogrammetry: "data/A/shinning.stl"
```

Both STL (binary or ASCII) and PLY files are supported.

---

## Trial Data

The `trial/` directory contains two clinical cases used for initial validation:

| Case | Implants | Files |
|---|---|---|
| s1 (86846A) | 6 | Desktop Scanner, Intraoral Scanner, Nexus PLY, Shinning STL |
| s2 (104663A) | 4 | Desktop Scanner, Intraoral Scanner, Nexus PLY, Shinning STL |

---

## Initial Conclusions

Results from the two trial cases are summarised below.  All values are mean ± range across implants and cases.

### Angular error (implant tilt, degrees)

| Technique | Mean | Range |
|---|---|---|
| **Intraoral Scanner** | **1.1°** | 0.5° – 2.5° |
| Shinning Photogrammetry | 2.6° | 1.6° – 3.3° |
| Nexus Photogrammetry | **7.5°** | 3.3° – 9.6° |

### Translational offset (centre displacement after alignment, mm)

| Technique | Mean | Range |
|---|---|---|
| **Nexus Photogrammetry** | **0.033 mm** | 0.020 – 0.059 mm |
| Intraoral Scanner | 0.042 mm | 0.028 – 0.086 mm |
| Shinning Photogrammetry | 0.077 mm | 0.046 – 0.109 mm |

### Inter-implant distance error (mm)

| Technique | Mean | Range |
|---|---|---|
| **Nexus Photogrammetry** | **0.024 mm** | 0.001 – 0.066 mm |
| Intraoral Scanner | 0.043 mm | 0.012 – 0.094 mm |
| Shinning Photogrammetry | 0.064 mm | 0.007 – 0.153 mm |

### Interpretation

- The **Intraoral Scanner** achieves the best angular accuracy (lowest tilt error), making it the strongest performer for capturing implant angulation.
- **Nexus Photogrammetry** shows a striking dissociation: it has the highest angular error (~7.5°) but the *best* translational accuracy — it captures implant positions and inter-implant spacing with exceptional precision while introducing significant axis tilt error.  This pattern is consistent with the known behaviour of photogrammetry systems, which excel at capturing 3-D point positions but are sensitive to the orientation of the scan body markers.
- **Shinning Photogrammetry** sits between the other two on both metrics.
- All three techniques achieve translational accuracy well under 0.15 mm, which is within clinically acceptable tolerances for most implant-supported restorations.

> **Note:** These conclusions are based on two cases only.  A larger study with more cases and patients is needed before clinical recommendations can be drawn.

---

## Project Structure

```
dental-scan-measurements/
├── config/
│   └── trial.yaml          # Input configuration for the trial dataset
├── src/
│   ├── loader.py           # Load STL / PLY → trimesh.Trimesh
│   ├── cylinder_fit.py     # Cylinder extraction (connected components + K-means + PCA)
│   ├── alignment.py        # Kabsch SVD rigid-body alignment
│   ├── metrics.py          # Angular error, translational offset, inter-implant distances
│   └── reporter.py         # Write results to CSV
├── checks/                 # Environment sanity-check scripts
├── trial/                  # Trial STL and PLY mesh files
├── papers/                 # Reference literature
├── main.py                 # CLI entry point
└── requirements.txt
```
