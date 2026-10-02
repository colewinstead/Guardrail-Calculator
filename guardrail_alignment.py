"""Foot-based alignment geometry, station equations, and adaptive offset paths."""

from __future__ import annotations
import math
import re
from dataclasses import dataclass
from typing import Callable
import guardrail_validation as validation
from guardrail_models import AlignmentGeometry as AlignmentProtocol
from guardrail_design import PATH_TOLERANCE

GEOMETRY_ABS_TOLERANCE = 1e-4


GEOMETRY_REL_TOLERANCE = 1e-6


def _finite_float(value: str | float, name: str) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"{name} must be a number.") from exc
    if not math.isfinite(number):
        raise ValueError(f"{name} must be finite.")
    return number


@dataclass(frozen=True)
class Line: start: tuple[float, float]; end: tuple[float, float]; length: float


@dataclass(frozen=True)
class Arc: start: tuple[float, float]; end: tuple[float, float]; center: tuple[float, float]; radius: float; length: float; rotation: str


def _validate_segment(segment: Line | Arc, previous_end: tuple[float, float] | None) -> None:
    if segment.length < 0:
        raise ValueError("Segment length cannot be negative.")
    if previous_end is not None and math.dist(previous_end, segment.start) > GEOMETRY_ABS_TOLERANCE:
        raise ValueError("Segment start is disconnected from the preceding segment end.")
    chord = math.dist(segment.start, segment.end)
    if segment.length == 0 and chord > GEOMETRY_ABS_TOLERANCE:
        raise ValueError("Zero-length geometry has differing endpoints.")
    if isinstance(segment, Line):
        if not math.isclose(segment.length, chord, rel_tol=GEOMETRY_REL_TOLERANCE,
                            abs_tol=GEOMETRY_ABS_TOLERANCE):
            raise ValueError("Line length is inconsistent with its horizontal endpoints.")
        return

    if segment.radius <= 0:
        raise ValueError("Arc radius must be greater than zero.")
    if segment.rotation not in {"cw", "ccw"}:
        raise ValueError("Arc rotation must be 'cw' or 'ccw'.")
    for point in (segment.start, segment.end):
        if not math.isclose(math.dist(point, segment.center), segment.radius,
                            rel_tol=GEOMETRY_REL_TOLERANCE, abs_tol=GEOMETRY_ABS_TOLERANCE):
            raise ValueError("Arc endpoint is inconsistent with its center and radius.")
    start_angle = math.atan2(segment.start[1] - segment.center[1], segment.start[0] - segment.center[0])
    end_angle = math.atan2(segment.end[1] - segment.center[1], segment.end[0] - segment.center[0])
    sign = 1 if segment.rotation == "ccw" else -1
    sweep = (sign * (end_angle - start_angle)) % math.tau
    # Coincident endpoints can represent a complete circle, as well as a zero-length arc.
    if chord <= GEOMETRY_ABS_TOLERANCE and math.isclose(
        segment.length, math.tau * segment.radius,
        rel_tol=GEOMETRY_REL_TOLERANCE, abs_tol=GEOMETRY_ABS_TOLERANCE,
    ):
        sweep = math.tau
    if not math.isclose(segment.length, sweep * segment.radius,
                        rel_tol=GEOMETRY_REL_TOLERANCE, abs_tol=GEOMETRY_ABS_TOLERANCE):
        raise ValueError("Arc length is inconsistent with its endpoints, radius, and declared rotation.")


