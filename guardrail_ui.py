"""Tkinter form collection, typed snapshot orchestration, and presentation."""

import logging
import os
from xml.etree.ElementTree import ParseError
from datetime import datetime
import guardrail_dxf
import guardrail_landxml
import guardrail_validation as validation
from guardrail_design import (
    APP_VERSION, DEFAULT_L1_FT, DEFAULT_TERMINAL_SECTION_FT, Facility, HazardOffsetSource,
    SideSlope, ClearZoneSelection, ReportStyle, DividedLayout, PlacementMode,
    SUPPORTED_SPEEDS, SUPPORTED_FLARE_RATES,
)
from guardrail_models import (
    ProjectMetadata, HazardBarrierInputs, CalculationInputs, CalculationSnapshot,
    ReportModel, AlignmentSelection, DrawingExportConfiguration,
)
from guardrail_engine import create_snapshot, resolve_clear_zone
from guardrail_parsing import parse_number as _first_number
from guardrail_presentation import _safe_filename
from guardrail_report import report_payload
from guardrail_pdf_files import write_report, appendix_manifest
from guardrail_drawing import drawing_inputs, standalone_placement

LOGGER = logging.getLogger(__name__)

def ui_main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    FACILITIES = {
        "Two-Lane, Two-Way Roadway": Facility.TWO_LANE_TWO_WAY,
        "Divided Highway": Facility.DIVIDED_HIGHWAY,
    }
    LA_MODES = {
        "Enter Hazard Offset Directly": HazardOffsetSource.DIRECT,
        "Select from Clear-Zone Table": HazardOffsetSource.CLEAR_ZONE,
    }
    SLOPES = {
        "6:1 or Flatter": SideSlope.FLAT,
        "5:1 to 4:1": SideSlope.MODERATE,
    }
    CLEAR_ZONE_PICKS = {
        "Minimum": ClearZoneSelection.MINIMUM,
        "Midpoint": ClearZoneSelection.MIDPOINT,
        "Maximum": ClearZoneSelection.MAXIMUM,
        "Custom": ClearZoneSelection.CUSTOM,
    }
    PDF_STYLES = {
        "Complete Calculation Package": ReportStyle.COMPLETE,
        "Summary Only": ReportStyle.SUMMARY,
        "Detailed Calculations Only": ReportStyle.DETAIL,
    }

    root = tk.Tk()
    root.title(f"Guardrail Length-of-Need Calculator {APP_VERSION}")
    root.geometry("1040x850")
    root.minsize(900, 700)
    root.configure(background="#111827")

    style = ttk.Style(root)
    if "clam" in style.theme_names():
        style.theme_use("clam")
    dark_bg = "#111827"
    panel_bg = "#1F2937"
    input_bg = "#0F172A"
    border = "#374151"
    text_fg = "#E5E7EB"
    muted_fg = "#9CA3AF"
    accent = "#3B82F6"
    style.configure(".", background=dark_bg, foreground=text_fg, fieldbackground=input_bg, bordercolor=border, lightcolor=border, darkcolor=border)
    style.configure("TFrame", background=dark_bg)
    style.configure("TLabel", background=dark_bg, foreground=text_fg)
    style.configure("Title.TLabel", font=("Segoe UI", 18, "bold"), foreground="#93C5FD", background=dark_bg)
    style.configure("Subtitle.TLabel", font=("Segoe UI", 9), foreground=muted_fg, background=dark_bg)
    style.configure("TLabelframe", background=panel_bg, bordercolor=border, relief="solid")
    style.configure("TLabelframe.Label", background=panel_bg, foreground="#BFDBFE")
    style.configure("Section.TLabelframe", background=panel_bg, bordercolor=border)
    style.configure("Section.TLabelframe.Label", font=("Segoe UI", 10, "bold"), foreground="#93C5FD", background=panel_bg)
    style.configure("TEntry", fieldbackground=input_bg, foreground=text_fg, insertcolor=text_fg, bordercolor=border)
    style.map("TEntry", fieldbackground=[("disabled", "#1F2937"), ("readonly", input_bg)], foreground=[("disabled", "#6B7280")])
    style.configure("TCombobox", fieldbackground=input_bg, background=input_bg, foreground=text_fg, arrowcolor=text_fg, bordercolor=border)
    style.map("TCombobox", fieldbackground=[("readonly", input_bg), ("disabled", "#1F2937")], foreground=[("readonly", text_fg), ("disabled", "#6B7280")], selectbackground=[("readonly", input_bg)], selectforeground=[("readonly", text_fg)])
    style.configure("TButton", background="#374151", foreground=text_fg, bordercolor="#4B5563", padding=(8, 5))
    style.map("TButton", background=[("active", "#4B5563"), ("pressed", "#1F2937"), ("disabled", "#1F2937")], foreground=[("disabled", "#6B7280")])
    style.configure("Primary.TButton", font=("Segoe UI", 10, "bold"), background=accent, foreground="#FFFFFF", bordercolor="#60A5FA")
    style.map("Primary.TButton", background=[("active", "#2563EB"), ("pressed", "#1D4ED8")])
    style.configure("TCheckbutton", background=panel_bg, foreground=text_fg)
    style.map("TCheckbutton", background=[("active", panel_bg)], foreground=[("active", "#FFFFFF")])
    style.configure("TRadiobutton", background=dark_bg, foreground=text_fg)
    style.map("TRadiobutton", background=[("active", dark_bg)], foreground=[("active", "#FFFFFF")])
    style.configure("ClearZone.TLabel", font=("Segoe UI", 10, "bold"), foreground="#6EE7B7", background="#064E3B")
    style.configure("Result.Treeview", rowheight=26, font=("Segoe UI", 10), background=input_bg, fieldbackground=input_bg, foreground=text_fg, bordercolor=border)
    style.map("Result.Treeview", background=[("selected", "#1D4ED8")], foreground=[("selected", "#FFFFFF")])
    style.configure("Result.Treeview.Heading", font=("Segoe UI", 9, "bold"), background="#374151", foreground=text_fg, relief="flat")
    style.map("Result.Treeview.Heading", background=[("active", "#4B5563")])
    style.configure("Vertical.TScrollbar", background="#374151", troughcolor=input_bg, arrowcolor=text_fg, bordercolor=border)

    outer = ttk.Frame(root)
    outer.pack(fill="both", expand=True)
    canvas = tk.Canvas(outer, highlightthickness=0, background=dark_bg)
    scrollbar = ttk.Scrollbar(outer, orient="vertical", command=canvas.yview)
    content = ttk.Frame(canvas, padding=18)
    content_window = canvas.create_window((0, 0), window=content, anchor="nw")
    canvas.configure(yscrollcommand=scrollbar.set)
    canvas.pack(side="left", fill="both", expand=True)
    scrollbar.pack(side="right", fill="y")

    def resize_content(event):
        canvas.itemconfigure(content_window, width=event.width)

    def update_scrollregion(_event=None):
        canvas.configure(scrollregion=canvas.bbox("all"))

    canvas.bind("<Configure>", resize_content)
    content.bind("<Configure>", update_scrollregion)
    canvas.bind_all("<MouseWheel>", lambda event: canvas.yview_scroll(int(-event.delta / 120), "units"))
    content.columnconfigure(0, weight=1)
    content.columnconfigure(1, weight=1)

    # Project metadata
    project_var = tk.StringVar()
    route_var = tk.StringVar()
    job_var = tk.StringVar()
    prepared_var = tk.StringVar()
    checked_var = tk.StringVar()
    date_var = tk.StringVar(value=datetime.now().strftime("%Y-%m-%d"))

    # Roadway and design inputs
    facility_var = tk.StringVar(value="Two-Lane, Two-Way Roadway")
    speed_var = tk.StringVar(value="60")
    adt_var = tk.StringVar(value="6000")
    la_mode_var = tk.StringVar(value="Select from Clear-Zone Table")
    LA_var = tk.StringVar(value="30")
    slope_var = tk.StringVar(value="6:1 or Flatter")
    cz_pick_var = tk.StringVar(value="Midpoint")
    cz_custom_var = tk.StringVar()
    L2_var = tk.StringVar(value="10")
    lane_width_var = tk.StringVar(value="12")
    add_dist_var = tk.StringVar()
    div_lane_w_var = tk.StringVar(value="12")
    lanes_this_var = tk.StringVar(value="2")
    lanes_opp_var = tk.StringVar(value="2")
    median_w_var = tk.StringVar(value="40")
    l1_mode_var = tk.StringVar(value="Standard")
    L1_custom_var = tk.StringVar(value=f"{DEFAULT_L1_FT:.4f}")
    term_mode_var = tk.StringVar(value="Default")
    term_custom_var = tk.StringVar(value=f"{DEFAULT_TERMINAL_SECTION_FT:.4f}")
    flare_var = tk.StringVar(value="30:1")
    clear_zone_used_var = tk.StringVar()

    # Output options
    pdf_style_var = tk.StringVar(value="Complete Calculation Package")
    pdf_path_var = tk.StringVar()
    include_appendix_var = tk.BooleanVar(value=True)
    auto_open_var = tk.BooleanVar(value=True)
    status_var = tk.StringVar(value="Ready")

    def add_field(parent, row, label, variable, kind="entry", values=None, width=24):
        ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
        if kind == "combo":
            widget = ttk.Combobox(parent, textvariable=variable, values=values or [], state="readonly", width=width)
        else:
            widget = ttk.Entry(parent, textvariable=variable, width=width)
        widget.grid(row=row, column=1, sticky="ew", pady=4)
        parent.columnconfigure(1, weight=1)
        return widget

    header = ttk.Frame(content)
    header.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 12))
    ttk.Label(header, text="Guardrail Length-of-Need Calculator", style="Title.TLabel").pack(anchor="w")
    ttk.Label(
        header,
        text="MDOT Table 9-6-A calculation package with GR-4 design outputs",
        style="Subtitle.TLabel",
    ).pack(anchor="w")

    project_frame = ttk.LabelFrame(content, text="Project Information", padding=12, style="Section.TLabelframe")
    project_frame.grid(row=1, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    project_frame.columnconfigure(1, weight=1)
    project_frame.columnconfigure(3, weight=1)
    project_fields = [
        ("Project", project_var), ("Job Number", job_var),
        ("Route / Location", route_var), ("Calculation Date", date_var),
        ("Prepared By", prepared_var), ("Checked By", checked_var),
    ]
    for index, (label, variable) in enumerate(project_fields):
        row, side = divmod(index, 2)
        col = side * 2
        ttk.Label(project_frame, text=label).grid(row=row, column=col, sticky="w", padx=(0, 10), pady=4)
        ttk.Entry(project_frame, textvariable=variable).grid(row=row, column=col + 1, sticky="ew", padx=(0, 14), pady=4)

    roadway_frame = ttk.LabelFrame(content, text="Roadway Geometry", padding=12, style="Section.TLabelframe")
    roadway_frame.grid(row=2, column=0, sticky="nsew", padx=(0, 5), pady=(0, 10))
    facility_combo = add_field(roadway_frame, 0, "Facility Type", facility_var, "combo", list(FACILITIES))
    speed_combo = add_field(
        roadway_frame, 1, "Design Speed (mph)", speed_var, "combo",
        [str(speed) for speed in SUPPORTED_SPEEDS],
    )
    add_field(roadway_frame, 2, "Design ADT", adt_var)
    add_field(roadway_frame, 3, "Near-Side Offset, L2 (ft)", L2_var)
    lane_width_entry = add_field(roadway_frame, 4, "Lane Width (ft)", lane_width_var)
    add_dist_entry = add_field(roadway_frame, 5, "Added Distance to Opposing ETW (ft)", add_dist_var)

    helper = ttk.LabelFrame(roadway_frame, text="Divided Highway Distance Helper", padding=8)
    helper.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    helper_widgets = []
    linked_distance_var = tk.BooleanVar(value=False)
    helper_values = [
        ("Lane Width", div_lane_w_var, 7),
        ("Lanes This Side", lanes_this_var, 5),
        ("Lanes Opposite", lanes_opp_var, 5),
        ("Median Width", median_w_var, 7),
    ]
    for i, (label, variable, entry_width) in enumerate(helper_values):
        ttk.Label(helper, text=label).grid(row=0, column=i, sticky="w", padx=3)
        entry = ttk.Entry(helper, textvariable=variable, width=entry_width)
        entry.grid(row=1, column=i, sticky="ew", padx=3, pady=(2, 4))
        helper_widgets.append(entry)

    def roadway_snapshot():
        facility = FACILITIES[facility_var.get()]
        L2 = _first_number(L2_var.get())
        if facility == "two_lane_two_way":
            return validation.create_roadway(facility, L2, _first_number(lane_width_var.get()))
        return validation.create_roadway(
            facility, L2, _first_number(div_lane_w_var.get()),
            _first_number(lanes_this_var.get()), _first_number(lanes_opp_var.get()),
            _first_number(median_w_var.get()),
            None if linked_distance_var.get() else _first_number(add_dist_var.get()),
        )

    def refresh_added_distance(*_args):
        divided = FACILITIES[facility_var.get()] == "divided_highway"
        add_dist_entry.configure(state=("readonly" if linked_distance_var.get() else "normal") if divided else "disabled")
        if not linked_distance_var.get():
            return
        try:
            roadway = validation.roadway_inputs(
                "divided_highway", _first_number(L2_var.get()), _first_number(div_lane_w_var.get()),
                _first_number(lanes_this_var.get()), _first_number(lanes_opp_var.get()),
                _first_number(median_w_var.get()),
            )
            add_dist_var.set(f"{roadway['added_distance']:.4f}")
        except ValueError:
            add_dist_var.set("")

    def compute_added_distance():
        try:
            linked_distance_var.set(True)
            roadway_snapshot()
        except ValueError as e:
            messagebox.showerror("Distance Helper", f"Could not compute the added distance.\n\n{e}")

    helper_button = ttk.Button(helper, text="Use Calculated Distance", command=compute_added_distance)
    helper_button.grid(row=2, column=0, columnspan=4, sticky="ew", padx=3, pady=(3, 0))
    helper_widgets.append(helper_button)
    linked_check = ttk.Checkbutton(helper, text="Keep distance linked to lane/median dimensions",
                                  variable=linked_distance_var)
    linked_check.grid(row=3, column=0, columnspan=4, sticky="w", padx=3)
    helper_widgets.append(linked_check)
    for variable in (div_lane_w_var, lanes_this_var, lanes_opp_var, median_w_var, L2_var, linked_distance_var):
        variable.trace_add("write", refresh_added_distance)

    design_frame = ttk.LabelFrame(content, text="Design Parameters", padding=12, style="Section.TLabelframe")
    design_frame.grid(row=2, column=1, sticky="nsew", padx=(5, 0), pady=(0, 10))
    la_mode_combo = add_field(design_frame, 0, "Hazard Offset Source", la_mode_var, "combo", list(LA_MODES))
    LA_entry = add_field(design_frame, 1, "Hazard Offset, LA (ft)", LA_var)
    slope_combo = add_field(design_frame, 2, "Clear-Zone Side Slope", slope_var, "combo", list(SLOPES))
    cz_pick_combo = add_field(design_frame, 3, "Clear-Zone Selection", cz_pick_var, "combo", list(CLEAR_ZONE_PICKS))
    cz_custom_entry = add_field(design_frame, 4, "Custom Clear Zone (ft)", cz_custom_var)
    l1_mode_combo = add_field(design_frame, 5, "Transition Length, L1", l1_mode_var, "combo", ["Standard", "Custom"])
    L1_custom_entry = add_field(design_frame, 6, "Custom L1 (ft)", L1_custom_var)
    term_mode_combo = add_field(design_frame, 7, "Terminal Section", term_mode_var, "combo", ["Default", "Custom"])
    term_custom_entry = add_field(design_frame, 8, "Custom Terminal Length (ft)", term_custom_var)
    flare_combo = add_field(
        design_frame, 9, "Flare Rate, a/b", flare_var, "combo",
        [f"{rate}:1" for rate in SUPPORTED_FLARE_RATES if rate] + ["Non-Flared"],
    )
    clear_zone_used_label = ttk.Label(
        design_frame, textvariable=clear_zone_used_var, style="ClearZone.TLabel",
        anchor="center", padding=(8, 7),
    )
    clear_zone_used_label.grid(row=10, column=0, columnspan=2, sticky="ew", pady=(9, 2))

    pdf_frame = ttk.LabelFrame(content, text="Calculation Package Output", padding=12, style="Section.TLabelframe")
    pdf_frame.grid(row=3, column=0, columnspan=2, sticky="ew", pady=(0, 10))
    pdf_frame.columnconfigure(1, weight=1)
    pdf_style_combo = add_field(pdf_frame, 0, "Package Content", pdf_style_var, "combo", list(PDF_STYLES), width=32)
    ttk.Label(pdf_frame, text="PDF File").grid(row=1, column=0, sticky="w", padx=(0, 10), pady=4)
    path_frame = ttk.Frame(pdf_frame)
    path_frame.grid(row=1, column=1, sticky="ew", pady=4)
    path_frame.columnconfigure(0, weight=1)
    ttk.Entry(path_frame, textvariable=pdf_path_var).grid(row=0, column=0, sticky="ew")

    def pick_pdf_path():
        default_name = _safe_filename(
            f"{project_var.get().strip()}_guardrail_calc_sheet"
            if project_var.get().strip() else "guardrail_calc_sheet"
        )
        path = filedialog.asksaveasfilename(
            title="Save Guardrail Calculation Package",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")],
        )
        if path:
            pdf_path_var.set(path)
        return path

    ttk.Button(path_frame, text="Browse...", command=pick_pdf_path).grid(row=0, column=1, padx=(8, 0))
    checks = ttk.Frame(pdf_frame)
    checks.grid(row=2, column=0, columnspan=2, sticky="w", pady=(5, 0))
    ttk.Checkbutton(checks, text="Include MDOT reference appendix", variable=include_appendix_var).pack(side="left")
    ttk.Checkbutton(checks, text="Open PDF after generation", variable=auto_open_var).pack(side="left", padx=(24, 0))

    results_frame = ttk.LabelFrame(content, text="Calculated Results", padding=12, style="Section.TLabelframe")
    results_frame.grid(row=4, column=0, columnspan=2, sticky="nsew", pady=(0, 10))
    results_frame.columnconfigure(0, weight=1)
    results_tree = ttk.Treeview(
        results_frame,
        columns=("near", "opposing"),
        show="tree headings",
        height=7,
        style="Result.Treeview",
    )
    results_tree.heading("#0", text="Result")
    results_tree.heading("near", text="Near Side")
    results_tree.heading("opposing", text="Opposing Side")
    results_tree.column("#0", width=270, anchor="w")
    results_tree.column("near", width=170, anchor="e")
    results_tree.column("opposing", width=170, anchor="e")
    results_tree.grid(row=0, column=0, sticky="nsew")
    result_scroll = ttk.Scrollbar(results_frame, orient="vertical", command=results_tree.yview)
    result_scroll.grid(row=0, column=1, sticky="ns")
    results_tree.configure(yscrollcommand=result_scroll.set)

    def set_state(widget, enabled):
        widget.configure(state=("normal" if enabled else "disabled"))

    def update_conditional_fields(_event=None):
        divided = FACILITIES[facility_var.get()] == "divided_highway"
        set_state(lane_width_entry, not divided)
        set_state(add_dist_entry, divided)
        for widget in helper_widgets:
            set_state(widget, divided)
        refresh_added_distance()

        clearzone = LA_MODES[la_mode_var.get()] == "clearzone"
        set_state(LA_entry, not clearzone)
        set_state(slope_combo, clearzone)
        set_state(cz_pick_combo, clearzone)
        set_state(cz_custom_entry, clearzone and CLEAR_ZONE_PICKS[cz_pick_var.get()] == "custom")
        set_state(L1_custom_entry, l1_mode_var.get() == "Custom")
        set_state(term_custom_entry, term_mode_var.get() == "Custom")
        refresh_clear_zone_display()

    for combo in (facility_combo, la_mode_combo, cz_pick_combo, l1_mode_combo, term_mode_combo):
        combo.bind("<<ComboboxSelected>>", update_conditional_fields)

    def compute_clear_zone(speed, adt):
        slope = SLOPES[slope_var.get()]
        pick = CLEAR_ZONE_PICKS[cz_pick_var.get()]
        custom_value = float(_first_number(cz_custom_var.get())) if pick == "custom" else None
        return resolve_clear_zone(speed, adt, slope, pick, custom_value)

    def refresh_clear_zone_display(*_args):
        if LA_MODES[la_mode_var.get()] != "clearzone":
            clear_zone_used_var.set("")
            clear_zone_used_label.grid_remove()
            return
        clear_zone_used_label.grid()
        try:
            selected_la = compute_clear_zone(int(speed_var.get()), float(_first_number(adt_var.get())))
            clear_zone_used_var.set(f"AUTOMATIC CLEAR ZONE:  LA USED = {selected_la:.4f} FT")
        except ValueError:
            clear_zone_used_var.set("AUTOMATIC CLEAR ZONE:  Enter valid values to determine LA")

    for variable in (speed_var, adt_var, slope_var, cz_pick_var, cz_custom_var, la_mode_var):
        variable.trace_add("write", refresh_clear_zone_display)

    def calculate_model() -> CalculationSnapshot:
        speed = int(speed_var.get())
        adt = _first_number(adt_var.get())
        source = LA_MODES[la_mode_var.get()]
        LA = _first_number(LA_var.get()) if source == HazardOffsetSource.DIRECT else compute_clear_zone(speed, adt)
        if source == HazardOffsetSource.CLEAR_ZONE:
            clear_zone_used_var.set(f"AUTOMATIC CLEAR ZONE:  LA USED = {LA:.4f} FT")
        roadway = roadway_snapshot()
        L1 = DEFAULT_L1_FT if l1_mode_var.get() == "Standard" else _first_number(L1_custom_var.get())
        terminal = DEFAULT_TERMINAL_SECTION_FT if term_mode_var.get() == "Default" else _first_number(term_custom_var.get())
        flare = 0.0 if flare_var.get() == "Non-Flared" else _first_number(flare_var.get().split(":")[0])
        barrier = HazardBarrierInputs(
            LA, L1, terminal, flare, source,
            SLOPES[slope_var.get()] if source == HazardOffsetSource.CLEAR_ZONE else None,
            CLEAR_ZONE_PICKS[cz_pick_var.get()] if source == HazardOffsetSource.CLEAR_ZONE else None,
        )
        project = ProjectMetadata(project_var.get().strip(), route_var.get().strip(),
                                  job_var.get().strip(), prepared_var.get().strip(),
                                  checked_var.get().strip(), date_var.get().strip() or datetime.now().strftime("%Y-%m-%d"))
        return create_snapshot(project, CalculationInputs(speed, adt, roadway, barrier))

    def show_results(result):
        results = result.as_dict()
        for item in results_tree.get_children():
            results_tree.delete(item)
        rows = [
            ("Runout Length, LR", f"{results['LR']:.4f} ft", f"{results['LR']:.4f} ft"),
            ("Minimum X", f"{results['X_min_near']:.4f} ft", f"{results['X_min_opp']:.4f} ft"),
            ("Required Rail Length", f"B = {results['B_required']:.4f} ft", f"D = {results['D_required']:.4f} ft"),
            ("Rounded Rail Length", f"B = {results['B']:.4f} ft", f"D = {results['D']:.4f} ft"),
            ("Final Overall Length", f"A = {results['A']:.4f} ft", f"C = {results['C']:.4f} ft"),
            ("Including Gating", f"{results['A_plus_gating']:.4f} ft", f"{results['C_plus_gating']:.4f} ft"),
        ]
        for label, near, opposing in rows:
            results_tree.insert("", "end", text=label, values=(near, opposing))

    def clear_results():
        for item in results_tree.get_children():
            results_tree.delete(item)

    auto_calculate_job = {"id": None}

    def run_auto_calculation():
        auto_calculate_job["id"] = None
        try:
            snapshot = calculate_model()
            show_results(snapshot.result)
            status_var.set("Results updated automatically.")
        except Exception as exc:
            if not isinstance(exc, ValueError):
                LOGGER.exception("Automatic calculation failed")
            clear_results()
            status_var.set(f"Waiting for valid calculation inputs: {exc}" if isinstance(exc, ValueError)
                           else "Automatic calculation failed; diagnostic details were logged.")

    def schedule_auto_calculation(*_args):
        if auto_calculate_job["id"] is not None:
            root.after_cancel(auto_calculate_job["id"])
        auto_calculate_job["id"] = root.after(350, run_auto_calculation)

    def calculate_action():
        try:
            snapshot = calculate_model()
            show_results(snapshot.result)
            status_var.set("Calculation complete. No PDF was generated.")
        except Exception as e:
            if not isinstance(e, (ValueError, OSError)):
                LOGGER.exception("Application action failed")
            status_var.set("Calculation failed.")
            messagebox.showerror("Calculation Error", str(e))

    def generate_pdf_action():
        try:
            snapshot = calculate_model()
            report = ReportModel(snapshot, PDF_STYLES[pdf_style_var.get()], datetime.now().strftime("%Y-%m-%d %H:%M"))
            pdf_data = report_payload(report)
            show_results(snapshot.result)
            out_path = pdf_path_var.get().strip()
            if not out_path:
                out_path = pick_pdf_path()
            if not out_path:
                status_var.set("PDF generation cancelled.")
                return
            appendix_used = write_report(
                out_path,
                report,
                auto_open=auto_open_var.get(),
                include_appendix=include_appendix_var.get(),
            )
            pdf_path_var.set(out_path)
            status_var.set(f"PDF generated: {out_path}")
            if include_appendix_var.get():
                manifest = appendix_manifest(pdf_data)
                included = [title for _, title, path in manifest if os.path.exists(path)]
                missing = [os.path.basename(path) for _, _, path in manifest if not os.path.exists(path)]
                appendix_note = "\n\nIncluded references:\n- " + "\n- ".join(included)
                if missing:
                    appendix_note += "\n\nMissing embedded references:\n- " + "\n- ".join(missing)
                elif appendix_used:
                    appendix_note += "\n\nAll expected embedded references were included."
            else:
                appendix_note = "\n\nReference appendices were not requested."
            messagebox.showinfo("Calculation Package Generated", f"PDF written to:\n{out_path}{appendix_note}")
        except Exception as e:
            if not isinstance(e, (ValueError, OSError)):
                LOGGER.exception("Application action failed")
            status_var.set("PDF generation failed.")
            messagebox.showerror("PDF Generation Error", str(e))

    def generate_dxf_action():
        try:
            snapshot = calculate_model()
            roadway = snapshot.inputs.roadway.as_dict()
            validation.require_drawing_crossing(roadway)
            show_results(snapshot.result)
            dialog = tk.Toplevel(root)
            dialog.title("To-Scale Guardrail DXF")
            dialog.configure(background=dark_bg)
            dialog.transient(root)
            dialog.grab_set()
            dialog.resizable(False, False)
            body = ttk.Frame(dialog, padding=14)
            body.grid(sticky="nsew")
            mode_var = tk.StringVar(value="standalone")
            bridge_length_var = tk.StringVar(value="100")
            landxml_path_var = tk.StringVar()
            alignment_var = tk.StringVar()
            bridge_start_var = tk.StringVar()
            bridge_end_var = tk.StringVar()
            divided_layout_var = tk.StringVar(value="Outside Opposing Clear Zone")
            loaded_alignments = {}
            accepted = {"value": False}

            ttk.Label(body, text="Drawing Placement", font=("Segoe UI", 10, "bold")).grid(row=0, column=0, columnspan=3, sticky="w", pady=(0, 6))
            ttk.Radiobutton(body, text="Standalone (1 DXF unit = 1 foot)", variable=mode_var, value="standalone").grid(row=1, column=0, columnspan=3, sticky="w")
            ttk.Radiobutton(body, text="LandXML project-coordinate overlay", variable=mode_var, value="landxml").grid(row=2, column=0, columnspan=3, sticky="w")
            ttk.Label(body, text="Standalone Bridge Length (ft)").grid(row=3, column=0, sticky="w", pady=4)
            bridge_length_entry = ttk.Entry(body, textvariable=bridge_length_var, width=24)
            bridge_length_entry.grid(row=3, column=1, columnspan=2, sticky="ew", pady=4)
            ttk.Label(body, text="LandXML File").grid(row=4, column=0, sticky="w", pady=4)
            landxml_entry = ttk.Entry(body, textvariable=landxml_path_var, width=42, state="readonly")
            landxml_entry.grid(row=4, column=1, sticky="ew", pady=4)

            def invalidate_landxml(*_args):
                loaded_alignments.clear()
                alignment_var.set("")
                bridge_start_var.set("")
                bridge_end_var.set("")
                alignment_combo.configure(values=[])

            landxml_path_var.trace_add("write", invalidate_landxml)

            def browse_landxml():
                path = filedialog.askopenfilename(parent=dialog, title="Select LandXML", filetypes=[("LandXML", "*.xml"), ("XML", "*.xml")])
                if not path:
                    return
                landxml_path_var.set(path)
                try:
                    rejected = []
                    alignments = guardrail_landxml.load_alignments(path, rejected_alignments=rejected)
                except Exception as exc:
                    if not isinstance(exc, (ValueError, OSError, ParseError)):
                        LOGGER.exception("DXF dialog operation failed")
                    messagebox.showerror("LandXML Error", str(exc), parent=dialog)
                    return
                loaded_alignments.clear()
                for index, alignment in enumerate(alignments, 1):
                    regions = " | ".join(alignment.civil_region_labels())
                    label = f"{alignment.name}  ({regions})"
                    if label in loaded_alignments:
                        label += f" [alignment {index}]"
                    loaded_alignments[label] = alignment
                alignment_combo.configure(values=list(loaded_alignments))
                alignment_var.set(next(iter(loaded_alignments)))
                if rejected:
                    messagebox.showwarning("Unsupported LandXML Alignments", "Rejected alignments:\n\n" + "\n".join(rejected), parent=dialog)

            browse_button = ttk.Button(body, text="Browse...", command=browse_landxml)
            browse_button.grid(row=4, column=2, padx=(6, 0))
            ttk.Label(body, text="Alignment").grid(row=5, column=0, sticky="w", pady=4)
            alignment_combo = ttk.Combobox(body, textvariable=alignment_var, state="readonly", width=39)
            alignment_combo.grid(row=5, column=1, columnspan=2, sticky="ew", pady=4)
            ttk.Label(body, text="Bridge Start Station").grid(row=6, column=0, sticky="w", pady=4)
            start_entry = ttk.Entry(body, textvariable=bridge_start_var)
            start_entry.grid(row=6, column=1, columnspan=2, sticky="ew", pady=4)
            ttk.Label(body, text="Bridge End Station").grid(row=7, column=0, sticky="w", pady=4)
            end_entry = ttk.Entry(body, textvariable=bridge_end_var)
            end_entry.grid(row=7, column=1, columnspan=2, sticky="ew", pady=4)
            ttk.Label(body, text="GR-4 Divided Layout").grid(row=8, column=0, sticky="w", pady=4)
            layout_combo = ttk.Combobox(body, textvariable=divided_layout_var, state="readonly", values=["Inside Opposing Clear Zone", "Outside Opposing Clear Zone"])
            layout_combo.grid(row=8, column=1, columnspan=2, sticky="ew", pady=4)

            mode_widgets = (landxml_entry, browse_button, alignment_combo, start_entry, end_entry)
            def update_dxf_dialog(*_args):
                landxml_mode = mode_var.get() == "landxml"
                bridge_length_entry.configure(state="disabled" if landxml_mode else "normal")
                for widget in mode_widgets:
                    widget.configure(state=("normal" if landxml_mode else "disabled"))
                alignment_combo.configure(state=("readonly" if landxml_mode else "disabled"))
                landxml_entry.configure(state=("readonly" if landxml_mode else "disabled"))
                layout_combo.configure(state=("readonly" if roadway["facility"] == "divided_highway" else "disabled"))
            mode_var.trace_add("write", update_dxf_dialog)

            def accept_dialog():
                try:
                    if mode_var.get() == "standalone":
                        bridge_length = _first_number(bridge_length_var.get())
                        if bridge_length <= 0:
                            raise ValueError("Standalone bridge length must be greater than zero.")
                        placement = standalone_placement(snapshot, bridge_length)
                        insunits = 2
                    else:
                        if alignment_var.get() not in loaded_alignments:
                            raise ValueError("Select a valid LandXML alignment.")
                        selected_alignment = loaded_alignments[alignment_var.get()]
                        accepted["bridge_start"] = selected_alignment.civil_to_internal(bridge_start_var.get())
                        accepted["bridge_end"] = selected_alignment.civil_to_internal(bridge_end_var.get())
                        if accepted["bridge_end"] <= accepted["bridge_start"]:
                            raise ValueError("Bridge end station must be greater than bridge start station.")
                        unit_key = "".join(selected_alignment.linear_unit.lower().split())
                        insunits = 21 if "ussurveyfoot" in unit_key or "usfoot" in unit_key else 2
                        placement = AlignmentSelection(
                            PlacementMode.LANDXML, selected_alignment, accepted["bridge_start"],
                            accepted["bridge_end"], landxml_path_var.get(), selected_alignment.linear_unit,
                        )
                    accepted["configuration"] = DrawingExportConfiguration(
                        placement, DividedLayout.INSIDE if divided_layout_var.get().startswith("Inside") else DividedLayout.OUTSIDE,
                        insunits,
                    )
                    accepted["value"] = True
                    dialog.destroy()
                except Exception as exc:
                    if not isinstance(exc, (ValueError, OSError)):
                        LOGGER.exception("DXF dialog operation failed")
                    messagebox.showerror("DXF Input Error", str(exc), parent=dialog)

            buttons = ttk.Frame(body)
            buttons.grid(row=9, column=0, columnspan=3, sticky="e", pady=(10, 0))
            ttk.Button(buttons, text="Cancel", command=dialog.destroy).pack(side="left", padx=4)
            ttk.Button(buttons, text="Continue", command=accept_dialog, style="Primary.TButton").pack(side="left", padx=4)
            update_dxf_dialog()
            dialog.protocol("WM_DELETE_WINDOW", dialog.destroy)
            root.wait_window(dialog)
            if not accepted["value"]:
                status_var.set("DXF generation cancelled.")
                return

            config = accepted["configuration"]
            drawing_model = drawing_inputs(snapshot, config)
            guardrail_dxf.validate_model(drawing_model)
            default_name = _safe_filename(
                f"{snapshot.project.project}_guardrail_plan" if snapshot.project.project else "guardrail_plan"
            ).rsplit(".", 1)[0]
            out_path = filedialog.asksaveasfilename(
                title="Save Guardrail Plan DXF", defaultextension=".dxf", initialfile=default_name,
                filetypes=[("DXF files", "*.dxf"), ("All files", "*.*")],
            )
            if not out_path:
                status_var.set("DXF generation cancelled.")
                return
            guardrail_dxf.export_guardrail_dxf(out_path, drawing_model)
            status_var.set(f"DXF generated: {out_path}")
            messagebox.showinfo("Guardrail Plan DXF Generated", f"DXF written to:\n{out_path}")
        except Exception as e:
            if not isinstance(e, (ValueError, OSError)):
                LOGGER.exception("Application action failed")
            status_var.set("DXF generation failed.")
            messagebox.showerror("DXF Generation Error", str(e))

    actions = ttk.Frame(content)
    actions.grid(row=5, column=0, columnspan=2, sticky="ew", pady=(0, 8))
    actions.columnconfigure(0, weight=1)
    actions.columnconfigure(1, weight=1)
    actions.columnconfigure(2, weight=1)
    ttk.Button(actions, text="Calculate", command=calculate_action, style="Primary.TButton").grid(
        row=0, column=0, sticky="ew", padx=(0, 6), ipady=5
    )
    ttk.Button(actions, text="Generate PDF", command=generate_pdf_action, style="Primary.TButton").grid(
        row=0, column=1, sticky="ew", padx=6, ipady=5
    )
    ttk.Button(actions, text="Export DXF", command=generate_dxf_action, style="Primary.TButton").grid(
        row=0, column=2, sticky="ew", padx=(6, 0), ipady=5
    )
    ttk.Label(content, textvariable=status_var, style="Subtitle.TLabel").grid(
        row=6, column=0, columnspan=2, sticky="w"
    )

    calculation_input_vars = (
        facility_var, speed_var, adt_var, la_mode_var, LA_var, slope_var, cz_pick_var,
        cz_custom_var, L2_var, lane_width_var, add_dist_var, div_lane_w_var,
        lanes_this_var, lanes_opp_var, median_w_var, l1_mode_var, L1_custom_var,
        term_mode_var, term_custom_var, flare_var,
    )
    for variable in calculation_input_vars:
        variable.trace_add("write", schedule_auto_calculation)

    update_conditional_fields()
    schedule_auto_calculation()
    root.mainloop()
