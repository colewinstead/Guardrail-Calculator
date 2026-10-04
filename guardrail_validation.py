"""Basic numeric data checks shared by calculation and output paths."""

import math


def require_finite(**values: float) -> None:
    for name, value in values.items():
        try:
            valid = not isinstance(value, bool) and math.isfinite(value)
        except (TypeError, ValueError, OverflowError):
            valid = False
        if not valid:
            raise ValueError(f"{name} must be a finite number.")


def require_nonnegative(**values: float) -> None:
    require_finite(**values)
    for name, value in values.items():
        if value < 0:
            raise ValueError(f"{name} cannot be negative.")


def require_positive(**values: float) -> None:
    require_finite(**values)
    for name, value in values.items():
        if value <= 0:
            raise ValueError(f"{name} must be greater than zero.")


def lane_count(value: float, name: str) -> int:
    require_positive(**{name: value})
    if value != int(value):
        raise ValueError(f"{name} must be a whole number of lanes.")
    return int(value)


def calculation_inputs(speed, adt, LA, L2, L2_opp, L1, terminal, flare) -> None:
    require_positive(speed=speed, LA=LA)
    require_nonnegative(ADT=adt, L2=L2, L2_opp=L2_opp, L1=L1, terminal=terminal, flare=flare)
    # LA < L2 is mathematically evaluable; applicability requires engineering review.


def installation_totals(A, B, C, D, L1, terminal, *, tolerance=1e-6) -> None:
    require_nonnegative(A=A, B=B, C=C, D=D, L1=L1, terminal=terminal)
    for label, total, rail in (("A", A, B), ("C", C, D)):
        expected = rail + L1 + terminal
        require_finite(**{label: expected})
        if not math.isclose(total, expected, rel_tol=0, abs_tol=tolerance):
            raise ValueError(f"{label} must equal its rail length plus L1 and terminal.")


def roadway_inputs(facility, L2, lane_width, lanes_this=1, lanes_opposing=1,
                   median_width=0.0, added_distance=None) -> dict:
    if facility not in {"two_lane_two_way", "divided_highway"}:
        raise ValueError("Invalid facility type.")
    require_nonnegative(L2=L2, median_width=median_width)
    require_positive(lane_width=lane_width)
    lanes_this = lane_count(lanes_this, "lanes_this")
    lanes_opposing = lane_count(lanes_opposing, "lanes_opposing")
    geometric_crossing = lane_width if facility == "two_lane_two_way" else (
        lane_width * (lanes_this + lanes_opposing) + median_width
    )
    require_finite(geometric_crossing=geometric_crossing)
    crossing = geometric_crossing if added_distance is None else added_distance
    require_nonnegative(added_distance=crossing)
    opposing_offset = L2 + crossing
    require_finite(L2_opp=opposing_offset)
    return dict(facility=facility, L2=L2, lane_width=lane_width, lanes_this=lanes_this,
                lanes_opposing=lanes_opposing, median_width=median_width,
                added_distance=crossing, L2_opp=opposing_offset)


def require_drawing_crossing(roadway: dict) -> None:
    geometric = roadway_inputs(
        roadway["facility"], roadway["L2"], roadway["lane_width"],
        roadway["lanes_this"], roadway["lanes_opposing"], roadway["median_width"],
    )["added_distance"]
    if not math.isclose(geometric, roadway["added_distance"], rel_tol=1e-9, abs_tol=1e-6):
        raise ValueError(
            "Entered opposing distance disagrees with the drawing's lane/median dimensions. "
            "Use Calculated Distance, or supply matching dimensions before DXF export. "
            "A custom crossing distance remains available for calculation/PDF only."
        )
