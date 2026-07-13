import math
import re
import os, sys
import shutil
import guardrail_dxf
import guardrail_landxml
from io import BytesIO
from datetime import datetime
from typing import Optional
APP_VERSION = "V8.5"
from pypdf import PdfReader, PdfWriter
def resource_path(rel_path: str) -> str:
    base = getattr(sys, "_MEIPASS", os.path.abspath("."))
    return os.path.join(base, rel_path)
def merge_with_appendices(
    main_pdf_path: str,
    appendices: list[tuple[str, str, str]],
    out_pdf_path: str,
) -> None:
    """Append labeled PDF sections while preserving each source page's native size."""
    from reportlab.lib.pagesizes import letter
    from reportlab.pdfgen import canvas as reportlab_canvas

    writer = PdfWriter()

    main_reader = PdfReader(main_pdf_path)
    for p in main_reader.pages:
        writer.add_page(p)

    outline_items = [("Guardrail Calculations", 0)]
    appendix_pages = []

    for appendix_label, title, appendix_path in appendices:
        if not os.path.exists(appendix_path):
            continue

        divider_buffer = BytesIO()
        divider = reportlab_canvas.Canvas(divider_buffer, pagesize=letter)
        page_width, page_height = letter
        divider.setFillColorRGB(0.09, 0.21, 0.36)
        divider.setFont("Helvetica-Bold", 20)
        divider.drawCentredString(page_width / 2, page_height * 0.62, appendix_label)
        divider.setFont("Helvetica-Bold", 15)
        divider.drawCentredString(page_width / 2, page_height * 0.55, title)
        divider.setFont("Helvetica", 9)
        divider.setFillColorRGB(0.25, 0.29, 0.34)
        divider.drawCentredString(
            page_width / 2,
            page_height * 0.48,
            "Embedded reference document included for calculation traceability.",
        )
        divider.save()
        divider_buffer.seek(0)

        divider_index = len(writer.pages)
        writer.add_page(PdfReader(divider_buffer).pages[0])
        appendix_pages.append((divider_index, f"{appendix_label} - {title}"))
        outline_items.append((f"{appendix_label} - {title}", divider_index))

        appendix_reader = PdfReader(appendix_path)
        for page in appendix_reader.pages:
            page_index = len(writer.pages)
            writer.add_page(page)
            appendix_pages.append((page_index, f"{appendix_label} - {title}"))

    total_pages = len(writer.pages)
    for page_index, footer_label in appendix_pages:
        page = writer.pages[page_index]
        page_width = float(page.mediabox.width)
        page_height = float(page.mediabox.height)
        overlay_buffer = BytesIO()
        overlay = reportlab_canvas.Canvas(overlay_buffer, pagesize=(page_width, page_height))
        overlay.setStrokeColorRGB(0.72, 0.75, 0.78)
        overlay.setLineWidth(0.5)
        overlay.line(40, 27, page_width - 40, 27)
        overlay.setFont("Helvetica", 7)
        overlay.setFillColorRGB(0.24, 0.27, 0.31)
        overlay.drawString(40, 16, footer_label)
        overlay.drawRightString(page_width - 40, 16, f"Page {page_index + 1} of {total_pages}")
        overlay.save()
        overlay_buffer.seek(0)
        page.merge_page(PdfReader(overlay_buffer).pages[0])

    for title, page_index in outline_items:
        writer.add_outline_item(title, page_index)

    with open(out_pdf_path, "wb") as f:
        writer.write(f)




INCR_GUARDRAIL_FT = 12.5
DEFAULT_L1_FT = 18 + (1.75 / 12.0)          # 18'-1.75" (Example 9-6-1)
DEFAULT_TERMINAL_SECTION_FT = 25.0          # GR-4 shows 25'-0" terminal section
DEFAULT_GATING_FT = 12.5                    # MDOT examples add 12.5' gating portion


# MDOT Roadway Design Manual (2020) Table 9-6-A (Barrier Length of Need)
# Columns: ADT bucket -> LR
#   10,000 ; 5,000-10,000 ; 1,000-5,000 ; under 1,000
TABLE_9_6_A = {
    70: {"LR": [360, 330, 290, 250]},
    65: {"LR": [330, 290, 250, 225]},
    60: {"LR": [300, 250, 210, 200]},
    55: {"LR": [265, 220, 185, 175]},
    50: {"LR": [230, 190, 160, 150]},
    45: {"LR": [195, 160, 135, 125]},
    40: {"LR": [160, 130, 110, 100]},
    35: {"LR": [135, 110, 95, 85]},
    30: {"LR": [110, 90, 80, 70]},
}

# "Basic" clear zone table (the simplified version you were using earlier)
# (This is Table 9-2-A values for 6:1 or flatter AND 5:1 to 4:1, as ranges)
TABLE_9_2_A = {
    "40_or_less": {
        "under_750":     {"6:1_or_flatter": (7, 10),  "5:1_to_4:1": (7, 10)},
        "750_1500":      {"6:1_or_flatter": (10, 12), "5:1_to_4:1": (12, 14)},
        "1501_6000":     {"6:1_or_flatter": (12, 14), "5:1_to_4:1": (14, 16)},
        "over_6000":     {"6:1_or_flatter": (14, 16), "5:1_to_4:1": (16, 18)},
    },
    "45_50": {
        "under_750":     {"6:1_or_flatter": (10, 12), "5:1_to_4:1": (12, 14)},
        "750_1500":      {"6:1_or_flatter": (14, 16), "5:1_to_4:1": (16, 20)},
        "1501_6000":     {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 26)},
        "over_6000":     {"6:1_or_flatter": (20, 22), "5:1_to_4:1": (24, 28)},
    },
    "55": {
        "under_750":     {"6:1_or_flatter": (12, 14), "5:1_to_4:1": (14, 18)},
        "750_1500":      {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 24)},
        "1501_6000":     {"6:1_or_flatter": (20, 22), "5:1_to_4:1": (24, 30)},
        "over_6000":     {"6:1_or_flatter": (22, 24), "5:1_to_4:1": (26, 32)},
    },
    "60": {
        "under_750":     {"6:1_or_flatter": (16, 18), "5:1_to_4:1": (20, 24)},
        "750_1500":      {"6:1_or_flatter": (20, 24), "5:1_to_4:1": (26, 32)},
        "1501_6000":     {"6:1_or_flatter": (26, 30), "5:1_to_4:1": (32, 40)},
        "over_6000":     {"6:1_or_flatter": (30, 32), "5:1_to_4:1": (36, 44)},
    },
    "65_70": {
        "under_750":     {"6:1_or_flatter": (18, 20), "5:1_to_4:1": (20, 26)},
        "750_1500":      {"6:1_or_flatter": (24, 26), "5:1_to_4:1": (28, 36)},
        "1501_6000":     {"6:1_or_flatter": (28, 32), "5:1_to_4:1": (34, 42)},
        "over_6000":     {"6:1_or_flatter": (30, 34), "5:1_to_4:1": (38, 46)},
    },
}


def _first_number(s: str) -> float:
    """
    Pull the first numeric token out of a messy input like:
      "6000, 2030" -> 6000
      "  18'-1.75\"" -> 18  (so don't do that; use ft inputs)
    """
    s = s.replace(",", " ")
    m = re.search(r"[-+]?\d*\.?\d+", s)
    if not m:
        raise ValueError("No number found")
    return float(m.group(0))


def prompt_float(msg: str, allow_blank: bool = False, default=None) -> float:
    while True:
        s = input(msg).strip()
        if allow_blank and s == "":
            return default
        try:
            return _first_number(s)
        except ValueError:
            print("  Please enter a number (you can include commas; I'll use the first number).")


def prompt_choice(msg: str, options: list[str]) -> str:
    opt_map = {str(i + 1): v for i, v in enumerate(options)}
    while True:
        print(msg)
        for i, v in enumerate(options, start=1):
            print(f"  {i}) {v}")
        sel = input("> ").strip()
        if sel in opt_map:
            return opt_map[sel]
        if sel in options:
            return sel
        print("  Pick one of the listed options.")


def fmt_ft_in(x_ft: float) -> str:
    """Pretty format like 18.1458 -> 18'-1.75\" (approx)."""
    if x_ft is None:
        return ""
    sign = "-" if x_ft < 0 else ""
    x = abs(x_ft)
    ft = int(x)
    inches = (x - ft) * 12.0
    return f"{sign}{ft}'-{inches:.4f}\""


def adt_bucket_index(adt: float) -> int:
    # Matches Table 9-6-A columns: 10,000 ; 5,000-10,000 ; 1,000-5,000 ; under 1,000
    if adt >= 10000:
        return 0
    if adt >= 5000:
        return 1
    if adt >= 1000:
        return 2
    return 3


def get_lr(speed_mph: int, adt: float) -> float:
    idx = adt_bucket_index(adt)
    return float(TABLE_9_6_A[speed_mph]["LR"][idx])


def speed_group_clearzone(speed: float) -> str:
    if speed <= 40:
        return "40_or_less"
    if 45 <= speed <= 50:
        return "45_50"
    if int(speed) == 55:
        return "55"
    if int(speed) == 60:
        return "60"
    return "65_70"


def adt_group_clearzone(adt: float) -> str:
    if adt < 750:
        return "under_750"
    if adt <= 1500:
        return "750_1500"
    if adt <= 6000:
        return "1501_6000"
    return "over_6000"


def resolve_clear_zone(
    speed: float,
    adt: float,
    slope: str,
    selection: str,
    custom_value: Optional[float] = None,
) -> float:
    """Resolve a Table 9-2-A clear-zone selection without UI or console dependencies."""
    if slope not in ("6:1_or_flatter", "5:1_to_4:1"):
        raise ValueError("Invalid clear-zone side-slope category.")
    if selection not in ("min", "mid", "max", "custom"):
        raise ValueError("Invalid clear-zone selection.")

    mn, mx = TABLE_9_2_A[speed_group_clearzone(speed)][adt_group_clearzone(adt)][slope]
    if selection == "min":
        return float(mn)
    if selection == "mid":
        return float((mn + mx) / 2.0)
    if selection == "max":
        return float(mx)
    if custom_value is None:
        raise ValueError("A custom clear-zone value is required.")
    return float(custom_value)


