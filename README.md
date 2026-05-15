# dental-scan-measurements

A tool for measuring and comparing the accuracy of dental implant scanning techniques.  It takes 3-D scan files from multiple techniques, fits cylinders to each implant scan body, and produces spreadsheets and charts showing how closely each technique matches the Desktop Scanner gold standard.

---

## Quick Start

```
python run_all.py --config config/trial.yaml
```

This runs the full pipeline in one command and produces `results.xlsx` and charts in `images/`.

Or run the steps individually:

```
python main.py --config config/trial.yaml       # measure accuracy → results.xlsx
python visualize.py --config config/trial.yaml  # per-case 3-D + bar charts → images/case_charts.pdf
python analyze.py                               # statistics + box plots → images/analysis.png
```

---

## Step 1 — Install Python and dependencies

You need **Python 3.10 or later**.  Download it from https://www.python.org if you don't have it.

Open a terminal (Command Prompt or PowerShell on Windows, Terminal on Mac), navigate to this folder, and run:

```
pip install -r requirements.txt
```

This installs everything the tool needs.  You only need to do this once.

---

## Step 2 — Organise your scan files

Create a folder for your study data.  The exact folder layout is up to you, but we recommend grouping files by case (patient):

```
data/
  patient_001/
    desktop_scanner.stl          ← gold standard for this patient
    intraoral_scanner.stl
    nexus_photogrammetry.ply
    shinning_photogrammetry.stl
  patient_002/
    ...
```

**Supported file formats:** STL (the most common format from dental CAD software) and PLY.  Both binary and ASCII STL files work.

**One file per technique per patient.**  Each file should contain all the implant scan bodies for that patient scanned with that technique.

---

## Step 3 — Create or update the config file

The config file tells the tool where your files are and how many implants each patient has.  Open `config/trial.yaml` in any text editor to see an example, or create a new file such as `config/my_study.yaml`.

### Config file format

```yaml
# Where to write the output spreadsheets (relative to this project folder)
output_csv: results_implants.csv
output_interimplant_csv: results_interimplant.csv

cases:
  - name: "Patient 001"           # Label used in output files — can be any text
    n_implants: 4                 # How many implants this patient has
    desktop_scanner: "data/patient_001/desktop_scanner.stl"   # gold standard file
    techniques:
      Intraoral_Scanner:          "data/patient_001/intraoral_scanner.stl"
      Nexus_Photogrammetry:       "data/patient_001/nexus_photogrammetry.ply"
      Shinning_Photogrammetry:    "data/patient_001/shinning_photogrammetry.stl"

  - name: "Patient 002"
    n_implants: 6
    desktop_scanner: "data/patient_002/desktop_scanner.stl"
    techniques:
      Intraoral_Scanner:          "data/patient_002/intraoral_scanner.stl"
      Nexus_Photogrammetry:       "data/patient_002/nexus_photogrammetry.ply"
      Shinning_Photogrammetry:    "data/patient_002/shinning_photogrammetry.stl"
```

### Important notes

- **File paths** are relative to the project root folder (the folder containing `main.py`).  Use forward slashes `/` even on Windows.
- **`n_implants`** must match the actual number of implant scan bodies in the files.  If this is wrong the tool will either find too few cylinders or try to split one scan body into two.
- **Technique names** (e.g. `Intraoral_Scanner`) can be anything you like — they appear as column labels in the output.  Use underscores instead of spaces.
- **Add as many cases as you need** — just copy and paste a case block and update the name, n_implants, and file paths.

---

## Step 4 — Run the measurement pipeline

```
python main.py --config config/my_study.yaml
```

The tool will print progress as it processes each case and technique.  When it finishes you will have a spreadsheet file `results.xlsx` with three sheets:

| Sheet | Contents |
|---|---|
| **Per Implant** | One row per implant per technique per case.  Contains angular error (degrees), translational offset (mm), and the raw cylinder parameters for both the technique and the gold standard. |
| **Inter-Implant** | One row per pair of implants per technique per case.  Contains the distance between each pair of implants in the gold standard and the technique, and the difference between them. |
| **Summary** | Descriptive statistics per technique. |

This file can be opened directly in Excel or any spreadsheet program.

### Options