@dataclass
class Alignment:
    name: str
    start_station: float
    segments: list[Line | Arc]
    linear_unit: str = "foot"
    station_equations: list[dict] | None = None

    def station_range(self): return self.start_station, self.start_station + sum(s.length for s in self.segments)
    def geometry_breakpoints(self) -> list[float]:
        stations = [self.start_station]
        for segment in self.segments:
            stations.append(stations[-1] + segment.length)
        return stations
    def _locate(self, station):
        station = _finite_float(station, "Station")
        lo, hi = self.station_range()
        if station < lo - 1e-7 or station > hi + 1e-7: raise ValueError(f"Station {station:.3f} is outside alignment {self.name} ({lo:.3f} to {hi:.3f}).")
        remaining = max(0.0, station - lo)
        for seg in self.segments:
            if remaining <= seg.length + 1e-7: return seg, min(remaining, seg.length)
            remaining -= seg.length
        return self.segments[-1], self.segments[-1].length
    @staticmethod
    def _arc_sign(seg: Arc):
        if seg.rotation == "cw":
            return -1
        if seg.rotation == "ccw":
            return 1
        raise ValueError("Arc rotation must be 'cw' or 'ccw'.")
    def xy_at_station(self, station):
        seg, distance = self._locate(station)
        if isinstance(seg, Line):
            r = 0 if seg.length == 0 else distance/seg.length
            return seg.start[0]+(seg.end[0]-seg.start[0])*r, seg.start[1]+(seg.end[1]-seg.start[1])*r
        a = math.atan2(seg.start[1]-seg.center[1], seg.start[0]-seg.center[0]) + self._arc_sign(seg)*distance/seg.radius
        return seg.center[0]+seg.radius*math.cos(a), seg.center[1]+seg.radius*math.sin(a)
    def tangent_at_station(self, station):
        seg, distance = self._locate(station)
        if isinstance(seg, Line):
            dx, dy = seg.end[0]-seg.start[0], seg.end[1]-seg.start[1]; length=math.hypot(dx,dy) or 1
            return dx/length, dy/length
        sign=self._arc_sign(seg); a=math.atan2(seg.start[1]-seg.center[1],seg.start[0]-seg.center[0])+sign*distance/seg.radius
        return (-math.sin(a), math.cos(a)) if sign > 0 else (math.sin(a), -math.cos(a))

    def civil_to_internal(self, value: str | float) -> float:
        return civil_to_internal_station(value, self.station_equations, self.station_range())

    def internal_to_civil(self, station: float) -> float:
        return internal_to_civil_station(station, self.station_equations)

    def station_label(self, station: float) -> str:
        region = 1 + sum(1 for equation in normalize_station_equations(self.station_equations) if station >= equation["internal"])
        suffix = f"R{region}" if region > 1 else ""
        return f"{format_station(self.internal_to_civil(station))}{suffix}"

    def civil_region_labels(self) -> list[str]:
        return civil_station_region_labels(self.station_equations, self.station_range())


def parse_station(value: str | float) -> tuple[float, int | None]:
    text = str(value).strip().upper().replace(" ", "")
    match = re.fullmatch(r"(.+?)(?:R(\d+))?", text)
    if not match: raise ValueError(f"Invalid station: {value}")
    station_text, region_text = match.groups()
    if "+" in station_text:
        left, right = station_text.split("+", 1); station = float(left) * 100.0 + float(right)
    else: station = float(station_text)
    station = _finite_float(station, "Station")
    return station, int(region_text) if region_text else None