def choose_clear_zone(speed: float, adt: float) -> float:
    group_s = speed_group_clearzone(speed)
    group_a = adt_group_clearzone(adt)

    slope = prompt_choice(
        "Side slope category for Table 9-2-A:",
        ["6:1_or_flatter", "5:1_to_4:1"]
    )

    mn, mx = TABLE_9_2_A[group_s][group_a][slope]
    pick = prompt_choice(
        f"Recommended clear zone range is {mn}-{mx} ft. What do you want to use?",
        ["min", "mid", "max", "custom"]
    )
    custom_value = prompt_float("Enter clear zone value (ft): ") if pick == "custom" else None
    return resolve_clear_zone(speed, adt, slope, pick, custom_value)


def round_up_to_increment(x: float, inc: float) -> float:
    quotient = x / inc
    nearest = round(quotient)
    if math.isclose(quotient, nearest, rel_tol=0.0, abs_tol=1e-9):
        return nearest * inc
    return math.ceil(quotient) * inc


def compute_x_min(speed: int, adt: float, LA: float, L2: float, L1: float, a_over_b: float) -> tuple[float, float]:
    """
    Returns (X_min, LR).
    - Flared equation + non-flared equation come from Table 9-6-A
    """
    LR = get_lr(speed, adt)

    if a_over_b == 0.0:
        # Non-flared design:
        # X = LR (LA - L2) / LA
        X_min = (LR * (LA - L2)) / LA
        return X_min, LR

    # Flared design:
    # X = (LA + (b/a)*L1 - L2) / ( (b/a) + (LA/LR) )
    b_over_a = 1.0 / a_over_b
    numerator = LA + (b_over_a * L1) - L2
    denom = b_over_a + (LA / LR)
    X_min = numerator / denom
    return X_min, LR


def compute_x_design_from_xmin(X_min: float, L1: float) -> tuple[float, float, float]:
    """
    MDOT Example 9-6-1 guardrail workflow:
      - compute flared portion: (X - L1)
      - round up to nearest 12.5 ft
      - add L1 back
    """
    flared_portion = max(0.0, X_min - L1)
    flared_portion_rounded = round_up_to_increment(flared_portion, INCR_GUARDRAIL_FT)
    X_design = flared_portion_rounded + L1
    return flared_portion, flared_portion_rounded, X_design


def compute_guardrail_outputs(
    speed: int,
    adt: float,
    LA: float,
    L2: float,
    L2_opp: float,
    L1: float,
    terminal_section: float,
    a_over_b: float,
) -> dict[str, float]:
    """Shared calc engine for CLI and GUI paths."""
    b_over_a = 0.0 if a_over_b == 0 else 1.0 / a_over_b

    X_min_near, LR = compute_x_min(speed, adt, LA, L2, L1, a_over_b)
    B_required = X_min_near - L1 - terminal_section
    B = round_up_to_increment(max(INCR_GUARDRAIL_FT, B_required), INCR_GUARDRAIL_FT)
    A = B + L1 + terminal_section
    flared_near = B_required
    flared_near_rounded = B
    X_design_near = A
    A_plus_gating = A + DEFAULT_GATING_FT

    X_min_opp, _ = compute_x_min(speed, adt, LA, L2_opp, L1, a_over_b)
    D_required = X_min_opp - L1 - terminal_section
    D = round_up_to_increment(max(INCR_GUARDRAIL_FT, D_required), INCR_GUARDRAIL_FT)
    C = D + L1 + terminal_section
    flared_opp = D_required
    flared_opp_rounded = D
    X_design_opp = C
    C_plus_gating = C + DEFAULT_GATING_FT

    return {
        "LR": LR,
        "b_over_a": b_over_a,
        "X_min_near": X_min_near,
        "B_required": B_required,
        "flared_near": flared_near,
        "flared_near_rounded": flared_near_rounded,
        "X_design_near": X_design_near,
        "A": A,
        "B": B,
        "A_plus_gating": A_plus_gating,
        "X_min_opp": X_min_opp,
        "D_required": D_required,
        "flared_opp": flared_opp,
        "flared_opp_rounded": flared_opp_rounded,
        "X_design_opp": X_design_opp,
        "C": C,
        "D": D,
        "C_plus_gating": C_plus_gating,
    }


def build_pdf_data(
    project: str,
    facility: str,
    speed: int,
    adt: float,
    LA: float,
    L2: float,
    L2_opp: float,
    lane_width: Optional[float],
    L1: float,
    terminal_section: float,
    a_over_b: float,
    pdf_style_num: int,
    results: dict[str, float],
    generated_time: Optional[str] = None,
    route_location: str = "",
    job_number: str = "",
    prepared_by: str = "",
    checked_by: str = "",
    calculation_date: str = "",
) -> dict:
    """Format PDF metadata/payload consistently for both UI and CLI."""
    generated_time = generated_time or datetime.now().strftime("%Y-%m-%d %H:%M")
    calculation_date = calculation_date or datetime.now().strftime("%Y-%m-%d")
    b_over_a = results.get("b_over_a", 0.0 if a_over_b == 0 else 1.0 / a_over_b)
    LR = results.get("LR", 0.0)
    facility_label = {
        "two_lane_two_way": "Two-Lane, Two-Way Roadway",
        "divided_highway": "Divided Highway",
    }.get(facility, facility)

    if a_over_b == 0:
        x_eq_near = f"X = {LR:.4f}({LA:.4f} - {L2:.4f}) / {LA:.4f}"
        x_eq_opp = f"X = {LR:.4f}({LA:.4f} - {L2_opp:.4f}) / {LA:.4f}"
    else:
        x_eq_near = (
            f"X = ({LA:.4f} + {b_over_a:.4f} x {L1:.4f} - {L2:.4f}) / "
            f"({b_over_a:.4f} + ({LA:.4f}/{LR:.4f}))"
        )
        x_eq_opp = (
            f"X = ({LA:.4f} + {b_over_a:.4f} x {L1:.4f} - {L2_opp:.4f}) / "
            f"({b_over_a:.4f} + ({LA:.4f}/{LR:.4f}))"
        )

    return {
        "__app_version": APP_VERSION,
        "__generated_time": generated_time,
        "__pdf_style": int(pdf_style_num),
        "__facility_code": facility,
        "__x_eq_opp": x_eq_opp,
        "__x_eq_near": x_eq_near,
        "__b_required_eq": (
            f"B(required) = {results['X_min_near']:.4f} - {L1:.4f} - {terminal_section:.4f} "
            f"= {results['B_required']:.4f}"
        ),
        "__b_round_eq": (
            f"B = round up max(12.5000, {results['B_required']:.4f}) "
            f"to 12.5000-ft increment = {results['B']:.4f}"
        ),
        "__a_eq_near": (
            f"A = {results['B']:.4f} + {L1:.4f} + {terminal_section:.4f} "
            f"= {results['A']:.4f}"
        ),
        "__d_required_eq": (
            f"D(required) = {results['X_min_opp']:.4f} - {L1:.4f} - {terminal_section:.4f} "
            f"= {results['D_required']:.4f}"
        ),
        "__d_round_eq": (
            f"D = round up max(12.5000, {results['D_required']:.4f}) "
            f"to 12.5000-ft increment = {results['D']:.4f}"
        ),
        "__c_eq_opp": (
            f"C = {results['D']:.4f} + {L1:.4f} + {terminal_section:.4f} "
            f"= {results['C']:.4f}"
        ),
        "Project": project or "(not provided)",
        "Route / Location": route_location or "(not provided)",
        "Job Number": job_number or "(not provided)",
        "Prepared By": prepared_by or "(not provided)",
        "Checked By": checked_by or "(not provided)",
        "Calculation Date": calculation_date,
        "Facility": facility_label,
        "Design speed (mph)": speed,
        "Design ADT": f"{adt:.0f}",
        "LA (ft)": f"{LA:.4f}",
        "Near-side L2 (ft)": f"{L2:.4f}",
        "Opp-side L2 (ft)": f"{L2_opp:.4f}",
        "Lane width (ft)": f"{lane_width:.4f}" if lane_width is not None else "(n/a)",
        "L1 (ft)": f"{L1:.4f} ({fmt_ft_in(L1)})",
        "Terminal section (ft)": f"{terminal_section:.4f}",
        "Flare rate a/b": ("non-flared (0)" if a_over_b == 0 else f"{a_over_b:.0f}/1"),
        "LR (ft)": f"{LR:.4f}",
        "X(min) near (ft)": f"{results['X_min_near']:.4f}",
        "B required (ft)": f"{results['B_required']:.4f}",
        "Flared portion near (ft)": f"{results['flared_near']:.4f}",
        "Flared portion rounded near (ft)": f"{results['flared_near_rounded']:.4f}",
        "X(design) near (ft)": f"{results['X_design_near']:.4f}",
        "X(min) opp (ft)": f"{results['X_min_opp']:.4f}",
        "D required (ft)": f"{results['D_required']:.4f}",
        "Flared portion opp (ft)": f"{results['flared_opp']:.4f}",
        "Flared portion rounded opp (ft)": f"{results['flared_opp_rounded']:.4f}",
        "X(design) opp (ft)": f"{results['X_design_opp']:.4f}",
        "A (near) (ft)": f"{results['A']:.4f}",
        "B (near) (ft)": f"{results['B']:.4f}",
        "C (opp) (ft)": f"{results['C']:.4f}",
        "D (opp) (ft)": f"{results['D']:.4f}",
        "Near + gating (ft)": f"{results['A_plus_gating']:.4f}",
        "Opp + gating (ft)": f"{results['C_plus_gating']:.4f}",
    }


def appendix_manifest(pdf_data: dict) -> list[tuple[str, str, str]]:
    facility = str(pdf_data.get("__facility_code", "two_lane_two_way"))
    standard_name = "GR-4.pdf" if facility == "divided_highway" else "GR-4a.pdf"
    standard_title = (
        "MDOT Standard Plan GR-4 - Divided Highways"
        if facility == "divided_highway"
        else "MDOT Standard Plan GR-4a - Two-Lane, Two-Way Highways"
    )
    return [
        ("APPENDIX A", "MDOT Roadway Design Manual Reference", resource_path("gr manual.pdf")),
        ("APPENDIX B", standard_title, resource_path(standard_name)),
    ]


