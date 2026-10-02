"""Report model formatting; engineering values come from the calculation snapshot."""

import re
from datetime import datetime
from typing import Optional
from guardrail_design import APP_VERSION
from guardrail_models import ReportModel
from guardrail_parsing import parse_number as _first_number
from guardrail_presentation import fmt_ft_in
import guardrail_validation as validation
from guardrail_validation import require_finite as _require_finite

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
    validation.calculation_inputs(speed, adt, LA, L2, L2_opp, L1, terminal_section, a_over_b)
    if facility not in {"two_lane_two_way", "divided_highway"}:
        raise ValueError("Invalid facility type.")
    if lane_width is not None:
        validation.require_positive(lane_width=lane_width)
    _require_finite(**results)
    validation.require_nonnegative(**{key: results[key] for key in (
        "LR", "A", "B", "C", "D", "A_plus_gating", "C_plus_gating",
        "flared_near_rounded", "flared_opp_rounded", "X_design_near", "X_design_opp",
    )})
    validation.installation_totals(results["A"], results["B"], results["C"], results["D"], L1, terminal_section)
    generated_time = generated_time or datetime.now().strftime("%Y-%m-%d %H:%M")
    calculation_date = calculation_date or datetime.now().strftime("%Y-%m-%d")
    b_over_a = results["b_over_a"] if "b_over_a" in results else (0.0 if a_over_b == 0 else 1.0 / a_over_b)
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


def validate_pdf_numbers(data: dict) -> None:
    """Validate display numeric fields, including documented L1/flare formatting."""
    signed_fields = {"X(min) near (ft)", "X(min) opp (ft)", "B required (ft)", "D required (ft)",
                     "Flared portion near (ft)", "Flared portion opp (ft)"}
    positive_fields = {"LA (ft)", "Lane width (ft)", "Design speed (mph)"}
    numbers = {}
    for field, text in data.items():
        if not (field.endswith("(ft)") or field in {"Design speed (mph)", "Design ADT", "Flare rate a/b"}):
            continue
        if field == "Lane width (ft)" and text == "(n/a)":
            continue
        if field == "L1 (ft)":
            match = re.fullmatch(r'([^()]+) \(-?\d+\x27-[\d.]+"\)', str(text))
            if not match:
                raise ValueError("Invalid L1 PDF value.")
            text = match[1]
        elif field == "Flare rate a/b":
            if text == "non-flared (0)":
                text = "0"
            else:
                match = re.fullmatch(r"([^/]+)/1", str(text))
                if not match:
                    raise ValueError("Invalid flare PDF value.")
                text = match[1]
        number = _first_number(str(text))
        numbers[field] = number
        if field in positive_fields:
            validation.require_positive(**{field: number})
        elif field not in signed_fields:
            validation.require_nonnegative(**{field: number})
    installation_fields = ("A (near) (ft)", "B (near) (ft)", "C (opp) (ft)", "D (opp) (ft)",
                           "L1 (ft)", "Terminal section (ft)")
    if all(field in numbers for field in installation_fields):
        # The display payload rounds each component independently to four decimals.
        validation.installation_totals(*(numbers[field] for field in installation_fields), tolerance=.00021)


def report_payload(report: ReportModel) -> dict:
    snapshot = report.snapshot
    inputs, project = snapshot.inputs, snapshot.project
    road, barrier = inputs.roadway, inputs.barrier
    return build_pdf_data(
        project.project, road.facility.value, inputs.speed, inputs.adt, barrier.LA,
        road.L2, road.L2_opp, road.lane_width, barrier.L1, barrier.terminal,
        barrier.flare_rate, report.style.value, snapshot.result.as_dict(),
        generated_time=report.generated_time, route_location=project.route_location,
        job_number=project.job_number, prepared_by=project.prepared_by,
        checked_by=project.checked_by, calculation_date=project.calculation_date,
    )
