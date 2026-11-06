---
target: critique the ui
total_score: 22
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 3
target_identity: "file:C:\\Coding Projects\\Guardrail-Calculator\\guardrail_ui.py"
target_fingerprint: "sha256:c6d59b000b66040ecc35af492cfd5200ccfd58dced762bfcfb2eaa8649138312"
target_path: "C:\\Coding Projects\\Guardrail-Calculator\\guardrail_ui.py"
timestamp: 2026-11-06T05-04-51Z
slug: guardrail-ui-py
---
Method: design review only (detector not applicable, native platform)

**Overall impression and design specificity**

This is a credible engineering utility with a workable foundation, but its hierarchy favors configuring the form over understanding the answer. The biggest opportunity is a persistent results-and-actions area within the existing Tkinter interface.

The terminology, near/opposing comparison, units, and reference workflow are specific to this product. The dark blue panels and three equally prominent blue buttons are generic; product character would come more effectively from clear engineering relationships and result hierarchy than additional decoration. Deterministic scan: not applicable to native Tkinter.

**Design health: 22/40 — Acceptable; substantial usability improvements available.**

These scores are a qualitative review of the observed desktop workflow, not a usability study or engineering certification.

| Heuristic | Score /4 | Evidence |
|---|---:|---|
| System status | 2 | Automatic updates exist; status is below the initial viewport. |
| Match with real-world work | 3 | Engineering terminology and near/opposing comparison fit the audience. |
| User control | 2 | DXF Cancel works; Escape did not dismiss the dialog. |
| Consistency | 3 | Sections and controls are consistent; manual/automatic calculation intent is unclear. |
| Error prevention | 3 | Readonly selections, conditional controls, and export validation protect inputs. |
| Recognition over recall | 2 | Active LA competes with a different disabled value; little contextual guidance. |
| Efficiency | 2 | Automatic calculation and linked distance help; no explicit action shortcuts in source. |
| Minimalist design | 2 | Inactive fields remain prominent; results have weak emphasis. |
| Error recovery | 2 | Inputs are retained, but automatic errors clear results and explain the problem at the bottom. |
| Help and documentation | 1 | README and references exist; no visible in-app help entry or contextual explanations. |
| **Total** | **22/40** | **Acceptable** |

**What works**

- Automatic recalculation reduces repetitive work, and invalid automatic calculations clear results rather than presenting stale numbers as current.
- Side-by-side near/opposing results make comparison straightforward.
- Explicit units, grouped engineering inputs, and separate standalone/LandXML choices establish a useful foundation. Cancellation from the DXF dialog works without writing a file.

**Priority issues**

1. **P1 — The displayed LA values disagree.** In the observed clear-zone workflow, the disabled Hazard Offset, LA field shows 30 while the green banner says LA USED = 28.0000 FT. The code uses the selected clear-zone value; this is a presentation ambiguity, not evidence of incorrect calculation. A designer can still read the wrong number while checking work. **Fix:** display the active computed LA in a readonly field, or hide the inactive direct-entry field and label the computed value clearly. Preserve the remembered direct-entry value separately. Source: guardrail_ui.py:135, 349, 376, 386. Suggested command: `$impeccable clarify`.

2. **P1 — Results and actions disappear below the initial viewport.** At the configured 1040-by-850 content size, the top view shows project metadata, the full input panels, and PDF configuration before the actual results; Calculate and both export actions require scrolling. The user must move away from inputs to check their effect. **Fix:** move results ahead of PDF configuration and keep a compact result summary, actions, and validity/status visible while inputs scroll. Preserve all existing workflows. Source: guardrail_ui.py:100, 288, 319, 652. Suggested command: `$impeccable layout`.

3. **P1 — Accessibility needs a native pass.** Windows UI Automation exposed most form controls and the DXF dialog contents as unnamed panes, rather than labeled inputs and buttons. That is an observed accessibility warning, not a completed NVDA test. White primary-button text on #3B82F6 also measures 3.68:1, below the usual 4.5:1 target for normal-sized text. **Fix:** verify the complete workflow with keyboard and NVDA, address native control names/roles, darken the primary-button background, and verify focus remains visible. Source: guardrail_ui.py:62-97, 160. Suggested command: `$impeccable audit`.

4. **P2 — Inactive configuration consumes too much attention.** A two-lane calculation still displays the entire disabled divided-highway helper; standard transition and terminal selections retain disabled custom-entry rows. The standalone DXF dialog similarly presents inactive LandXML fields. **Fix:** show conditional groups only when relevant, while keeping active default values visible as concise summaries and preserving entered values when switching modes. Source: guardrail_ui.py:206, 266, 342, 515. Suggested command: `$impeccable distill`.

5. **P2 — The most useful results and actions have no clear visual priority.** Six result rows have equal weight, four-decimal values dominate the table, and Calculate, Generate PDF, and Beta DXF all use the same primary style even though results update automatically. **Fix:** emphasize Rounded Rail Length and Final Overall Length for each side; retain full precision and supporting rows. Give recalculation and exports a clear hierarchy, and explain automatic updates beside the results. Source: guardrail_ui.py:404, 425, 657. Suggested command: `$impeccable polish`.

**Cognitive load and emotional journey**

Related inputs are grouped well, but hierarchy, progressive disclosure, chunking, and working-memory demands need work: ten design-parameter rows appear together, inactive controls stay visible, and results require scrolling away from inputs. Speed and flare dropdowns have more than four choices, but these are legitimate engineering selections; organizing the workflow matters more than arbitrarily shortening those lists.

The opening looks orderly and technical. Confidence drops when the LA displays disagree and results sit out of view. Automatic updates and successful output feedback provide reassurance, but too much of that reassurance lives at the bottom.

**Persona red flags**

- **Alex, experienced designer:** repeated input/result scrolling; three equally emphasized actions; no explicit Calculate/PDF/DXF shortcuts found in source.
- **Jordan, new team member:** inactive LA conflicts with active LA; ETW, gating, and automatic/manual calculation behavior have little contextual explanation.
- **Sam, keyboard or assistive-technology user:** unnamed UI Automation panes and insufficient primary-button text contrast; Escape did not close the DXF dialog.

**Minor observations**

- Error feedback should identify the affected field nearby; clearing the result table plus a bottom status sentence makes diagnosis harder.
- Labels use the darker global background inside lighter panels, producing small rectangular patches that add visual noise.
- Add an Escape binding and explicit initial focus to the DXF dialog. Cancel remains available.
- Keep the Beta designation associated with DXF when revising action hierarchy.

**Questions to consider**

Would a designer checking a changed input see the active LA and final lengths without scrolling? Can inactive controls be removed from view while preserving their remembered values?

**Limits**

No application code was changed. This review did not validate engineering assumptions, regenerate PDF/DXF outputs, run the regression suite, or complete NVDA/high-DPI testing.
