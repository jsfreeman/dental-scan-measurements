# dental-scan-measurements

A tool for measuring and comparing the accuracy of dental implant scanning techniques.  It takes 3-D scan files from multiple techniques, fits cylinders to each implant scan body, and produces spreadsheets and charts showing how closely each technique matches the Desktop Scanner gold standard.

---

## Quick Start

```
python main.py --config config/trial.yaml      # measure accuracy → CSV files
python visualize.py --config config/trial.yaml # generate 3-D and error charts per case
python analyze.py                              # run statistics and generate analysis chart
```

Results appear in the project folder as `results_implants.csv`, `results_interimplant.csv`, and `images/`.

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
    desktop_scanner.stl
    intraoral_scanner.stl
    nexus_photogrammetry.ply
    shinning_photogrammetry.stl
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

  - name: "Patient 003"
    n_implants: 3
    desktop_scanner: "data/patient_003/desktop_scanner.stl"
    techniques:
      Intraoral_Scanner:          "data/patient_003/intraoral_scanner.stl"
      Nexus_Photogrammetry:       "data/patient_003/nexus_photogrammetry.ply"
      Shinning_Photogrammetry:    "data/patient_003/shinning_photogrammetry.stl"
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

The tool will print progress as it processes each case and technique.  When it finishes you will have two spreadsheet files:

| File | Contents |
|---|---|
| `results_implants.csv` | One row per implant per technique per case.  Contains angular error (degrees), translational offset (mm), and the raw cylinder parameters for both the technique and the gold standard. |
| `results_interimplant.csv` | One row per pair of implants per technique per case.  Contains the distance between each pair of implants in the gold standard and the technique, and the difference between them. |

These files can be opened directly in Excel or any spreadsheet program.

**Tip:** If you want separate output files for different studies, change `output_csv` and `output_interimplant_csv` in your config file.

---

## Step 5 — Generate visual charts

```
python visualize.py --config config/my_study.yaml
```

This generates one image per case inside the `images/` folder.  Each image shows:

- **Left panel:** A 3-D view of all the fitted cylinders for that case, colour-coded by technique.  This lets you verify that the tool found the right implants and that the alignment looks correct.
- **Centre panel:** A bar chart of angular error per implant (how accurately each technique captured the tilt of each implant).
- **Right panel:** A bar chart of translational offset per implant (how accurately each technique captured the position of each implant).

To open an image on Windows, run:
```
start images\case_Patient_001.png
```

---

## Step 6 — Run the statistical analysis

```
python analyze.py
```

This reads `results_implants.csv` and `results_interimplant.csv` (whichever are currently in the project folder) and:

- Prints a full statistical report to the terminal, including descriptive statistics, outlier detection, a Friedman repeated-measures test, and pairwise Wilcoxon tests with Bonferroni correction.
- Saves a composite chart to `images/analysis.png` with box plots, individual data points, a scatter plot of angular vs translational error, and per-case breakdowns.

Open the analysis chart on Windows:
```
start images\analysis.png
```

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

**The tool is slow on large PLY files**
Photogrammetry files can be very large (100,000+ triangles).  This is normal — the tool samples a manageable point cloud from the surface.  Processing typically takes 10–30 seconds per file.

---

## Trial data and initial conclusions

The `trial/` folder contains two cases used during development:

| Case | Implants | Techniques |
|---|---|---|
| s1 (86846A) | 6 | Desktop Scanner, Intraoral Scanner, Nexus PLY, Shinning STL |
| s2 (104663A) | 4 | Desktop Scanner, Intraoral Scanner, Nexus PLY, Shinning STL |

Results from these two cases (n = 10 implants per technique):

| Technique | Mean angular error | Mean translational offset | Mean inter-implant distance error |
|---|---|---|---|
| Intraoral Scanner | 2.2° | 0.053 mm | 0.041 mm |
| Shinning Photogrammetry | 2.5° | 0.076 mm | 0.063 mm |
| Nexus Photogrammetry | 7.3° | **0.032 mm** | **0.023 mm** |

**Key finding:** Nexus Photogrammetry captures implant *positions* most accurately (lowest translational and inter-implant distance errors) but captures implant *angulation* least accurately (angular error ~3x higher than the other techniques, p = 0.002).  The Intraoral Scanner provides the best overall balance.  These are preliminary results based on two cases only.

---

## Project structure

```
dental-scan-measurements/
├── config/
│   └── trial.yaml              # Example config for the trial dataset
├── src/
│   ├── loader.py               # Loads STL and PLY files
│   ├── cylinder_fit.py         # Finds and fits cylinders to each scan body
│   ├── alignment.py            # Aligns cylinder sets between techniques
│   ├── metrics.py              # Calculates error measurements
│   └── reporter.py             # Writes results to CSV
├── checks/                     # One-time environment verification scripts
├── trial/                      # Trial scan files (2 cases)
├── papers/                     # Reference literature
├── images/                     # Generated charts (created when you run the scripts)
├── main.py                     # Step 4: run measurements
├── visualize.py                # Step 5: generate per-case charts
├── analyze.py                  # Step 6: statistical analysis
└── requirements.txt            # Python package dependencies
```