def write_calc_pdf(
    out_path: str,
    pdf_data: dict,
    auto_open: bool = False,
    include_appendix: bool = True,
) -> bool:
    """
    Render the calc sheet, append available embedded references, and optionally auto-open.
    Returns True when every expected appendix document was appended.
    """
    out_path = os.path.abspath(out_path)
    tmp_pdf = os.path.splitext(out_path)[0] + "_tmp.pdf"
    expected_appendices = appendix_manifest(pdf_data)
    available_appendices = [item for item in expected_appendices if os.path.exists(item[2])]
    appendices_complete = bool(include_appendix and len(available_appendices) == len(expected_appendices))

    try:
        render_data = dict(pdf_data)
        render_data["__include_appendix"] = False
        generate_pdf_calc_sheet(tmp_pdf, render_data)

        if include_appendix and available_appendices:
            merge_with_appendices(tmp_pdf, available_appendices, out_path)
        else:
            shutil.move(tmp_pdf, out_path)

        if auto_open:
            try:
                os.startfile(out_path)
            except Exception as e:
                print(f"Could not auto-open PDF: {e}")

        return appendices_complete
    finally:
        try:
            if os.path.exists(tmp_pdf):
                os.remove(tmp_pdf)
        except OSError:
            pass


# =========================
# NEW STUFF: PDF CALC SHEET
# =========================
def _safe_filename(name: str) -> str:
    name = name.strip()
    if not name:
        return "guardrail_calc_sheet.pdf"
    # Remove invalid Windows filename characters
    name = re.sub(r'[<>:"/\\|?*]+', "_", name)
    if not name.lower().endswith(".pdf"):
        name += ".pdf"
    return name


def _join_path(folder: str, filename: str) -> str:
    folder = (folder or "").strip()
    if folder == "":
        return os.path.abspath(filename)
    return os.path.abspath(os.path.join(folder, filename))


def _generate_pdf_calc_sheet_legacy(pdf_path: str, data: dict) -> None:
    """
    Writes a 1-2 page calc sheet PDF with:
      - Page 1: Summary (inputs + results)
      - Page 2: Example-style calc boxes
    Style selection:
      __pdf_style = 1 -> summary only
      __pdf_style = 2 -> calc boxes only
      __pdf_style = 3 -> both (summary then calc boxes)
    Requires: reportlab (pip install reportlab)
    """
    try:
        from reportlab.lib.pagesizes import letter
        from reportlab.pdfgen import canvas
    except Exception as e:
        raise RuntimeError(
            "ReportLab is not available. Install it with:\n"
            "  python -m pip install reportlab\n"
            f"Original error: {e}"
        )

    c = canvas.Canvas(pdf_path, pagesize=letter)
    width, height = letter

    style = int(data.get("__pdf_style", 3))  # 1=summary, 2=calc, 3=both

    def wrap_text(text: str, font_name: str, font_size: int, max_width: float) -> list[str]:
        """Simple word-wrap using ReportLab stringWidth."""
        from reportlab.pdfbase.pdfmetrics import stringWidth
        if not text:
            return [""]
        words = str(text).split()
        lines = []
        cur = ""
        for w in words:
            test = (cur + " " + w).strip()
            if stringWidth(test, font_name, font_size) <= max_width:
                cur = test
            else:
                if cur:
                    lines.append(cur)
                cur = w
        if cur:
            lines.append(cur)
        return lines

    def draw_box(x, y, w, h, title=None):
        """Draw a rectangle box with optional title."""
        c.rect(x, y, w, h, stroke=1, fill=0)
        if title:
            c.setFont("Helvetica-Bold", 10)
            c.drawString(x + 8, y + h - 14, title)

    def draw_lines_wrapped(x, y_top, w, lines, font="Helvetica", size=9, line_h=12):
        c.setFont(font, size)
        y = y_top
        for line in lines:
            for wl in wrap_text(line, font, size, w):
                c.drawString(x, y, wl)
                y -= line_h
        return y

    def stamp_version():
        ver = str(data.get("__app_version", "")).strip()
        gen = str(data.get("__generated_time", "")).strip()

        if ver or gen:
            c.setFont("Helvetica", 8)
            label = " | ".join(x for x in [
                f"Guardrail Calculation Package {ver}" if ver else "",
                f"Generated {gen}" if gen else ""
        ] if x)
        c.drawRightString(width - 36, 18, label)
    def draw_summary_page():
        def page_break_reset():
            """Stamp footer, advance to a new page, reset y/font."""
            stamp_version()
            c.showPage()
            return height - 60

        y = height - 60
        c.setFont("Helvetica-Bold", 16)
        c.drawString(72, y, "MDOT Guardrail Calc Sheet")
        y -= 18
        c.setFont("Helvetica", 10)
        c.drawString(72, y, "Bridge Approach Guardrail (Table 9-6-A) + GR-4 Outputs (A/B/C/D)")
        y -= 18

        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "INPUTS")
        y -= 14
        c.setFont("Helvetica", 10)

        input_keys = [
            "Project", "Facility", "Design speed (mph)", "Design ADT",
            "LA (ft)", "Near-side L2 (ft)", "Opp-side L2 (ft)",
            "Lane width (ft)", "L1 (ft)", "Terminal section (ft)",
            "Flare rate a/b", "LR (ft)",
        ]
        for k in input_keys:
            if k in data:
                c.drawString(72, y, f"{k}: {data[k]}")
                y -= 12
                if y < 120:
                    y = page_break_reset()
                    c.setFont("Helvetica", 10)

        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "RESULTS")
        y -= 14
        c.setFont("Helvetica", 10)

        c.setFont("Helvetica-Bold", 11)
        c.drawString(72, y, "Near side")
        y -= 12
        c.setFont("Helvetica", 10)
        for k in ["X(min) near (ft)", "Flared portion near (ft)", "Flared portion rounded near (ft)", "X(design) near (ft)"]:
            if k in data:
                c.drawString(90, y, f"{k}: {data[k]}")
                y -= 12
                if y < 120:
                    y = page_break_reset()
                    c.setFont("Helvetica", 10)

        y -= 6
        c.setFont("Helvetica-Bold", 11)
        c.drawString(72, y, "Opposing side")
        y -= 12
        c.setFont("Helvetica", 10)
        for k in ["X(min) opp (ft)", "Flared portion opp (ft)", "Flared portion rounded opp (ft)", "X(design) opp (ft)"]:
            if k in data:
                c.drawString(90, y, f"{k}: {data[k]}")
                y -= 12
                if y < 120:
                    y = page_break_reset()
                    c.setFont("Helvetica", 10)

        y -= 6
        c.setFont("Helvetica-Bold", 12)
        c.drawString(72, y, "GR-4 OUTPUTS (per your definitions)")
        y -= 14
        c.setFont("Helvetica", 10)
        for k in ["A (near) (ft)", "B (near) (ft)", "C (opp) (ft)", "D (opp) (ft)",
                  "Near + gating (ft)", "Opp + gating (ft)"]:
            if k in data:
                c.drawString(72, y, f"{k}: {data[k]}")
                y -= 12
                if y < 90:
                    y = page_break_reset()
                    c.setFont("Helvetica", 10)

        y -= 10
        c.setFont("Helvetica-Oblique", 9)
        c.drawString(72, y, "Note: Summary of entered inputs and computed results (not a stamped design document).")

        # End-of-summary handling:
        if style == 3:
            stamp_version()
            c.showPage()
        else:
            stamp_version()

    def draw_calc_page():
        # ---------- Title ----------
        c.setFont("Helvetica-Bold", 14)
        title = f"{str(data.get('Project','')).strip()} Guardrail Calculations".strip()
        c.drawCentredString(width / 2, height - 50, title)

        left = 54
        right = width - 54
        y = height - 85
        line = 12

        def h2(text):
            nonlocal y
            c.setFont("Helvetica-Bold", 12)
            c.drawString(left, y, text)
            y -= 16

        def label(text):
            nonlocal y
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left, y, text)
            y -= 12

        def txt(text, indent=0, size=10):
            nonlocal y
            c.setFont("Helvetica", size)
            c.drawString(left + indent, y, text)
            y -= line

        def bold(text, indent=0):
            nonlocal y
            c.setFont("Helvetica-Bold", 10)
            c.drawString(left + indent, y, text)
            y -= line

        def wrap(lines, indent=0, font="Helvetica", size=9, lh=11, extra_gap=10):
            nonlocal y
            draw_lines_wrapped(left + indent, y, right - left - indent, lines, font=font, size=size, line_h=lh)
            y -= extra_gap

        def hr():
            nonlocal y
            c.setLineWidth(0.8)
            c.line(left, y, right, y)
            y -= 14

        # Helper getters (keeps blanks from showing "None")
        def g(key, default=""):
            v = data.get(key, default)
            return "" if v is None else str(v)

        # =======================
        # LONG SIDE (NEAR): A & B
        # =======================
        h2("LONG SIDE (Near Side) - A & B")

        label("Given")
        txt(f"Design speed = {g('Design speed (mph)')} mph", indent=12)
        txt(f"ADT = {g('Design ADT')}", indent=12)
        txt(f"LA = {g('LA (ft)')} ft", indent=12)
        txt(f"L2 (near) = {g('Near-side L2 (ft)')} ft", indent=12)
        txt(f"L1 = {g('L1 (ft)')} ft", indent=12)
        txt(f"Terminal section = {g('Terminal section (ft)')} ft", indent=12)
        txt(f"LR = {g('LR (ft)')} ft (Table 9-6-A)", indent=12)

        y -= 4
        label("Compute X (minimum) and X(design) (near)")
        xeq_near = g("__x_eq_near", "")
        if xeq_near:
            wrap([xeq_near], indent=12, font="Helvetica", size=9, lh=11, extra_gap=14)
        bold(f"X(design) (near) = {g('X(design) near (ft)')} ft", indent=12)

        y -= 4
        label("Compute B (near)")
        txt(g("__b_required_eq", ""), indent=12, size=9)
        txt(g("__b_round_eq", ""), indent=12, size=9)
        bold(f"B (near) = {g('B (near) (ft)')} ft", indent=12)

        y -= 4
        label("Compute A (near)")
        txt(g("__a_eq_near", ""), indent=12, size=9)
        bold(f"A (near) = {g('A (near) (ft)')} ft", indent=12)

        hr()

        # =========================
        # SHORT SIDE (FAR): C & D
        # =========================
        h2("SHORT SIDE (Far Side) - C & D")

        label("Given")
        txt(f"L2 (far/opp) = {g('Opp-side L2 (ft)')} ft", indent=12)
        txt(f"L1 = {g('L1 (ft)')} ft", indent=12)
        txt(f"Terminal section = {g('Terminal section (ft)')} ft", indent=12)
        txt(f"LR = {g('LR (ft)')} ft (Table 9-6-A)", indent=12)

        y -= 4
        label("Compute X (minimum) and X(design) (far)")
        # If you later add an explicit opposing equation string, we'll show it here:
        xeq_opp = g("__x_eq_opp", "")
        if xeq_opp:
            wrap([xeq_opp], indent=12, font="Helvetica", size=9, lh=11, extra_gap=14)

        bold(f"X(design) (far) = {g('X(design) opp (ft)')} ft", indent=12)

        y -= 4
        label("Compute D (far)")
        txt(g("__d_required_eq", ""), indent=12, size=9)
        txt(g("__d_round_eq", ""), indent=12, size=9)
        bold(f"D (far) = {g('D (opp) (ft)')} ft", indent=12)

        y -= 4
        label("Compute C (far)")
        txt(g("__c_eq_opp", ""), indent=12, size=9)
        bold(f"C (far) = {g('C (opp) (ft)')} ft", indent=12)

        # Footer stamp (version + generated time)
        stamp_version()




    # Render pages
    if style == 1:
        draw_summary_page()
    elif style == 2:
        draw_calc_page()
    else:
        draw_summary_page()
        draw_calc_page()

    c.save()