def format_station(station: float) -> str:
    hundreds = int(station // 100); return f"{hundreds}+{station - hundreds * 100:06.3f}"


def normalize_station_equations(equations: list[dict] | None) -> list[dict[str, float]]:
    result = []
    for equation in equations or []:
        try:
            back = float(equation.get("staBack", equation.get("back", "")))
            ahead = float(equation.get("staAhead", equation.get("ahead", "")))
            internal = float(equation.get("staInternal", equation.get("internal", back)))
        except (TypeError, ValueError) as exc:
            raise ValueError("Invalid LandXML station equation.") from exc
        _finite_float(back, "Station equation back")
        _finite_float(ahead, "Station equation ahead")
        _finite_float(internal, "Station equation internal")
        result.append({"internal": internal, "back": back, "ahead": ahead})
    return sorted(result, key=lambda item: item["internal"])


def civil_to_internal_station(value: str | float, equations: list[dict] | None,
                              station_range: tuple[float, float] | None = None) -> float:
    station, requested_region = parse_station(value)
    normalized = normalize_station_equations(equations)
    candidates = []
    prior_internal, prior_offset, region = float("-inf"), 0.0, 1
    for equation in normalized:
        candidate = station - prior_offset
        if prior_internal <= candidate <= equation["internal"]: candidates.append((region, candidate))
        prior_internal = equation["internal"]; prior_offset = equation["ahead"] - equation["internal"]; region += 1
    candidate = station - prior_offset
    if candidate >= prior_internal: candidates.append((region, candidate))
    if station_range:
        lo, hi = station_range; candidates = [(r, c) for r, c in candidates if lo - 1e-6 <= c <= hi + 1e-6]
    if requested_region is not None: candidates = [(r, c) for r, c in candidates if r == requested_region]
    if not candidates:
        suffix = f"R{requested_region}" if requested_region else ""
        ranges = "; ".join(civil_station_region_labels(equations, station_range)) if station_range else "the available station regions"
        raise ValueError(
            f"Station {format_station(station)}{suffix} is outside this alignment. "
            f"Valid civil-station regions: {ranges}."
        )
    if requested_region is None and any(
        abs(candidate - candidates[0][1]) > 1e-6 for _, candidate in candidates[1:]
    ):
        regions = ", ".join(f"R{region}" for region, _ in candidates)
        raise ValueError(f"Ambiguous civil station {value}; specify a station region ({regions}).")
    return candidates[0][1]


def internal_to_civil_station(station: float, equations: list[dict] | None) -> float:
    station = _finite_float(station, "Station")
    civil = station
    for equation in normalize_station_equations(equations):
        if station >= equation["internal"]: civil = station + equation["ahead"] - equation["internal"]
        else: break
    return civil


def civil_station_region_labels(equations: list[dict] | None, station_range: tuple[float, float]) -> list[str]:
    """Describe each continuous civil-station region without hiding equation jumps."""
    lo, hi = station_range
    normalized = normalize_station_equations(equations)
    labels = []
    region_start_internal = lo
    offset = 0.0
    region = 1
    for equation in normalized:
        region_end_internal = min(hi, equation["internal"])
        if region_start_internal <= region_end_internal:
            start_civil = region_start_internal + offset
            # The back station is the displayed value at the end of the preceding region.
            end_civil = equation["back"] if equation["internal"] <= hi else region_end_internal + offset
            suffix = "" if region == 1 else f"R{region}"
            labels.append(f"{format_station(start_civil)}{suffix} to {format_station(end_civil)}{suffix}")
        region_start_internal = max(lo, equation["internal"])
        offset = equation["ahead"] - equation["internal"]
        region += 1
    if region_start_internal <= hi:
        suffix = "" if region == 1 else f"R{region}"
        labels.append(f"{format_station(region_start_internal + offset)}{suffix} to {format_station(hi + offset)}{suffix}")
    return labels


@dataclass(frozen=True)
class LineAlignment:
    start: float
    end: float

    def __post_init__(self) -> None:
        validation.require_finite(start=self.start, end=self.end)
        if self.end <= self.start:
            raise ValueError("Alignment end must be greater than start.")

    def station_range(self) -> tuple[float, float]: return self.start, self.end
    def geometry_breakpoints(self) -> list[float]: return [self.start, self.end]
    def xy_at_station(self, station: float) -> tuple[float, float]:
        if station < self.start or station > self.end: raise ValueError("Station outside standalone alignment.")
        return station, 0.0
    def tangent_at_station(self, station: float) -> tuple[float, float]:
        self.xy_at_station(station); return 1.0, 0.0


def _point(alignment: AlignmentProtocol, station: float, offset: float) -> tuple[float, float]:
    validation.require_finite(station=station, offset=offset)
    x, y = alignment.xy_at_station(station); tx, ty = alignment.tangent_at_station(station)
    point = x - ty * offset, y + tx * offset
    validation.require_finite(x=point[0], y=point[1], tx=tx, ty=ty)
    return point


def _path(alignment: AlignmentProtocol, start: float, end: float,
          offset: float | Callable[[float], float], step: float = 10.0,
          *, count: int | None = None) -> list[tuple[float, float]]:
    """Sample constant/variable alignment offsets, retaining legacy straight vertices."""
    validation.require_finite(start=start, end=end)
    validation.require_positive(step=step)
    count = count or max(1, int(math.ceil(abs(end - start) / step)))
    stations = [start + (end - start) * i / count for i in range(count + 1)]
    if hasattr(alignment, "geometry_breakpoints"):
        stations.extend(s for s in alignment.geometry_breakpoints() if min(start, end) < s < max(start, end))
    stations = sorted(set(stations), reverse=end < start) if start != end else stations

    def point(station):
        return _point(alignment, station, offset(station) if callable(offset) else offset)

    def refine(a, b, pa, pb, depth=0):
        for ratio in (.25, .5, .75):
            actual = point(a + (b - a) * ratio)
            chord = (pa[0] + (pb[0] - pa[0]) * ratio, pa[1] + (pb[1] - pa[1]) * ratio)
            if math.dist(actual, chord) > PATH_TOLERANCE:
                if depth >= 20:
                    raise ValueError("Alignment offset cannot be sampled within DXF tolerance; check geometry joins.")
                mid = (a + b) / 2
                pm = point(mid)
                return refine(a, mid, pa, pm, depth + 1) + refine(mid, b, pm, pb, depth + 1)
        return [pb]

    points = [point(stations[0])]
    for a, b in zip(stations, stations[1:]):
        points.extend(refine(a, b, points[-1], point(b)))
    return points


def _taper_path(alignment: AlignmentProtocol, start: float, end: float,
                offset_start: float, offset_end: float, count: int = 1) -> list[tuple[float, float]]:
    def offset(station):
        ratio = 0 if start == end else (station - start) / (end - start)
        return offset_start + (offset_end - offset_start) * ratio
    return _path(alignment, start, end, offset, count=count)


# Public geometry interfaces; original private names remain compatibility aliases.
point_at_offset = _point
sample_offset_path = _path
sample_taper_path = _taper_path
