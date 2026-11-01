"""ReportLab layout only; no widget reads or engineering calculations."""

from xml.sax.saxutils import escape
from guardrail_design import INCR_GUARDRAIL_FT
from guardrail_models import ReportModel
from guardrail_report import report_payload, validate_pdf_numbers

def generate_pdf_calc_sheet(pdf_path: str, data: dict) -> None:
    """Create a formal, four-decimal-place engineering calculation package."""
    validate_pdf_numbers(data)
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
    except ImportError as e:
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
        return "" if raw is None else escape(str(raw))

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


def render_report(pdf_path, report: ReportModel) -> None:
    generate_pdf_calc_sheet(pdf_path, report_payload(report))
