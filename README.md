# Guardrail Length-of-Need Calculator

A Windows desktop application for calculating guardrail length-of-need values and producing a PDF calculation package. The calculator is based on the MDOT Roadway Design Manual tables and the included GR-4 reference documents.

Current application version: **V8.5**

## What it does

- Calculates near-side and opposing-side guardrail lengths.
- Supports two-lane/two-way and divided-highway facilities.
- Determines runout length from MDOT Table 9-6-A using design speed and ADT.
- Uses either a direct hazard offset or a clear-zone selection based on MDOT Table 9-2-A.
- Handles transition length, terminal section, flare rate, and gating length.
- Generates a calculation-sheet PDF, with an option to append the included MDOT reference documents.

## Use the Windows application

Download and run [guardrail.exe](guardrail.exe). No Python installation is required for the packaged application.

Enter the project and roadway information, select the design parameters, and choose:

- **Calculate** to show results in the application.
- **Generate PDF** to save a calculation package. The package can include the MDOT reference appendix and can optionally open when complete.

## Run from source

### Requirements

- Python 3.10 or later
- Tkinter (normally included with standard Windows Python installations)
- `pypdf`
- `reportlab`

Install the Python dependencies:

```powershell
py -m pip install pypdf reportlab
```

Run the application from the project folder:

```powershell
py guardrail_V8.5.py
```

Keep these reference PDFs in the same folder as the script so they can be embedded in generated calculation packages:

- `gr manual.pdf`
- `GR-4.pdf`
- `GR-4a.pdf`

## Build the executable

The repository includes a PyInstaller specification that bundles the application and its required reference PDFs.

```powershell
py -m pip install pyinstaller
py -m PyInstaller guardrail.spec -y
```

The build produces `dist\guardrail.exe`. Copy it to the project root if you want to replace the executable published in this repository.

## Reference documents

The source folder includes the MDOT reference documents used by the calculator, along with example calculation sheets. They provide traceability for the PDF output and should remain with the application when calculation packages need appendices.

## Important

This tool assists with engineering calculations; it does not replace professional engineering judgment, project-specific review, or verification against the current governing standards and agency requirements.
