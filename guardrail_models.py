"""Immutable numeric application contracts, independent of UI and output libraries."""

from dataclasses import asdict, dataclass
from typing import Protocol

from guardrail_design import (
    ClearZoneSelection, DividedLayout, Facility, HazardOffsetSource, PlacementMode,
    ReportStyle, SideSlope,
)


class AlignmentGeometry(Protocol):
    def station_range(self) -> tuple[float, float]: ...
    def xy_at_station(self, station: float) -> tuple[float, float]: ...
    def tangent_at_station(self, station: float) -> tuple[float, float]: ...
    def geometry_breakpoints(self) -> list[float]: ...


@dataclass(frozen=True)
class ProjectMetadata:
    project: str = ""
    route_location: str = ""
    job_number: str = ""
    prepared_by: str = ""
    checked_by: str = ""
    calculation_date: str = ""


@dataclass(frozen=True)
class DividedRoadwayInputs:
    lanes_this: int
    lanes_opposing: int
    median_width: float


@dataclass(frozen=True)
class RoadwayConfiguration:
    facility: Facility
    L2: float
    lane_width: float
    added_distance: float
    L2_opp: float
    divided: DividedRoadwayInputs | None = None

    def as_dict(self) -> dict:
        divided = self.divided or DividedRoadwayInputs(1, 1, 0.0)
        return dict(facility=self.facility.value, L2=self.L2, lane_width=self.lane_width,
                    added_distance=self.added_distance, L2_opp=self.L2_opp,
                    lanes_this=divided.lanes_this, lanes_opposing=divided.lanes_opposing,
                    median_width=divided.median_width)


@dataclass(frozen=True)
class HazardBarrierInputs:
    LA: float
    L1: float
    terminal: float
    flare_rate: float
    offset_source: HazardOffsetSource = HazardOffsetSource.DIRECT
    slope: SideSlope | None = None
    clear_zone_selection: ClearZoneSelection | None = None


@dataclass(frozen=True)
class CalculationInputs:
    speed: int
    adt: float
    roadway: RoadwayConfiguration
    barrier: HazardBarrierInputs


@dataclass(frozen=True)
class CalculationResult:
    LR: float
    b_over_a: float
    X_min_near: float
    B_required: float
    flared_near: float
    flared_near_rounded: float
    X_design_near: float
    A: float
    B: float
    A_plus_gating: float
    X_min_opp: float
    D_required: float
    flared_opp: float
    flared_opp_rounded: float
    X_design_opp: float
    C: float
    D: float
    C_plus_gating: float

    def as_dict(self) -> dict[str, float]:
        return asdict(self)


@dataclass(frozen=True)
class CalculationSnapshot:
    project: ProjectMetadata
    inputs: CalculationInputs
    result: CalculationResult


@dataclass(frozen=True)
class AlignmentSelection:
    mode: PlacementMode
    alignment: AlignmentGeometry
    bridge_start: float
    bridge_end: float
    source_path: str | None = None
    linear_unit: str = "foot"


@dataclass(frozen=True)
class DrawingExportConfiguration:
    placement: AlignmentSelection
    divided_layout: DividedLayout = DividedLayout.OUTSIDE
    insunits: int = 2


@dataclass(frozen=True)
class ReportModel:
    snapshot: CalculationSnapshot
    style: ReportStyle
    generated_time: str