def generate_pdf_calc_sheet(pdf_path: str, data: dict) -> None:
    """Create a formal, four-decimal-place engineering calculation package."""
    try:
        from reportlab.lib import colors
        from reportlab.lib.enums import TA_CENTER, TA_LEFT
        from reportlab.lib.pagesizes import letter
        from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
        from reportlab.lib.units import inch
        from reportlab.platypus import (
            KeepTogether,
            PageBreak,
            Paragraph,
            SimpleDocTemplate,
            Spacer,
            Table,
            TableStyle,
        )
    except Exception as e:
        raise RuntimeError(
            "ReportLab is not available. Install it with:\n"
            "  python -m pip install reportlab\n"
            f"Original error: {e}"
        )

    navy = colors.HexColor("#17365D")
    blue = colors.HexColor("#D9E7F5")
    light_blue = colors.HexColor("#EDF3F8")
    light_gray = colors.HexColor("#F2F3F5")
    medium_gray = colors.HexColor("#B7BEC7")
    dark_gray = colors.HexColor("#3D4650")

    styles = getSampleStyleSheet()
    styles.add(ParagraphStyle(
        name="DocumentTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=17,
        leading=20,
        textColor=navy,
        alignment=TA_LEFT,
        spaceAfter=3,
    ))
    styles.add(ParagraphStyle(
        name="DocumentSubtitle",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=9,
        leading=12,
        textColor=dark_gray,
        spaceAfter=10,
    ))
    styles.add(ParagraphStyle(
        name="SectionHeading",
        parent=styles["Heading2"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=colors.white,
        backColor=navy,
        borderPadding=(5, 7, 5, 7),
        spaceBefore=8,
        spaceAfter=5,
    ))
    styles.add(ParagraphStyle(
        name="Subheading",
        parent=styles["Heading3"],
        fontName="Helvetica-Bold",
        fontSize=10,
        leading=12,
        textColor=navy,
        spaceBefore=5,
        spaceAfter=4,
    ))
    styles.add(ParagraphStyle(
        name="BodySmall",
        parent=styles["BodyText"],
        fontName="Helvetica",
        fontSize=8.5,
        leading=11,
    ))
    styles.add(ParagraphStyle(
        name="Equation",
        parent=styles["BodyText"],
        fontName="Courier",
        fontSize=8,
        leading=11,
        leftIndent=8,
        textColor=dark_gray,
    ))
    styles.add(ParagraphStyle(
        name="ResultValue",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=13,
        leading=15,
        alignment=TA_CENTER,
        textColor=navy,
    ))
    styles.add(ParagraphStyle(
        name="ResultLabel",
        parent=styles["BodyText"],
        fontName="Helvetica-Bold",
        fontSize=8,
        leading=10,
        alignment=TA_CENTER,
        textColor=dark_gray,
    ))
    styles.add(ParagraphStyle(
        name="Note",
        parent=styles["BodyText"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        leading=10,
        textColor=dark_gray,
    ))
    styles.add(ParagraphStyle(
        name="AppendixTitle",
        parent=styles["Title"],
        fontName="Helvetica-Bold",
        fontSize=20,
        leading=24,
        alignment=TA_CENTER,
        textColor=navy,
    ))

    generated = str(data.get("__generated_time", "")).strip()
    version = str(data.get("__app_version", "")).strip()
    doc = SimpleDocTemplate(
        pdf_path,
        pagesize=letter,
        rightMargin=0.55 * inch,
        leftMargin=0.55 * inch,
        topMargin=0.55 * inch,
        bottomMargin=0.52 * inch,
        title=f"{data.get('Project', '')} Guardrail Calculations",
        author="",
        subject="Guardrail length-of-need calculations",
    )

    def footer(canvas, document):
        canvas.saveState()
        page_width, _ = letter
        canvas.setStrokeColor(medium_gray)
        canvas.setLineWidth(0.5)
        canvas.line(doc.leftMargin, 0.38 * inch, page_width - doc.rightMargin, 0.38 * inch)
        canvas.setFont("Helvetica", 7)
        canvas.setFillColor(dark_gray)
        canvas.drawString(doc.leftMargin, 0.23 * inch, f"Guardrail Calculation Package {version}".strip())
        canvas.drawCentredString(page_width / 2, 0.23 * inch, f"Generated {generated}")
        canvas.drawRightString(page_width - doc.rightMargin, 0.23 * inch, f"Page {document.page}")
        canvas.restoreState()

    def p(text, style="BodySmall"):
        return Paragraph(str(text), styles[style])

    def value(key, default=""):
        raw = data.get(key, default)
        return "" if raw is None else str(raw)

    def section(title):
        return Paragraph(title, styles["SectionHeading"])

    def metadata_table():
        rows = [
            [p("<b>Project</b>"), p(value("Project")), p("<b>Job Number</b>"), p(value("Job Number"))],
            [p("<b>Route / Location</b>"), p(value("Route / Location")), p("<b>Calculation Date</b>"), p(value("Calculation Date"))],
            [p("<b>Prepared By</b>"), p(value("Prepared By")), p("<b>Checked By</b>"), p(value("Checked By"))],
        ]
        table = Table(rows, colWidths=[0.95 * inch, 2.35 * inch, 1.08 * inch, 2.0 * inch])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.5, medium_gray),
            ("BACKGROUND", (0, 0), (0, -1), light_gray),
            ("BACKGROUND", (2, 0), (2, -1), light_gray),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        return table

    def key_value_table(items, columns=2):
        rows = []
        if columns == 2:
            for i in range(0, len(items), 2):
                pair = items[i:i + 2]
                row = []
                for label, val in pair:
                    row.extend([p(f"<b>{label}</b>"), p(val)])
                if len(pair) == 1:
                    row.extend([p(""), p("")])
                rows.append(row)
            widths = [1.48 * inch, 1.72 * inch, 1.48 * inch, 1.72 * inch]
        else:
            rows = [[p(f"<b>{label}</b>"), p(val)] for label, val in items]
            widths = [2.4 * inch, 4.0 * inch]
        table = Table(rows, colWidths=widths)
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.4, medium_gray),
            ("BACKGROUND", (0, 0), (0, -1), light_gray),
            ("BACKGROUND", (2, 0), (2, -1), light_gray),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    def output_boxes():
        entries = [
            ("A - Near Side", value("A (near) (ft)")),
            ("B - Near Rail", value("B (near) (ft)")),
            ("C - Opposing Side", value("C (opp) (ft)")),
            ("D - Opposing Rail", value("D (opp) (ft)")),
        ]
        cells = [
            [p(label, "ResultLabel") for label, _ in entries],
            [p(f"{result} ft", "ResultValue") for _, result in entries],
        ]
        table = Table(cells, colWidths=[1.6 * inch] * 4, rowHeights=[0.27 * inch, 0.43 * inch])
        table.setStyle(TableStyle([
            ("SPAN", (0, 0), (0, 0)),
            ("BACKGROUND", (0, 0), (-1, 0), blue),
            ("BACKGROUND", (0, 1), (-1, 1), colors.white),
            ("BOX", (0, 0), (-1, -1), 0.8, navy),
            ("INNERGRID", (0, 0), (-1, -1), 0.5, navy),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("LEFTPADDING", (0, 0), (-1, -1), 4),
            ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ("TOPPADDING", (0, 0), (-1, -1), 4),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return table

    def calculation_block(side_name, x_eq_key, x_min_key, flared_key, rounded_key, design_key, output_rows):
        body = [
            p(side_name, "Subheading"),
            key_value_table([
                ("Minimum X", f"{value(x_min_key)} ft"),
                ("Required Rail Length", f"{value(flared_key)} ft"),
                ("Rounded Rail Length", f"{value(rounded_key)} ft"),
                ("Final Overall Length", f"{value(design_key)} ft"),
            ]),
            Spacer(1, 4),
            p("<b>Length-of-need equation and substitution</b>"),
            p(value(x_eq_key), "Equation"),
            Spacer(1, 4),
        ]
        calc_rows = []
        for label, equation, result in output_rows:
            calc_rows.append([
                p(f"<b>{label}</b>"),
                p(equation, "Equation"),
                p(f"<b>{result} ft</b>"),
            ])
        table = Table(calc_rows, colWidths=[1.25 * inch, 3.8 * inch, 1.35 * inch])
        table.setStyle(TableStyle([
            ("GRID", (0, 0), (-1, -1), 0.45, medium_gray),
            ("BACKGROUND", (0, 0), (0, -1), light_blue),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ("ALIGN", (-1, 0), (-1, -1), "RIGHT"),
            ("LEFTPADDING", (0, 0), (-1, -1), 5),
            ("RIGHTPADDING", (0, 0), (-1, -1), 5),
            ("TOPPADDING", (0, 0), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
        ]))
        body.append(table)
        return KeepTogether(body)

    story = [
        Paragraph("GUARDRAIL LENGTH-OF-NEED CALCULATIONS", styles["DocumentTitle"]),
        Paragraph(
            "Bridge approach guardrail based on MDOT Roadway Design Manual Table 9-6-A and GR-4 dimensions.",
            styles["DocumentSubtitle"],
        ),
        metadata_table(),
        section("DESIGN INPUTS"),
        key_value_table([
            ("Facility", value("Facility")),
            ("Design Speed", f"{value('Design speed (mph)')} mph"),
            ("Design ADT", value("Design ADT")),
            ("Runout Length, LR", f"{value('LR (ft)')} ft"),
            ("Hazard Offset, LA", f"{value('LA (ft)')} ft"),
            ("Near-Side Offset, L2", f"{value('Near-side L2 (ft)')} ft"),
            ("Opposing-Side Offset, L2", f"{value('Opp-side L2 (ft)')} ft"),
            ("Lane Width", f"{value('Lane width (ft)')} ft"),
            ("Transition Length, L1", f"{value('L1 (ft)')}"),
            ("Terminal Section", f"{value('Terminal section (ft)')} ft"),
            ("Flare Rate, a/b", value("Flare rate a/b")),
            ("Guardrail Increment", f"{INCR_GUARDRAIL_FT:.4f} ft"),
        ]),
        section("FINAL DESIGN OUTPUTS"),
        output_boxes(),
        Spacer(1, 5),
        key_value_table([
            ("Near Side Including Gating", f"{value('Near + gating (ft)')} ft"),
            ("Opposing Side Including Gating", f"{value('Opp + gating (ft)')} ft"),
        ]),
        section("SUPPORTING RESULTS"),
        key_value_table([
            ("Near Minimum X", f"{value('X(min) near (ft)')} ft"),
            ("Near Required Rail, B", f"{value('B required (ft)')} ft"),
            ("Opposing Minimum X", f"{value('X(min) opp (ft)')} ft"),
            ("Opposing Required Rail, D", f"{value('D required (ft)')} ft"),
            ("Rounded Rail, B", f"{value('B (near) (ft)')} ft"),
            ("Rounded Rail, D", f"{value('D (opp) (ft)')} ft"),
        ]),
        Spacer(1, 7),
        p(
            "<b>Design basis:</b> MDOT Roadway Design Manual, Table 9-6-A, Barrier Length of Need. "
            "Calculated guardrail lengths are rounded in accordance with the existing 12.5000-foot increment workflow.",
            "Note",
        ),
        Spacer(1, 4),
        p(
            "<b>Engineering disclaimer:</b> This calculation package documents user-entered inputs and computed results. "
            "It is not a sealed or stamped engineering document and must be independently reviewed for project applicability.",
            "Note",
        ),
    ]

    style = int(data.get("__pdf_style", 3))
    if style in (2, 3):
        if style == 3:
            story.append(PageBreak())
        story.extend([
            Paragraph("DETAILED CALCULATIONS", styles["DocumentTitle"]),
            Paragraph(
                f"Project: {value('Project')} &nbsp;&nbsp; | &nbsp;&nbsp; Job Number: {value('Job Number')}",
                styles["DocumentSubtitle"],
            ),
            section("COMMON PARAMETERS"),
            key_value_table([
                ("Design Speed", f"{value('Design speed (mph)')} mph"),
                ("Design ADT", value("Design ADT")),
                ("LA", f"{value('LA (ft)')} ft"),
                ("L1", f"{value('L1 (ft)')}"),
                ("Terminal Section", f"{value('Terminal section (ft)')} ft"),
                ("LR", f"{value('LR (ft)')} ft"),
            ]),
            section("NEAR SIDE - OUTPUTS A AND B"),
            calculation_block(
                "Near-Side Length of Need",
                "__x_eq_near",
                "X(min) near (ft)",
                "Flared portion near (ft)",
                "Flared portion rounded near (ft)",
                "X(design) near (ft)",
                [
                    ("B Required", value("__b_required_eq"), value("B required (ft)")),
                    ("Output B", value("__b_round_eq"), value("B (near) (ft)")),
                    ("Output A", value("__a_eq_near"), value("A (near) (ft)")),
                ],
            ),
            Spacer(1, 8),
            section("OPPOSING SIDE - OUTPUTS C AND D"),
            calculation_block(
                "Opposing-Side Length of Need",
                "__x_eq_opp",
                "X(min) opp (ft)",
                "Flared portion opp (ft)",
                "Flared portion rounded opp (ft)",
                "X(design) opp (ft)",
                [
                    ("D Required", value("__d_required_eq"), value("D required (ft)")),
                    ("Output D", value("__d_round_eq"), value("D (opp) (ft)")),
                    ("Output C", value("__c_eq_opp"), value("C (opp) (ft)")),
                ],
            ),
            Spacer(1, 8),
            p(
                "All displayed calculated lengths are shown to four decimal places. Internal calculation precision and "
                "the established 12.5000-foot increment rounding method are unchanged.",
                "Note",
            ),
        ])

    if style == 2:
        story = story[story.index(next(item for item in story if isinstance(item, Paragraph) and item.getPlainText() == "DETAILED CALCULATIONS")):]

    if data.get("__include_appendix"):
        story.extend([
            PageBreak(),
            Spacer(1, 2.2 * inch),
            Paragraph("APPENDIX A", styles["AppendixTitle"]),
            Spacer(1, 0.15 * inch),
            Paragraph("MDOT ROADWAY DESIGN MANUAL REFERENCE", styles["AppendixTitle"]),
            Spacer(1, 0.35 * inch),
            Paragraph(
                "The following reference pages are reproduced from the MDOT Roadway Design Manual and are included "
                "for calculation traceability.",
                ParagraphStyle(
                    "AppendixBody",
                    parent=styles["BodyText"],
                    fontName="Helvetica",
                    fontSize=10,
                    leading=14,
                    alignment=TA_CENTER,
                    textColor=dark_gray,
                ),
            ),
        ])

    doc.build(story, onFirstPage=footer, onLaterPages=footer)



def main():
    print("\nGuardrail Calculator Starting....")
    print("Bridge Approach Guardrail (MDOT Table 9-6-A) + outputs A/B/C/D per GR-4\n")

    project = input("Project name (optional): ").strip()

    facility = prompt_choice(
        "Facility type:",
        ["two_lane_two_way", "divided_highway"]
    )

    speed = int(prompt_choice(
        "Design speed (mph) (must match MDOT Table 9-6-A):",
        ["30", "35", "40", "45", "50", "55", "60", "65", "70"]
    ))

    adt = prompt_float("Design ADT (total both directions, design year): ")

    la_mode = prompt_choice(
        "How do you want to set LA (distance from edge of traveled way to back of hazard)?",
        ["Help me choose a clear zone from Table 9-2-A (then LA = clear zone)", "I will enter LA directly"]
    )

    if la_mode.startswith("I will enter"):
        LA = prompt_float("LA (ft): ")
        clear_zone_used = None
    else:
        clear_zone_used = choose_clear_zone(speed, adt)
        LA = clear_zone_used
        print(f"Using LA = {LA:.4f} ft based on Table 9-2-A selection.\n")

    # Near-side L2 (edge of traveled way -> barrier face line)
    L2 = prompt_float("Near-side L2 (ft) = offset from edge of traveled way to guardrail (barrier face line): ")

    lane_width = None

    # Opposite-side L2 rule:
    # LA DOES NOT CHANGE, only L2 changes by + one lane width (two-lane, two-way).
    if facility == "two_lane_two_way":
        lane_width = prompt_float("Lane width (ft): ")
        L2_opp = L2 + lane_width
    else:
        mode = prompt_choice(
            "Opposing-side L2 adjustment (divided):",
            ["Enter added distance to opposite traveled-way edge (custom)", "Compute from lanes + median (helper)"]
        )
        if mode.startswith("Enter"):
            add_dist = prompt_float("Added distance to reach opposite traveled-way edge (ft): ")
        else:
            lane_w = prompt_float("Lane width (ft): ")
            lanes_this = prompt_float("Number of lanes in your direction: ")
            lanes_opp = prompt_float("Number of lanes in opposing direction: ")
            median_w = prompt_float("Median width between traveled ways (ft): ")
            add_dist = lane_w * (lanes_this + lanes_opp) + median_w
            print(f"Computed added distance = {add_dist:.4f} ft")
        L2_opp = L2 + add_dist

    # L1 option
    l1_mode = prompt_choice(
        f"L1 option (Example 9-6-1 uses L1 = 18'-1.75\" = {DEFAULT_L1_FT:.4f} ft):",
        ["Use standard L1", "Enter custom L1"]
    )
    L1 = DEFAULT_L1_FT if l1_mode.startswith("Use") else prompt_float("Enter L1 (ft): ")

    # Terminal section option
    term_mode = prompt_choice(
        f"Terminal section length to use for B/D (default = {DEFAULT_TERMINAL_SECTION_FT:.1f} ft):",
        ["Use 25.0 ft", "Enter custom"]
    )
    terminal_section = DEFAULT_TERMINAL_SECTION_FT if term_mode.startswith("Use") else prompt_float("Enter terminal section length (ft): ")

    # Flare rate (a/b)
    flare_pick = prompt_choice(
        "Flare rate a/b:",
        ["30", "28", "26", "24", "21", "18", "16", "15", "13", "0 (non-flared)"]
    )
    a_over_b = 0.0 if flare_pick.startswith("0") else float(flare_pick)
    results = compute_guardrail_outputs(speed, adt, LA, L2, L2_opp, L1, terminal_section, a_over_b)

    # -------------------------
    # PRINT
    # -------------------------
    print("\n--- Inputs ---")
    print(f"Project: {project or '(blank)'}")
    print(f"Facility: {facility}")
    print(f"Design speed: {speed} mph")
    print(f"Design ADT: {adt:.0f}")
    if clear_zone_used is not None:
        print(f"Clear zone selected (Table 9-2-A): {clear_zone_used:.4f} ft (used as LA)")
    print(f"LA: {LA:.4f} ft")
    print(f"Near-side L2: {L2:.4f} ft")
    print(f"Opp-side L2 (near L2 + crossing): {L2_opp:.4f} ft")
    print(f"L1: {L1:.4f} ft  ({fmt_ft_in(L1)})")
    print(f"Terminal section for B/D: {terminal_section:.4f} ft")
    print(f"Flare rate a/b: {a_over_b:.0f}/1" if a_over_b != 0 else "Flare rate: non-flared (a/b = 0)")
    print(f"LR (Table 9-6-A): {results['LR']:.0f} ft")

    print("\n--- Near-side calculation ---")
    print(f"X(min) before rounding: {results['X_min_near']:.4f} ft")
    print(f"B required = X(min) - L1 - terminal: {results['B_required']:.4f} ft")
    print(f"B after 12.5000-ft minimum and increment rounding: {results['B']:.4f} ft")
    print(f"A = B + L1 + terminal: {results['A']:.4f} ft")

    print("\n--- Opposing-side calculation (LA same, L2 increased) ---")
    print(f"X(min) before rounding: {results['X_min_opp']:.4f} ft")
    print(f"D required = X(min) - L1 - terminal: {results['D_required']:.4f} ft")
    print(f"D after 12.5000-ft minimum and increment rounding: {results['D']:.4f} ft")
    print(f"C = D + L1 + terminal: {results['C']:.4f} ft")

    print("\n=== GR-4 / GR-4a Outputs ===")
    print(f"A (near) = B + L1 + terminal: {results['A']:.4f} ft")
    print(f"B (near) = rounded rail length: {results['B']:.4f} ft")
    print(f"C (opp)  = D + L1 + terminal: {results['C']:.4f} ft")
    print(f"D (opp)  = rounded rail length: {results['D']:.4f} ft")

    print("\n(Extra) If you want the MDOT example add gating portion total:")
    print(f"Near total with +{DEFAULT_GATING_FT} ft gating: {results['A_plus_gating']:.4f} ft")
    print(f"Opp  total with +{DEFAULT_GATING_FT} ft gating: {results['C_plus_gating']:.4f} ft")

    # =========================
    # PDF OUTPUT (FIXED)
    # =========================
    make_pdf = input("\nGenerate PDF calc sheet now? (y/n): ").strip().lower()
    if make_pdf in ("y", "yes"):
        print("\nWhere do you want to save the PDF?")
        print("Examples:")
        print(r"  C:\Users\colew\Desktop")
        print(r"  C:\Users\colew\Documents\Guardrail Calcs")
        out_folder = input("Folder path (Enter = current folder): ").strip()

        default_name = _safe_filename(f"{project}_guardrail_calc_sheet" if project else "guardrail_calc_sheet")
        out_name = input(f"PDF filename (Enter for '{default_name}'): ").strip()
        if not out_name:
            out_name = default_name
        out_name = _safe_filename(out_name)

        full_pdf_path = _join_path(out_folder, out_name)

        pdf_style = prompt_choice(
            "PDF style:",
            ["1 (summary)", "2 (calc boxes only)", "3 (summary + example calc boxes)"]
        )
        pdf_style_num = int(pdf_style.split()[0])
        pdf_data = build_pdf_data(
            project=project,
            facility=facility,
            speed=speed,
            adt=adt,
            LA=LA,
            L2=L2,
            L2_opp=L2_opp,
            lane_width=lane_width,
            L1=L1,
            terminal_section=terminal_section,
            a_over_b=a_over_b,
            pdf_style_num=pdf_style_num,
            results=results,
            generated_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )

        try:
            appendix_used = write_calc_pdf(full_pdf_path, pdf_data, auto_open=False)
            if appendix_used:
                print(f"\nPDF written (manual appended): {full_pdf_path}")
            else:
                print(f"\nPDF written (no appendix found; calc sheet only): {full_pdf_path}")
        except Exception as e:
            print(f"\nPDF generation failed: {e}")


def _ui_main_legacy():
    import tkinter as tk
    from tkinter import ttk, filedialog, messagebox

    def set_enabled(widget, enabled: bool):
        try:
            widget.configure(state=("normal" if enabled else "disabled"))
        except Exception:
            pass

    def pick_pdf_path():
        default_name = _safe_filename(f"{project_var.get().strip()}_guardrail_calc_sheet" if project_var.get().strip() else "guardrail_calc_sheet")
        path = filedialog.asksaveasfilename(
            title="Save PDF calc sheet as...",
            defaultextension=".pdf",
            initialfile=default_name,
            filetypes=[("PDF files", "*.pdf"), ("All files", "*.*")]
        )
        if path:
            pdf_path_var.set(path)

    def recompute_LA_fields():
        use_clearzone = (la_mode_var.get() == "clearzone")
        for w in (slope_combo, cz_pick_combo, cz_custom_entry):
            set_enabled(w, use_clearzone)
        set_enabled(LA_entry, not use_clearzone)

    def recompute_facility_fields():
        is_two_lane = (facility_var.get() == "two_lane_two_way")
        # two-lane uses lane width; divided uses "added distance" (or helper)
        set_enabled(lane_width_entry, is_two_lane)
        set_enabled(add_dist_entry, not is_two_lane)
        # Helper fields only for divided
        for w in (div_lane_w_entry, lanes_this_entry, lanes_opp_entry, median_w_entry, helper_btn):
            set_enabled(w, not is_two_lane)

    def compute_clear_zone_value(speed: float, adt: float) -> float:
        # UI version of choose_clear_zone() without console prompts
        group_s = speed_group_clearzone(speed)
        group_a = adt_group_clearzone(adt)
        slope = slope_var.get()
        if slope not in ("6:1_or_flatter", "5:1_to_4:1"):
            raise ValueError("Pick a side slope category for clear zone (Table 9-2-A).")

        mn, mx = TABLE_9_2_A[group_s][group_a][slope]
        pick = cz_pick_var.get()
        if pick == "min":
            return float(mn)
        if pick == "mid":
            return float((mn + mx) / 2.0)
        if pick == "max":
            return float(mx)
        if pick == "custom":
            return float(_first_number(cz_custom_var.get()))
        raise ValueError("Pick min/mid/max/custom for clear zone selection.")

    def fill_added_distance_helper():
        try:
            lane_w = float(_first_number(div_lane_w_var.get()))
            lanes_this = float(_first_number(lanes_this_var.get()))
            lanes_opp = float(_first_number(lanes_opp_var.get()))
            median_w = float(_first_number(median_w_var.get()))
            add_dist = lane_w * (lanes_this + lanes_opp) + median_w
            add_dist_var.set(f"{add_dist:.4f}")
        except Exception as e:
            messagebox.showerror("Helper error", f"Could not compute added distance.\n\n{e}")

    def run_calc_and_pdf():
        try:
            project = project_var.get().strip()
            facility = facility_var.get().strip()
            if facility not in ("two_lane_two_way", "divided_highway"):
                raise ValueError("Facility must be 'two_lane_two_way' or 'divided_highway'.")

            speed = int(speed_var.get())
            adt = float(_first_number(adt_var.get()))

            # LA
            clear_zone_used = None
            if la_mode_var.get() == "direct":
                LA = float(_first_number(LA_var.get()))
            else:
                clear_zone_used = compute_clear_zone_value(speed, adt)
                LA = float(clear_zone_used)

            # L2 near
            L2 = float(_first_number(L2_var.get()))

            # Opposing L2
            lane_width = None
            if facility == "two_lane_two_way":
                lane_width = float(_first_number(lane_width_var.get()))
                L2_opp = L2 + lane_width
            else:
                add_dist = float(_first_number(add_dist_var.get()))
                L2_opp = L2 + add_dist

            # L1
            if l1_mode_var.get() == "standard":
                L1 = float(DEFAULT_L1_FT)
            else:
                L1 = float(_first_number(L1_custom_var.get()))

            # terminal section
            if term_mode_var.get() == "default":
                terminal_section = float(DEFAULT_TERMINAL_SECTION_FT)
            else:
                terminal_section = float(_first_number(term_custom_var.get()))

            # flare rate a/b
            flare_pick = flare_var.get().strip()
            a_over_b = 0.0 if flare_pick.startswith("0") else float(flare_pick)

            # ---- calcs (shared) ----
            results_dict = compute_guardrail_outputs(speed, adt, LA, L2, L2_opp, L1, terminal_section, a_over_b)

            # Build pdf_data using shared helper
            pdf_style_num = int(pdf_style_var.get())
            pdf_generated_time = datetime.now().strftime("%Y-%m-%d %H:%M")
            pdf_data = build_pdf_data(
                project=project,
                facility=facility,
                speed=speed,
                adt=adt,
                LA=LA,
                L2=L2,
                L2_opp=L2_opp,
                lane_width=lane_width,
                L1=L1,
                terminal_section=terminal_section,
                a_over_b=a_over_b,
                pdf_style_num=pdf_style_num,
                results=results_dict,
                generated_time=pdf_generated_time,
            )

            # Show results in UI
            results.delete("1.0", "end")
            results.insert("end", f"LR (Table 9-6-A): {results_dict['LR']:.0f} ft\n")
            if clear_zone_used is not None:
                results.insert("end", f"Clear zone used (Table 9-2-A): {clear_zone_used:.4f} ft (LA)\n")
            results.insert("end", "\n--- Near side ---\n")
            results.insert("end", f"X(min): {results_dict['X_min_near']:.4f} ft\n")
            results.insert("end", f"X(design): {results_dict['X_design_near']:.4f} ft\n")
            results.insert("end", f"A: {results_dict['A']:.4f} ft\nB: {results_dict['B']:.4f} ft\n")
            results.insert("end", "\n--- Opposing side ---\n")
            results.insert("end", f"X(min): {results_dict['X_min_opp']:.4f} ft\n")
            results.insert("end", f"X(design): {results_dict['X_design_opp']:.4f} ft\n")
            results.insert("end", f"C: {results_dict['C']:.4f} ft\nD: {results_dict['D']:.4f} ft\n")

            # Write PDF if path given
            out_path = pdf_path_var.get().strip()
            if not out_path:
                messagebox.showinfo("Done (no PDF)", "Calcs complete. Pick a PDF path if you want the calc sheet generated.")
                return

            appendix_used = write_calc_pdf(out_path, pdf_data, auto_open=auto_open_var.get())

            msg = f"PDF written:\n{out_path}"
            if not appendix_used:
                msg += "\n(Appendix 'gr manual.pdf' not found; calc sheet only.)"

            messagebox.showinfo("Success", msg)

        except Exception as e:
            messagebox.showerror("Error", str(e))

    # ---------------- UI Layout ----------------
    root = tk.Tk()
    root.title("MDOT Guardrail Calculator (GR-4 Outputs + PDF)")
    root.geometry("900x820")

    frm = ttk.Frame(root, padding=12)
    frm.pack(fill="both", expand=True)

    # Vars
    project_var = tk.StringVar(value="")
    facility_var = tk.StringVar(value="two_lane_two_way")
    speed_var = tk.StringVar(value="60")
    adt_var = tk.StringVar(value="6000")

    la_mode_var = tk.StringVar(value="clearzone")   # direct | clearzone
    LA_var = tk.StringVar(value="30")
    slope_var = tk.StringVar(value="6:1_or_flatter")
    cz_pick_var = tk.StringVar(value="mid")
    cz_custom_var = tk.StringVar(value="")

    L2_var = tk.StringVar(value="10")
    lane_width_var = tk.StringVar(value="12")
    add_dist_var = tk.StringVar(value="")

    div_lane_w_var = tk.StringVar(value="12")
    lanes_this_var = tk.StringVar(value="2")
    lanes_opp_var = tk.StringVar(value="2")
    median_w_var = tk.StringVar(value="40")

    l1_mode_var = tk.StringVar(value="standard")  # standard | custom
    L1_custom_var = tk.StringVar(value=f"{DEFAULT_L1_FT:.4f}")

    term_mode_var = tk.StringVar(value="default") # default | custom
    term_custom_var = tk.StringVar(value=f"{DEFAULT_TERMINAL_SECTION_FT:.4f}")

    flare_var = tk.StringVar(value="30")
    pdf_style_var = tk.StringVar(value="3")
    pdf_path_var = tk.StringVar(value="")
    auto_open_var = tk.BooleanVar(value=True)


    # Grid helper
    def row(label, widget, r):
        ttk.Label(frm, text=label).grid(row=r, column=0, sticky="w", pady=3)
        widget.grid(row=r, column=1, sticky="ew", pady=3)
        return r + 1

    frm.columnconfigure(1, weight=1)

    r = 0
    ttk.Label(frm, text="Inputs", font=("Segoe UI", 12, "bold")).grid(row=r, column=0, sticky="w", pady=(0,6)); r += 1

    r = row("Project (optional)", ttk.Entry(frm, textvariable=project_var), r)

    facility_combo = ttk.Combobox(frm, textvariable=facility_var, values=["two_lane_two_way", "divided_highway"], state="readonly")
    facility_combo.bind("<<ComboboxSelected>>", lambda e: recompute_facility_fields())
    r = row("Facility", facility_combo, r)

    speed_combo = ttk.Combobox(frm, textvariable=speed_var, values=["30","35","40","45","50","55","60","65","70"], state="readonly")
    r = row("Design speed (mph)", speed_combo, r)

    r = row("Design ADT", ttk.Entry(frm, textvariable=adt_var), r)

    la_mode_combo = ttk.Combobox(frm, textvariable=la_mode_var, values=["direct", "clearzone"], state="readonly")
    la_mode_combo.bind("<<ComboboxSelected>>", lambda e: recompute_LA_fields())
    r = row("LA mode", la_mode_combo, r)

    LA_entry = ttk.Entry(frm, textvariable=LA_var)
    r = row("LA (ft) [direct only]", LA_entry, r)

    slope_combo = ttk.Combobox(frm, textvariable=slope_var, values=["6:1_or_flatter", "5:1_to_4:1"], state="readonly")
    r = row("Clear zone slope [clearzone only]", slope_combo, r)

    cz_pick_combo = ttk.Combobox(frm, textvariable=cz_pick_var, values=["min","mid","max","custom"], state="readonly")
    r = row("Clear zone pick [clearzone only]", cz_pick_combo, r)

    cz_custom_entry = ttk.Entry(frm, textvariable=cz_custom_var)
    r = row("Clear zone custom (ft) [if custom]", cz_custom_entry, r)

    r = row("Near-side L2 (ft)", ttk.Entry(frm, textvariable=L2_var), r)

    lane_width_entry = ttk.Entry(frm, textvariable=lane_width_var)
    r = row("Lane width (ft) [two-lane only]", lane_width_entry, r)

    add_dist_entry = ttk.Entry(frm, textvariable=add_dist_var)
    r = row("Added distance to opposite ETW (ft) [divided]", add_dist_entry, r)

    # Divided helper row
    helper_row = ttk.Frame(frm)
    helper_row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(4,8))
    ttk.Label(helper_row, text="Divided helper:").pack(side="left")
    div_lane_w_entry = ttk.Entry(helper_row, width=6, textvariable=div_lane_w_var); div_lane_w_entry.pack(side="left", padx=6)
    ttk.Label(helper_row, text="lane w").pack(side="left")
    lanes_this_entry = ttk.Entry(helper_row, width=4, textvariable=lanes_this_var); lanes_this_entry.pack(side="left", padx=6)
    ttk.Label(helper_row, text="lanes this").pack(side="left")
    lanes_opp_entry = ttk.Entry(helper_row, width=4, textvariable=lanes_opp_var); lanes_opp_entry.pack(side="left", padx=6)
    ttk.Label(helper_row, text="lanes opp").pack(side="left")
    median_w_entry = ttk.Entry(helper_row, width=6, textvariable=median_w_var); median_w_entry.pack(side="left", padx=6)
    ttk.Label(helper_row, text="median").pack(side="left")
    helper_btn = ttk.Button(helper_row, text="Compute added distance (+)", command=fill_added_distance_helper)
    helper_btn.pack(side="left", padx=10)
    r += 1

    l1_mode_combo = ttk.Combobox(frm, textvariable=l1_mode_var, values=["standard","custom"], state="readonly")
    r = row("L1 mode", l1_mode_combo, r)
    r = row(f"L1 custom (ft) (standard={DEFAULT_L1_FT:.4f})", ttk.Entry(frm, textvariable=L1_custom_var), r)

    term_mode_combo = ttk.Combobox(frm, textvariable=term_mode_var, values=["default","custom"], state="readonly")
    r = row("Terminal section mode", term_mode_combo, r)
    r = row(f"Terminal custom (ft) (default={DEFAULT_TERMINAL_SECTION_FT:.1f})", ttk.Entry(frm, textvariable=term_custom_var), r)

    flare_combo = ttk.Combobox(frm, textvariable=flare_var, values=["30","28","26","24","21","18","16","15","13","0 (non-flared)"], state="readonly")
    r = row("Flare rate a/b", flare_combo, r)

    ttk.Separator(frm).grid(row=r, column=0, columnspan=2, sticky="ew", pady=10); r += 1
    ttk.Label(frm, text="PDF output", font=("Segoe UI", 12, "bold")).grid(row=r, column=0, sticky="w", pady=(0,6)); r += 1

    pdf_style_combo = ttk.Combobox(frm, textvariable=pdf_style_var, values=["1","2","3"], state="readonly")
    r = row("PDF style (1=summary, 2=calc boxes, 3=summary+calc)", pdf_style_combo, r)

    path_row = ttk.Frame(frm)
    path_row.grid(row=r, column=0, columnspan=2, sticky="ew")
    path_row.columnconfigure(0, weight=1)
    ttk.Entry(path_row, textvariable=pdf_path_var).grid(row=0, column=0, sticky="ew")
    ttk.Button(path_row, text="Choose...", command=pick_pdf_path).grid(row=0, column=1, padx=8)
    r += 1

    ttk.Checkbutton(
        frm,
        text="Auto-open PDF after generating",
        variable=auto_open_var
    ).grid(row=r, column=0, columnspan=2, sticky="w", pady=(4, 8))

    r += 1


    ttk.Separator(frm).grid(row=r, column=0, columnspan=2, sticky="ew", pady=10); r += 1

    # --- Buttons row (two buttons side-by-side) ---
    btn_row = ttk.Frame(frm)
    btn_row.grid(row=r, column=0, columnspan=2, sticky="ew", pady=(0, 6))
    btn_row.columnconfigure(0, weight=1)
    btn_row.columnconfigure(1, weight=1)

    btn_calc = ttk.Button(btn_row, text="Calculate", command=run_calc_and_pdf)
    btn_calc.grid(row=0, column=0, sticky="ew", padx=(0, 6))

    btn_pdf = ttk.Button(btn_row, text="Generate PDF", command=run_calc_and_pdf)
    btn_pdf.grid(row=0, column=1, sticky="ew", padx=(6, 0))

    r += 1



    results = tk.Text(frm, height=12)
    results.grid(row=r, column=0, columnspan=2, sticky="nsew", pady=(10,0))
    frm.rowconfigure(r, weight=1)

    # Init enabled states
    recompute_LA_fields()
    recompute_facility_fields()

    root.mainloop()


def ui_main():
    import tkinter as tk
    from tkinter import filedialog, messagebox, ttk

    FACILITIES = {
        "Two-Lane, Two-Way Roadway": "two_lane_two_way",
        "Divided Highway": "divided_highway",
    }
    LA_MODES = {
        "Enter Hazard Offset Directly": "direct",
        "Select from Clear-Zone Table": "clearzone",
    }
    SLOPES = {
        "6:1 or Flatter": "6:1_or_flatter",
        "5:1 to 4:1": "5:1_to_4:1",
    }
    CLEAR_ZONE_PICKS = {
        "Minimum": "min",
        "Midpoint": "mid",
        "Maximum": "max",
        "Custom": "custom",
    }
    PDF_STYLES = {
        "Complete Calculation Package": 3,
        "Summary Only": 1,
        "Detailed Calculations Only": 2,
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
        ["30", "35", "40", "45", "50", "55", "60", "65", "70"],
    )
    add_field(roadway_frame, 2, "Design ADT", adt_var)
    add_field(roadway_frame, 3, "Near-Side Offset, L2 (ft)", L2_var)
    lane_width_entry = add_field(roadway_frame, 4, "Lane Width (ft)", lane_width_var)
    add_dist_entry = add_field(roadway_frame, 5, "Added Distance to Opposing ETW (ft)", add_dist_var)

    helper = ttk.LabelFrame(roadway_frame, text="Divided Highway Distance Helper", padding=8)
    helper.grid(row=6, column=0, columnspan=2, sticky="ew", pady=(8, 0))
    helper_widgets = []
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

    def compute_added_distance():
        try:
            lane_w = float(_first_number(div_lane_w_var.get()))
            lanes_this = float(_first_number(lanes_this_var.get()))
            lanes_opp = float(_first_number(lanes_opp_var.get()))
            median_w = float(_first_number(median_w_var.get()))
            add_dist_var.set(f"{lane_w * (lanes_this + lanes_opp) + median_w:.4f}")
        except Exception as e:
            messagebox.showerror("Distance Helper", f"Could not compute the added distance.\n\n{e}")

    helper_button = ttk.Button(helper, text="Use Calculated Distance", command=compute_added_distance)
    helper_button.grid(row=2, column=0, columnspan=4, sticky="ew", padx=3, pady=(3, 0))
    helper_widgets.append(helper_button)

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
        ["30:1", "28:1", "26:1", "24:1", "21:1", "18:1", "16:1", "15:1", "13:1", "Non-Flared"],
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
        except Exception:
            clear_zone_used_var.set("AUTOMATIC CLEAR ZONE:  Enter valid values to determine LA")

    for variable in (speed_var, adt_var, slope_var, cz_pick_var, cz_custom_var, la_mode_var):
        variable.trace_add("write", refresh_clear_zone_display)

    def calculate_model():
        facility = FACILITIES[facility_var.get()]
        speed = int(speed_var.get())
        adt = float(_first_number(adt_var.get()))
        if adt < 0:
            raise ValueError("Design ADT cannot be negative.")

        if LA_MODES[la_mode_var.get()] == "direct":
            LA = float(_first_number(LA_var.get()))
        else:
            LA = compute_clear_zone(speed, adt)
            clear_zone_used_var.set(f"AUTOMATIC CLEAR ZONE:  LA USED = {LA:.4f} FT")
        if LA <= 0:
            raise ValueError("Hazard offset LA must be greater than zero.")

        L2 = float(_first_number(L2_var.get()))
        if L2 < 0:
            raise ValueError("Near-side offset L2 cannot be negative.")

        lane_width = None
        if facility == "two_lane_two_way":
            lane_width = float(_first_number(lane_width_var.get()))
            if lane_width <= 0:
                raise ValueError("Lane width must be greater than zero.")
            L2_opp = L2 + lane_width
        else:
            added_distance = float(_first_number(add_dist_var.get()))
            if added_distance < 0:
                raise ValueError("Added distance cannot be negative.")
            L2_opp = L2 + added_distance

        L1 = DEFAULT_L1_FT if l1_mode_var.get() == "Standard" else float(_first_number(L1_custom_var.get()))
        terminal = (
            DEFAULT_TERMINAL_SECTION_FT
            if term_mode_var.get() == "Default"
            else float(_first_number(term_custom_var.get()))
        )
        if L1 < 0 or terminal < 0:
            raise ValueError("L1 and terminal section lengths cannot be negative.")

        flare = flare_var.get()
        a_over_b = 0.0 if flare == "Non-Flared" else float(flare.split(":")[0])
        results = compute_guardrail_outputs(speed, adt, LA, L2, L2_opp, L1, terminal, a_over_b)
        pdf_data = build_pdf_data(
            project=project_var.get().strip(),
            route_location=route_var.get().strip(),
            job_number=job_var.get().strip(),
            prepared_by=prepared_var.get().strip(),
            checked_by=checked_var.get().strip(),
            calculation_date=date_var.get().strip(),
            facility=facility,
            speed=speed,
            adt=adt,
            LA=LA,
            L2=L2,
            L2_opp=L2_opp,
            lane_width=lane_width,
            L1=L1,
            terminal_section=terminal,
            a_over_b=a_over_b,
            pdf_style_num=PDF_STYLES[pdf_style_var.get()],
            results=results,
            generated_time=datetime.now().strftime("%Y-%m-%d %H:%M"),
        )
        return results, pdf_data

    def show_results(results):
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
            results, _ = calculate_model()
            show_results(results)
            status_var.set("Results updated automatically.")
        except Exception as exc:
            clear_results()
            status_var.set(f"Waiting for valid calculation inputs: {exc}")

    def schedule_auto_calculation(*_args):
        if auto_calculate_job["id"] is not None:
            root.after_cancel(auto_calculate_job["id"])
        auto_calculate_job["id"] = root.after(350, run_auto_calculation)

    def calculate_action():
        try:
            results, _ = calculate_model()
            show_results(results)
            status_var.set("Calculation complete. No PDF was generated.")
        except Exception as e:
            status_var.set("Calculation failed.")
            messagebox.showerror("Calculation Error", str(e))

    def generate_pdf_action():
        try:
            results, pdf_data = calculate_model()
            show_results(results)
            out_path = pdf_path_var.get().strip()
            if not out_path:
                out_path = pick_pdf_path()
            if not out_path:
                status_var.set("PDF generation cancelled.")
                return
            appendix_used = write_calc_pdf(
                out_path,
                pdf_data,
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
            status_var.set("PDF generation failed.")
            messagebox.showerror("PDF Generation Error", str(e))

    def generate_dxf_action():
        try:
            results, pdf_data = calculate_model()
            show_results(results)
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
            landxml_entry = ttk.Entry(body, textvariable=landxml_path_var, width=42)
            landxml_entry.grid(row=4, column=1, sticky="ew", pady=4)

            def browse_landxml():
                path = filedialog.askopenfilename(parent=dialog, title="Select LandXML", filetypes=[("LandXML", "*.xml"), ("XML", "*.xml")])
                if not path:
                    return
                try:
                    alignments = guardrail_landxml.load_alignments(path)
                except Exception as exc:
                    messagebox.showerror("LandXML Error", str(exc), parent=dialog)
                    return
                loaded_alignments.clear()
                for alignment in alignments:
                    regions = " | ".join(alignment.civil_region_labels())
                    label = f"{alignment.name}  ({regions})"
                    loaded_alignments[label] = alignment
                landxml_path_var.set(path)
                alignment_combo.configure(values=list(loaded_alignments))
                alignment_var.set(next(iter(loaded_alignments)))

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
                layout_combo.configure(state=("readonly" if FACILITIES[facility_var.get()] == "divided_highway" else "disabled"))
            mode_var.trace_add("write", update_dxf_dialog)

            def accept_dialog():
                try:
                    if mode_var.get() == "standalone":
                        if float(_first_number(bridge_length_var.get())) <= 0:
                            raise ValueError("Standalone bridge length must be greater than zero.")
                    else:
                        if alignment_var.get() not in loaded_alignments:
                            raise ValueError("Select a valid LandXML alignment.")
                        selected_alignment = loaded_alignments[alignment_var.get()]
                        accepted["bridge_start"] = selected_alignment.civil_to_internal(bridge_start_var.get())
                        accepted["bridge_end"] = selected_alignment.civil_to_internal(bridge_end_var.get())
                        if accepted["bridge_end"] <= accepted["bridge_start"]:
                            raise ValueError("Bridge end station must be greater than bridge start station.")
                    accepted["value"] = True
                    dialog.destroy()
                except Exception as exc:
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

            facility = FACILITIES[facility_var.get()]
            L2 = float(_first_number(L2_var.get()))
            if LA_MODES[la_mode_var.get()] == "direct":
                LA = float(_first_number(LA_var.get()))
            else:
                LA = compute_clear_zone(int(speed_var.get()), float(_first_number(adt_var.get())))
            L1 = DEFAULT_L1_FT if l1_mode_var.get() == "Standard" else float(_first_number(L1_custom_var.get()))
            terminal = DEFAULT_TERMINAL_SECTION_FT if term_mode_var.get() == "Default" else float(_first_number(term_custom_var.get()))
            flare = flare_var.get()
            flare_rate = 0.0 if flare == "Non-Flared" else float(flare.split(":")[0])
            lane_width = float(_first_number(lane_width_var.get() if facility == "two_lane_two_way" else div_lane_w_var.get()))
            lanes_this = 1 if facility == "two_lane_two_way" else int(float(_first_number(lanes_this_var.get())))
            lanes_opposing = 1 if facility == "two_lane_two_way" else int(float(_first_number(lanes_opp_var.get())))
            median_width = 0.0 if facility == "two_lane_two_way" else float(_first_number(median_w_var.get()))
            required = (
                max(results["A"], results["C"] if facility == "two_lane_two_way" else results["A"])
                + guardrail_dxf.GATING_LENGTH
                + guardrail_dxf.SHOULDER_TRANSITION_LENGTH
                + guardrail_dxf.NORMAL_SHOULDER_EXTENSION
            )
            if mode_var.get() == "standalone":
                bridge_start = required
                bridge_end = bridge_start + float(_first_number(bridge_length_var.get()))
                alignment = guardrail_dxf.LineAlignment(0.0, bridge_end + required)
                insunits = 2
            else:
                bridge_start = accepted["bridge_start"]
                bridge_end = accepted["bridge_end"]
                alignment = loaded_alignments[alignment_var.get()]
                unit_key = "".join(alignment.linear_unit.lower().split())
                insunits = 21 if "ussurveyfoot" in unit_key or "usfoot" in unit_key else 2
            drawing_model = guardrail_dxf.DrawingModel(
                facility=facility, bridge_start=bridge_start, bridge_end=bridge_end, alignment=alignment,
                A=results["A"], B=results["B"], C=results["C"], D=results["D"], L1=L1,
                terminal=terminal, L2=L2, LA=LA, lane_width=lane_width, lanes_this=lanes_this,
                lanes_opposing=lanes_opposing, median_width=median_width, flare_rate=flare_rate,
                divided_layout="inside" if divided_layout_var.get().startswith("Inside") else "outside",
                project=project_var.get().strip(), route=route_var.get().strip(),
                insunits=insunits,
            )
            default_name = _safe_filename(
                f"{project_var.get().strip()}_guardrail_plan" if project_var.get().strip() else "guardrail_plan"
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



if __name__ == "__main__":
    ui_main()
    
