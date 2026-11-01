# Repository Guidelines

## Project Structure & Module Organization

This is a Windows desktop application using Python 3.10+ and Tkinter. Source files live at the repository root:

- `guardrail_V8.5.py`: desktop launcher and compatibility API; `guardrail_ui.py`: Tkinter.
- `guardrail_design.py`, `guardrail_models.py`, `guardrail_parsing.py`, `guardrail_validation.py`, and `guardrail_engine.py`: design data and the typed calculation pipeline.
- `guardrail_report.py`, `guardrail_pdf.py`, and `guardrail_pdf_files.py`: report formatting, layout, and file/appendix handling.
- `guardrail_alignment.py` and `guardrail_landxml.py`: geometry, station conversion, and XML import.
- `guardrail_drawing.py` and `guardrail_dxf.py`: drawing geometry and DXF serialization.
- Root `test_*.py` and `test_fixtures/`: regression tests and corrected-baseline characterization. See `ARCHITECTURE.md` for remaining modules and boundaries.

Keep `gr manual.pdf`, `GR-4.pdf`, and `GR-4a.pdf` beside the application; PDF appendices and executable packaging depend on these filenames. Root calculation sheets and `Test Exports/` contain examples. `guardrail.spec` defines the PyInstaller build; `requirements.txt` lists runtime dependencies.

## Build, Test, and Development Commands

Run these commands from the repository root in PowerShell:

```powershell
py -m pip install -r requirements.txt  # Install runtime dependencies
py guardrail_V8.5.py                  # Launch the desktop application
py -m unittest discover -v           # Run the complete regression suite
py -m pip install pyinstaller         # Install the build tool
py -m PyInstaller guardrail.spec -y   # Build dist/guardrail.exe
```

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and uppercase constants. Preserve established engineering symbols such as `LA` and `L2` where they match drawing terminology. Follow surrounding code and use type annotations for new geometry interfaces. Keep reusable geometry and export logic separate from Tkinter callbacks. No formatter or linter is currently configured; avoid unrelated formatting changes.

Keep one immutable calculation snapshot authoritative for UI, reports, and drawings. Preserve established engineering behavior and unsupported-export rejection rules; software parity does not approve unresolved MDOT assumptions.

## Testing Guidelines

Tests use Python's `unittest`; name files `test_*.py` and methods `test_*`. Add regression tests for changed geometry, station equations, units, and input rejection. Use temporary directories for generated fixtures. No numeric coverage threshold is configured. Run the existing suite before submitting code changes, and manually check affected GUI flows and PDF/DXF output for layout changes.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive action phrases, such as `Remove generated build files and correct setup docs`; no formal prefix scheme is enforced. Keep commits focused. PRs should explain the problem, resulting behavior, and validation performed. Link related issues when applicable and include screenshots or export examples for visible changes. Explain the reference basis for changes to engineering calculations.

## Build Assets & Releases

`build/`, `dist/`, and Python bytecode are ignored. Publish Windows executables through GitHub Releases and keep the README download link current. Commit example exports only when they provide useful, reviewed documentation.
