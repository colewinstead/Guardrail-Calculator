# Repository Guidelines

## Project Structure & Module Organization

This is a Windows desktop application using Python 3.10+ and Tkinter. Source files live at the repository root:

- `guardrail_V8.5.py`: GUI, length-of-need calculations, and PDF generation.
- `guardrail_dxf.py`: drawing models and R12 DXF export.
- `guardrail_landxml.py`: foot-based alignment parsing, geometry, and station conversion.
- `test_guardrail_dxf.py`: automated DXF and LandXML regression tests.

Keep `gr manual.pdf`, `GR-4.pdf`, and `GR-4a.pdf` beside the application; PDF appendices and executable packaging depend on these filenames. Root calculation sheets and `Test Exports/` contain examples. `guardrail.spec` defines the PyInstaller build; `requirements.txt` lists runtime dependencies.

## Build, Test, and Development Commands

Run these commands from the repository root in PowerShell:

```powershell
py -m pip install -r requirements.txt  # Install runtime dependencies
py guardrail_V8.5.py                  # Launch the desktop application
py -m unittest -v test_guardrail_dxf   # Run export regression tests
py -m pip install pyinstaller         # Install the build tool
py -m PyInstaller guardrail.spec -y   # Build dist/guardrail.exe
```

## Coding Style & Naming Conventions

Use four-space indentation, `snake_case` functions and variables, `PascalCase` classes, and uppercase constants. Preserve established engineering symbols such as `LA` and `L2` where they match drawing terminology. Follow surrounding code and use type annotations for new geometry interfaces. Keep reusable geometry and export logic separate from Tkinter callbacks. No formatter or linter is currently configured; avoid unrelated formatting changes.

## Testing Guidelines

Tests use Python's `unittest`; name files `test_*.py` and methods `test_*`. Add regression tests for changed geometry, station equations, units, and input rejection. Use temporary directories for generated fixtures. No numeric coverage threshold is configured. Run the existing suite before submitting code changes, and manually check affected GUI flows and PDF/DXF output for layout changes.

## Commit & Pull Request Guidelines

Recent commits use short, descriptive action phrases, such as `Remove generated build files and correct setup docs`; no formal prefix scheme is enforced. Keep commits focused. PRs should explain the problem, resulting behavior, and validation performed. Link related issues when applicable and include screenshots or export examples for visible changes. Explain the reference basis for changes to engineering calculations.

## Build Assets & Releases

`build/`, `dist/`, and Python bytecode are ignored. Publish Windows executables through GitHub Releases and keep the README download link current. Commit example exports only when they provide useful, reviewed documentation.