| Flag | Values | Default | Description |
|---|---|---|---|
| `--config` | path | *(required)* | Path to the YAML configuration file. |
| `--segmentation` | `components`, `kmeans` | `components` | How scan bodies are separated within each mesh file. `components` splits on mesh connectivity and falls back to K-means if needed. `kmeans` always uses spatial clustering — useful when meshes are fused into a single body. |

Run `python main.py --help` for a full usage summary.

---

## Step 5 — Generate visual charts

```
python visualize.py --config config/my_study.yaml
```

This generates a multi-page PDF (`images/case_charts.pdf`) with one page per case.  Each page shows:

- **Left panel:** A 3-D view of all the fitted cylinders for that case, colour-coded by technique.  This lets you verify that the tool found the right implants and that the alignment looks correct.
- **Centre panel:** A bar chart of angular error per implant (how accurately each technique captured the tilt of each implant).
- **Right panel:** A bar chart of translational offset per implant (how accurately each technique captured the position of each implant).

Accepts the same `--segmentation` flag as `main.py`.  Run `python visualize.py --help` for all options.

---

## Step 6 — Run the statistical analysis

```
python analyze.py
```

This reads `results.xlsx` (produced by Step 4) and:

- Prints a full statistical report to the terminal, including descriptive statistics, outlier detection, a Friedman repeated-measures test, and pairwise Wilcoxon tests with Bonferroni correction.
- Saves a composite chart to `images/analysis.png` with box plots, individual data points, a scatter plot of angular vs translational error, and per-case breakdowns.

Run `python analyze.py --help` for a usage summary.

---

## Measuring accuracy — what the numbers mean

| Metric | Unit | What it tells you |
|---|---|---|
| **Angular error** | degrees | How accurately the technique captured the tilt of each implant relative to the Desktop Scanner.  Lower is better.  Clinically relevant for prosthetic fit. |
| **Translational offset** | mm | How far off the implant centre position is after aligning the two scans.  Lower is better.  Captures relative positioning errors between implants. |
| **Inter-implant distance error** | mm | How accurately the distance between each pair of implants was reproduced.  This does not depend on the alignment step and is a direct measure of how well the technique captured the spatial layout of the implants. |

---

## Troubleshooting

**"Mesh file not found"**
The file path in your config is wrong or the file doesn't exist.  Check that the path is relative to the project root and uses forward slashes.

**"Could only extract N clusters, expected M"**
The `n_implants` value in your config doesn't match the number of scan bodies in the file.  Open the file in a mesh viewer (e.g. MeshLab, which is free) and count the scan bodies manually, then update the config.

**"Alignment RMSE exceeds 1 mm" warning**
The two scans may not represent the same patient, or `n_implants` may be wrong.  Check that the correct files are listed in the config.

**"Alignment ambiguity" warning**
More than one way of matching the technique implants to the gold-standard implants gives a good alignment score.  This can happen when implants are placed in a symmetric pattern.  The per-implant angular and translational errors for this case may be unreliable; the inter-implant distance errors (which do not depend on alignment) are still valid.

**The tool is slow on large PLY files**
Photogrammetry files can be very large (100,000+ triangles).  This is normal — the tool samples a manageable point cloud from the surface.  Processing typically takes 10–30 seconds per file.

**Cylinder extraction looks wrong for fused meshes**
Some scanners export all scan bodies as a single connected mesh rather than separate components.  Try `--segmentation kmeans` to force spatial clustering instead of component splitting.

---

## Project structure

```
dental-scan-measurements/
├── config/
│   └── trial.yaml                  # Config for the 27-case trial dataset
├── src/
│   ├── loader.py                   # Loads STL and PLY files
│   ├── cylinder_fit.py             # Finds and fits cylinders to each scan body
│   ├── alignment.py                # Aligns cylinder sets between techniques
│   ├── metrics.py                  # Calculates error measurements
│   └── reporter.py                 # Writes results to results.xlsx
├── trial/                          # Trial scan files (27 cases, 3 techniques)
├── images/                         # Generated charts (created when you run the scripts)
├── run_all.py                      # Run the full pipeline in one command
├── main.py                         # Step 4: run measurements → results.xlsx
├── visualize.py                    # Step 5: generate per-case charts
├── analyze.py                      # Step 6: statistical analysis
├── analyze_nexus_gold.py           # Sensitivity analysis: Nexus as gold standard
└── requirements.txt                # Python package dependencies
```
