"""Pure calculation functions. Characterized behavior is not engineering approval."""

import math
from typing import Optional
import guardrail_validation as validation
from guardrail_validation import require_finite as _require_finite
from guardrail_design import INCR_GUARDRAIL_FT, DEFAULT_GATING_FT, TABLE_9_6_A, TABLE_9_2_A
from guardrail_models import CalculationInputs, CalculationResult, CalculationSnapshot, ProjectMetadata


def calculate(inputs: CalculationInputs) -> CalculationResult:
    validation.validate_inputs(inputs)
    road, barrier = inputs.roadway, inputs.barrier
    values = compute_guardrail_outputs(inputs.speed, inputs.adt, barrier.LA, road.L2,
                                      road.L2_opp, barrier.L1, barrier.terminal, barrier.flare_rate)
    return CalculationResult(**values)


def create_snapshot(project: ProjectMetadata, inputs: CalculationInputs) -> CalculationSnapshot:
    return CalculationSnapshot(project, inputs, calculate(inputs))

def adt_bucket_index(adt: float) -> int:
    validation.require_nonnegative(ADT=adt)
    # Matches Table 9-6-A columns: 10,000 ; 5,000-10,000 ; 1,000-5,000 ; under 1,000
    if adt >= 10000:
        return 0
    if adt >= 5000:
        return 1
    if adt >= 1000:
        return 2
    return 3


def get_lr(speed_mph: int, adt: float) -> float:
    validation.require_positive(speed=speed_mph)
    if speed_mph not in TABLE_9_6_A:
        raise ValueError("Design speed must match a Table 9-6-A speed.")
    idx = adt_bucket_index(adt)
    return float(TABLE_9_6_A[speed_mph]["LR"][idx])


def speed_group_clearzone(speed: float) -> str:
    validation.require_positive(speed=speed)
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
    validation.require_nonnegative(ADT=adt)
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
    _require_finite(speed=speed, adt=adt)
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
    value = float(custom_value)
    validation.require_positive(custom_clear_zone=value)
    return value


def round_up_to_increment(x: float, inc: float) -> float:
    _require_finite(x=x)
    validation.require_positive(increment=inc)
    quotient = x / inc
    _require_finite(quotient=quotient)
    nearest = round(quotient)
    if math.isclose(quotient, nearest, rel_tol=0.0, abs_tol=1e-9):
        return nearest * inc
    return math.ceil(quotient) * inc


def compute_x_min(speed: int, adt: float, LA: float, L2: float, L1: float, a_over_b: float) -> tuple[float, float]:
    """
    Returns (X_min, LR).
    - Flared equation + non-flared equation come from Table 9-6-A
    """
    validation.calculation_inputs(speed, adt, LA, L2, L2, L1, 0, a_over_b)
    LR = get_lr(speed, adt)

    if a_over_b == 0.0:
        # Non-flared design:
        # X = LR (LA - L2) / LA
        X_min = (LR * (LA - L2)) / LA
        _require_finite(X_min=X_min)
        return X_min, LR

    # Flared design:
    # X = (LA + (b/a)*L1 - L2) / ( (b/a) + (LA/LR) )
    b_over_a = 1.0 / a_over_b
    numerator = LA + (b_over_a * L1) - L2
    denom = b_over_a + (LA / LR)
    X_min = numerator / denom
    _require_finite(X_min=X_min)
    return X_min, LR


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
    validation.calculation_inputs(speed, adt, LA, L2, L2_opp, L1, terminal_section, a_over_b)
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

    outputs = {
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
    _require_finite(**outputs)
    return outputs
