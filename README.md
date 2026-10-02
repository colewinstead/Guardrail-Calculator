# Guardrail Length-of-Need Calculator

A Windows desktop application for calculating guardrail length-of-need values and producing a PDF calculation package. The calculator is based on the MDOT Roadway Design Manual tables and the included GR-4 reference documents.

Current application version: **V8.5**

The source is organized around immutable calculation snapshots, a pure engine,
and separate report/drawing output modules. See [Python architecture](ARCHITECTURE.md)
for module responsibilities, characterization coverage, and unresolved engineering questions.

## What it does

- Calculates near-side and opposing-side guardrail lengths.
- Supports two-lane/two-way and divided-highway facilities.
- Determines runout length from MDOT Table 9-6-A using design speed and ADT.
- Uses either a direct hazard offset or a clear-zone selection based on MDOT Table 9-2-A.
- Handles transition length, terminal section, flare rate, and gating length.
- Generates a calculation-sheet PDF, with an option to append the included MDOT reference documents.
- Exports a layered, to-scale DXF plan showing the calculated guardrail lengths and GR-4/GR-4a shoulder geometry at both bridge ends. The existing serializer writes AutoCAD R2000 format.

## Use the Windows application

Download and run [guardrail.exe](https://github.com/colewinstead/Guardrail-Calculator/releases/latest/download/guardrail.exe). No Python installation is required for the packaged application. See [Releases](https://github.com/colewinstead/Guardrail-Calculator/releases) for available versions.

Enter the project and roadway information, select the design parameters, and choose:

- **Calculate** to show results in the application.
- **Generate PDF** to save a calculation package. The package can include the MDOT reference appendix and can optionally open when complete.
- **Export DXF** to create either a standalone feet-based plan or a LandXML overlay in real project coordinates. The export dialog collects bridge limits and the applicable GR-4 layout.

### DXF export modes

- **Standalone** uses one DXF model-space unit per foot and asks for the bridge length.
- **LandXML overlay** lists every usable alignment in the selected file and asks for bridge start and end stations.
- LandXML overlays accept foot-based line and circular-arc geometry, including LandXML station equations and ORD region suffixes such as `R2`. Metric units, spirals, invalid station ranges, and alignments without adequate approach length are rejected before a DXF is written.
- The DXF contains separate layers for the roadway, alignment, bridge, lane lines, shoulder flare, guardrail, terminal, gating section, dimensions, leaders, labels, and traffic arrows.
- The terminal end flares 2'-0" over its entered length; the 12.5-foot gating section then flares an additional 2'-8" to reach the GR-4A 4'-8" total offset.
- The clear-zone line is placed at the edge-of-traveled-lane offset plus LA on the approach beyond the gating endpoint, then tapers back toward the bridge into the shoulder line over 75 feet.
- DXF annotations use compact engineering dimensions; long descriptive feature callouts are intentionally omitted to keep the plan legible.
- The 75-foot clear-zone taper and 150-foot shoulder transition are dimensioned longitudinally, while LA is labeled horizontally beside the full-width clear-zone line.
- The 150-foot shoulder flare is drawn as a continuous line and ties directly into the ETL. The normal shoulder at ETL + L2 intersects that taper before its endpoint and continues on the separate dashed `GR_NORMAL_SHOULDER` layer without a called-out tie length.
- All DXF labels and dimensions use the MDOT `Engineering Regular` text style backed by `EngineeringRegular.ttf`, including TrueType family metadata for correct OpenRoads/MicroStation font resolution.

### Source application export validation

- Curved longitudinal features follow alignment offsets with a 0.01-foot sampling tolerance and include geometry breakpoints. Longitudinal dimension labels retain alignment station distances, rather than measuring drawn chords or offset paths.
- DXF export requires a positive terminal length and enough installation length for the complete 75-foot clear-zone taper before the bridge. Unsupported short or zero-terminal installations are rejected; calculations and PDFs still allow a zero terminal.
- For divided highways, **Use Calculated Distance** links the opposing distance to lane counts, lane width, and median width. Subsequent dimension edits update that distance automatically. Uncheck the link to enter a custom calculation/PDF distance; DXF export requires it to match the drawing dimensions.
- LandXML imports report rejected alignments individually and retain completely valid line/arc alignments. Unsupported geometry is never silently omitted. Selecting another file clears the prior geometry, including when loading fails.
- The existing DXF assumption `LA >= L2` remains unchanged and requires engineering verification. It is not imposed on the calculation engine or PDF output.

## Run from source

### Requirements

- Python 3.10 or later
- Tkinter (normally included with standard Windows Python installations)
- `pypdf`
- `reportlab`

Install the Python dependencies:

```powershell
py -m pip install -r requirements.txt
```

Run the application from the project folder:

```powershell
py guardrail_V8.5.py
```

Unexpected GUI errors retain tracebacks in `%LOCALAPPDATA%\GuardrailCalculator\guardrail.log`
when launched through the desktop entry point. If that directory is unavailable,
the application falls back to console logging.

Run the complete regression suite with:

```powershell
py -m unittest discover -v
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

The build produces `dist\guardrail.exe`. Build output is ignored by Git; upload the executable to a GitHub release to distribute a new version.

## Reference documents

The source folder includes the MDOT reference documents used by the calculator, along with example calculation sheets. They provide traceability for the PDF output and should remain with the application when calculation packages need appendices.

## Important

This tool assists with engineering calculations; it does not replace professional engineering judgment, project-specific review, or verification against the current governing standards and agency requirements.
