# Guardrail Length-of-Need Calculator

A Windows desktop application for calculating guardrail length-of-need values and producing a PDF calculation package. The calculator is based on the MDOT Roadway Design Manual tables and the included GR-4 reference documents.

Current application version: **V9.0.3**

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

Open the [latest release](https://github.com/colewinstead/Guardrail-Calculator/releases/latest) and download the executable under **Assets**. The filename includes the release tag, for example `guardrail-v8.5.3.exe`. No Python installation is required for the packaged application. See [Releases](https://github.com/colewinstead/Guardrail-Calculator/releases) for available versions.

Enter the project and roadway information, select the design parameters, and choose:

- **Calculate** to show results in the application.
- **Generate PDF** to save a calculation package. The complete package includes the summary, detailed calculations, and MDOT reference appendices, and can optionally open when complete.
- **Export DXF** to create either a standalone feet-based plan or a LandXML overlay in real project coordinates. The export dialog collects bridge limits and the applicable GR-4 layout.

### Keyboard access and screen readers

Use **Tab** and **Shift+Tab** to move between enabled controls; the main form
scrolls to keep the focused control visible. Use **Space** to activate a focused
button or checkbox, and the standard arrow keys to operate selection controls.
The DXF dialog starts with the bridge-length field focused; **Escape** cancels it.

Button text has at least 4.5:1 contrast in its normal, hover, and pressed states,
and focused controls have a distinct light outline.
[View the keyboard-focus example](docs/images/keyboard-focus.png).

Screen-reader compatibility has not been verified. The tested Tk 8.6.15 runtime
does not provide the `tk accessible` naming API documented for
[Tk 9.1](https://www.tcl-lang.org/man/tcl9.1/TkCmd/accessible.html), and Windows UI
Automation exposed most controls as unnamed panes during inspection. These
keyboard and contrast improvements do not establish NVDA support; that requires
a separate runtime/accessibility review and testing with a screen reader.

### Automatic clear-zone criteria

Choose **New Construction** (Table 9-2-A) or **3R Rural Non-Freeway**
(Table 12-2-B) when selecting LA from the clear-zone table. The 3R lookup covers
recoverable fill slopes on non-curbed facilities, at supported design speeds
from 30 through 65 mph. Backslopes and nonrecoverable fill slopes are not supported.
The selected criteria, slope, and range selection are recorded in the PDF.

[MDOT's 2020 Roadway Design Manual](https://mdot.ms.gov/documents/Roadway%20Design/Standards/Manuals/2020%20Roadway%20Design%20Manual.pdf),
Section 12-2.08.01, recommends Chapter 9
clear-zone distances where feasible and Table 12-2-B where they are infeasible.
The starred ranges retain their published values; the conditional 15-ft allowance
requires project review and is not applied automatically. Direct LA entry remains
independent of the table selector.


### DXF export modes - BETA

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

The repository includes a PyInstaller specification that bundles the application and its required reference PDFs. On a new Windows computer, install **all runtime dependencies** before building (installing PyInstaller alone does not install Matplotlib):

```powershell
# Run from the repository root using the same Python interpreter for every command.
py -m pip install -r requirements.txt
py -m pip install pyinstaller
py -c "import matplotlib; print(matplotlib.__version__)"
py -m PyInstaller --clean --noconfirm guardrail.spec
```

The Matplotlib check should print the installed version before the build starts. If it raises `ModuleNotFoundError`, install the requirements in the Python environment used by `py -m PyInstaller` and rebuild; otherwise the executable may be missing PDF-generation dependencies.

The specification reads `APP_VERSION` from `guardrail_design.py` automatically.
The build produces `dist\guardrail-v8.5.3.exe` for V8.5.3; future versions use
the matching lowercase version tag in the filename. Build output is ignored by Git.

GitHub Actions runs the regression suite and builds the Windows executable on
every push and pull request. Download `guardrail-windows` from the workflow run
to try a build before releasing it. The workflow can also be run manually from
the repository's **Actions** tab.

Work on a feature branch and open a pull request into `main`. Both `Version
policy` and `Windows tests and executable` must pass before merging, and review
conversations must be resolved. These requirements also apply to administrators.

For application changes, increase `APP_VERSION` in `guardrail_design.py` and
update the current version at the top of this README in the same PR. New
versions use `VMAJOR.MINOR.PATCH`: patch for compatible fixes and small UI changes,
minor for features, and major for breaking changes. See `AGENTS.md` for the full
policy. Keep the compatibility launcher filename `guardrail_V8.5.py` unchanged.

After the PR merges, passing tests and a successful Windows build automatically
publish `guardrail-<tag>.exe` (for example, `guardrail-v8.5.3.exe`) with generated
release notes and the matching lowercase version tag. Do not push release tags manually. Published
versions are immutable; make a new patch release for corrections. The README's
latest-release download link continues to point to the latest release. No
additional GitHub secrets are required.

Documentation-only, test-only, and CI/tooling-only changes do not need a version
bump and do not publish a release. Manual workflow runs also never publish.

## Reference documents

The source folder includes the MDOT reference documents used by the calculator, along with example calculation sheets. They provide traceability for the PDF output and should remain with the application when calculation packages need appendices.

### PDF presentation

PDF exports use `<Project> - Guardrail Calculations.pdf`, or `Guardrail Calculations.pdf`
when the project is blank. Desktop and console exports always create the complete
package. Legacy report-style arguments remain supported for programmatic callers.
Equations use embedded STIX math fonts, aligned steps, and stacked fractions
through Matplotlib MathText (no external LaTeX installation); substitutions
and results retain four decimal places. The barrier length-of-need reference figure
is presented in landscape without changing the packaged source PDF.

V9.0.0 removes the summary-only, details-only, and omit-appendix choices from the
interactive export workflow. Calculation formulas and precision are unchanged.

## Important

This tool assists with engineering calculations; it does not replace professional engineering judgment, project-specific review, or verification against the current governing standards and agency requirements.
