"""Atomic PDF generation and native-page appendix merging."""

import os
import tempfile
from io import BytesIO
from pypdf import PdfReader, PdfWriter
from guardrail_models import ReportModel
from guardrail_pdf import generate_pdf_calc_sheet
from guardrail_report import report_payload
from guardrail_resources import resource_path

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
    *, renderer=None, merger=None,
) -> bool:
    """
    Render the calc sheet, append available embedded references, and optionally auto-open.
    Returns True when every expected appendix document was appended.
    """
    renderer = renderer or generate_pdf_calc_sheet
    merger = merger or merge_with_appendices
    out_path = os.path.abspath(out_path)
    expected_appendices = appendix_manifest(pdf_data)
    available_appendices = [item for item in expected_appendices if os.path.exists(item[2])]
    appendices_complete = bool(include_appendix and len(available_appendices) == len(expected_appendices))

    fd, tmp_pdf = tempfile.mkstemp(prefix=".guardrail-", suffix=".pdf", dir=os.path.dirname(out_path))
    os.close(fd)  # Close before ReportLab opens the file, including on Windows.
    temporary_paths = [tmp_pdf]
    try:
        render_data = dict(pdf_data)
        render_data["__include_appendix"] = False
        renderer(tmp_pdf, render_data)

        if include_appendix and available_appendices:
            fd, completed_pdf = tempfile.mkstemp(
                prefix=".guardrail-", suffix=".pdf", dir=os.path.dirname(out_path),
            )
            os.close(fd)
            temporary_paths.append(completed_pdf)
            merger(tmp_pdf, available_appendices, completed_pdf)
        else:
            completed_pdf = tmp_pdf
        os.replace(completed_pdf, out_path)

        if auto_open:
            try:
                os.startfile(out_path)
            except Exception as e:
                print(f"Could not auto-open PDF: {e}")

        return appendices_complete
    finally:
        for path in temporary_paths:
            try:
                if os.path.exists(path):
                    os.remove(path)
            except OSError:
                pass


def write_report(out_path: str, report: ReportModel, auto_open: bool = False,
                 include_appendix: bool = True) -> bool:
    return write_calc_pdf(out_path, report_payload(report), auto_open, include_appendix)
