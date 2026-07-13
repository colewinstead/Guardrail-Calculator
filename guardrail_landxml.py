"""Strict, foot-based LandXML alignment reader for guardrail DXF placement."""

from __future__ import annotations

import math
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from pathlib import Path


def _tag(node) -> str: return node.tag.rsplit("}", 1)[-1]
def _point(text: str) -> tuple[float, float]:
    values = [float(v) for v in text.split()]
    # LandXML is Northing, Easting; CAD is X=Easting, Y=Northing.
    return values[1], values[0]


@dataclass(frozen=True)
class Line: start: tuple[float, float]; end: tuple[float, float]; length: float
@dataclass(frozen=True)
class Arc: start: tuple[float, float]; end: tuple[float, float]; center: tuple[float, float]; radius: float; length: float; rotation: str


@dataclass
class Alignment:
    name: str
    start_station: float
    segments: list[Line | Arc]
    linear_unit: str = "foot"
    station_equations: list[dict] | None = None

    def station_range(self): return self.start_station, self.start_station + sum(s.length for s in self.segments)
    def _locate(self, station):
        lo, hi = self.station_range()
        if station < lo - 1e-7 or station > hi + 1e-7: raise ValueError(f"Station {station:.3f} is outside alignment {self.name} ({lo:.3f} to {hi:.3f}).")
        remaining = max(0.0, station - lo)
        for seg in self.segments:
            if remaining <= seg.length + 1e-7: return seg, min(remaining, seg.length)
            remaining -= seg.length
        return self.segments[-1], self.segments[-1].length
    @staticmethod
    def _arc_sign(seg: Arc):
        expected = seg.length / seg.radius
        a = math.atan2(seg.start[1]-seg.center[1], seg.start[0]-seg.center[0]); b = math.atan2(seg.end[1]-seg.center[1], seg.end[0]-seg.center[0])
        ccw, cw = (b-a) % math.tau, (a-b) % math.tau
        return 1 if abs(ccw-expected) <= abs(cw-expected) else -1
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
        except (TypeError, ValueError): continue
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
    return candidates[0][1]


def internal_to_civil_station(station: float, equations: list[dict] | None) -> float:
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


def load_alignments(path: str | Path) -> list[Alignment]:
    root = ET.parse(path).getroot()
    units = next((n for n in root.iter() if _tag(n) in {"Imperial", "Metric"}), None)
    unit = (units.get("linearUnit", "") if units is not None else "").lower()
    if unit not in {"foot", "feet", "us survey foot", "ussurveyfoot"}: raise ValueError(f"LandXML must use feet; found '{unit or 'undeclared'}'.")
    result = []
    for node in (n for n in root.iter() if _tag(n) == "Alignment"):
        station_equations = [dict(n.attrib) for n in node.iter() if _tag(n) == "StaEquation"]
        geom = next((n for n in node if _tag(n) == "CoordGeom"), None)
        if geom is None: continue
        segments = []
        for child in geom:
            tag = _tag(child)
            if tag == "Spiral": raise ValueError(f"Alignment '{node.get('name','')}' contains spirals, which are not supported.")
            children = {_tag(n): (n.text or "") for n in child}
            if tag == "Line": segments.append(Line(_point(children["Start"]), _point(children["End"]), float(child.get("length", 0))))
            elif tag == "Curve": segments.append(Arc(_point(children["Start"]), _point(children["End"]), _point(children["Center"]), float(child.get("radius",0)), float(child.get("length",0)), child.get("rot","ccw")))
        if segments: result.append(Alignment(node.get("name", "Unnamed alignment"), float(node.get("staStart",0)), segments, unit, station_equations))
    if not result: raise ValueError("LandXML contains no usable line/arc alignments.")
    return result
