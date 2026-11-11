# Guardrail Length-of-Need Calculator

<!-- impeccable:product-schema 1 -->

## Platform

Windows desktop, using Python 3.10+ and Tkinter/ttk. The packaged application
runs without a separate Python installation; the source entry point is
`guardrail_V8.5.py`.

Impeccable's current platform vocabulary (web, ios, android, adaptive) does not
represent this desktop application. Do not infer a web or mobile migration from
this record. No target platform for a future conversion has been confirmed.

## Users

Roadway and bridge designers preparing MDOT guardrail calculations, PDF
calculation packages, and CAD plans on Windows. This audience and preservation
of the current calculation, PDF, and CAD workflows were confirmed by the owner.

## Product Purpose

Calculate near-side and opposing-side guardrail length of need from project,
roadway, and barrier inputs, using the established MDOT tables and included
GR-4/GR-4a references. Let designers inspect results and produce calculation
packages and supported drawing exports from the same accepted calculation.

Success means consistent results across the screen, PDF, and drawing outputs,
with invalid inputs and unsupported exports explained before a file is written.
The tool supports professional engineering judgment and project-specific review;
it does not establish approval of unresolved engineering assumptions.

## Operating Context

- Enter project information, roadway geometry, and design parameters; select
  either a direct hazard offset or the clear-zone helper; calculate and review
  near-side and opposing-side results.
- Generate a calculation-sheet PDF, optionally including the bundled MDOT
  reference appendix and opening the completed package.
- Export a DXF plan either as a standalone drawing in feet or as a LandXML
  alignment overlay in project coordinates. The export dialog collects bridge
  limits and the applicable GR-4 divided layout. Export DXF is labeled Beta.
- For divided highways, the opposing distance can stay linked to lane and median
  dimensions or be entered manually for calculations and PDFs.

## Capabilities and Constraints

- Support two-lane/two-way and divided-highway facilities, MDOT Table 9-6-A
  runout lengths, Table 9-2-A and Table 12-2-B recoverable fill-slope clear-zone
  selection, transitions, terminals, flare rates, and gating lengths.
- Preserve one immutable calculation snapshot as the authority for the UI,
  reports, and drawings. Keep calculation and export logic separate from Tkinter.
- Preserve engineering terminology, including LA and L2, units, station notation,
  and the existing distinction between calculation validity and export support.
- LandXML overlays support foot-based lines and circular arcs, station equations,
  and ORD region suffixes. Reject metric units, spirals, invalid station ranges,
  and insufficient approach geometry rather than silently dropping geometry.
- DXF has additional requirements, including a positive terminal length, room
  for the complete clear-zone taper, matching roadway dimensions, and the existing
  DXF-only `LA >= L2` assumption. Do not extend those rules to calculations or PDFs.
- Keep `gr manual.pdf`, `GR-4.pdf`, and `GR-4a.pdf` available under their established
  filenames for appendices and executable packaging.
- Preserve established engineering behavior. Resolve changes against governing
  references; regression parity alone does not validate an engineering assumption.
  See `ARCHITECTURE.md` for the unresolved engineering questions.

## Evidence on Hand

- `README.md`: supported user workflows, export limitations, and launch commands.
- `ARCHITECTURE.md`: calculation/output contracts and unresolved engineering basis.
- `gr manual.pdf`, `GR-4.pdf`, `GR-4a.pdf`: bundled reference documents.
- `sr8_guardrail_calc_sheet.pdf` and `sr8_guardrail_calc_sheet_V8.5.pdf`: example
  calculation packages; examples are not independent engineering certification.
- `guardrail_ui.py`: current desktop interface and user-facing terminology.
- `test_*.py` and `test_fixtures/`: software regression and characterization evidence.

## Product Principles

1. Preserve the current calculation, PDF, and CAD workflows.
2. Keep accepted engineering values consistent across every output.
3. Explain invalid inputs and unsupported exports without hiding rejected data.
4. Keep assumptions and reference limitations visible; require engineering review
   before changing their meaning.

## Open Decisions

No product-specific accessibility standard or additional accommodation was
specified during initialization. Future work must establish any such requirement
without treating its absence here as evidence of accessibility compliance.
