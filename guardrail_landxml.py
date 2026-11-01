"""LandXML file parsing with per-alignment diagnostics; no UI or serialization."""

from __future__ import annotations
import math
import xml.etree.ElementTree as ET
from pathlib import Path
from guardrail_alignment import (
    _finite_float, Line, Arc, _validate_segment, Alignment, parse_station,
    format_station, normalize_station_equations, civil_to_internal_station,
    internal_to_civil_station, civil_station_region_labels,
)

def _tag(node) -> str: return node.tag.rsplit("}", 1)[-1]


def _point(text: str) -> tuple[float, float]:
    values = [_finite_float(v, "Coordinate") for v in text.split()]
    if len(values) not in (2, 3):
        raise ValueError("LandXML points require northing, easting, and optional elevation.")
    # LandXML is Northing, Easting; CAD is X=Easting, Y=Northing.
    return values[1], values[0]


def load_alignments(path: str | Path, *, rejected_alignments: list[str] | None = None) -> list[Alignment]:
    """Strict by default; diagnostic mode retains only wholly valid alignments."""
    root = ET.parse(path).getroot()
    units = next((n for n in root.iter() if _tag(n) in {"Imperial", "Metric"}), None)
    unit = (units.get("linearUnit", "") if units is not None else "").lower()
    if unit not in {"foot", "feet", "us survey foot", "ussurveyfoot"}: raise ValueError(f"LandXML must use feet; found '{unit or 'undeclared'}'.")
    result = []
    failures = []
    for node in (n for n in root.iter() if _tag(n) == "Alignment"):
        try:
            result.append(_load_alignment(node, unit))
        except ValueError as exc:
            message = f"Alignment '{node.get('name', 'Unnamed alignment')}': {exc}"
            if rejected_alignments is None:
                raise ValueError(message) from exc
            rejected_alignments.append(message)
            failures.append(message)
    if not result:
        raise ValueError("LandXML contains no usable line/arc alignments. " + "; ".join(failures))
    return result


def _load_alignment(node, unit: str) -> Alignment:
    station_equations = [dict(n.attrib) for n in node.iter() if _tag(n) == "StaEquation"]
    geom = next((n for n in node if _tag(n) == "CoordGeom"), None)
    if geom is None:
        raise ValueError("Missing CoordGeom.")
    segments = []
    for child in geom:
        tag = _tag(child)
        if tag == "Feature": continue  # LandXML metadata, not horizontal geometry.
        if tag == "Spiral":
            raise ValueError("Unsupported geometry element 'Spiral'; spirals are not supported.")
        if tag not in {"Line", "Curve"}:
            raise ValueError(f"Unsupported geometry element '{tag}'.")
        children = {_tag(n): (n.text or "") for n in child}
        try:
            start, end = _point(children["Start"]), _point(children["End"])
            length = _finite_float(child.get("length", 0), "Segment length")
            if tag == "Line":
                segment = Line(start, end, length)
            else:
                segment = Arc(start, end, _point(children["Center"]),
                              _finite_float(child.get("radius", 0), "Arc radius"),
                              length, child.get("rot", "ccw"))
            _validate_segment(segment, segments[-1].end if segments else None)
        except (KeyError, ValueError) as exc:
            raise ValueError(f"Segment {len(segments) + 1} ({tag}): {exc}") from exc
        segments.append(segment)
    if not segments:
        raise ValueError("CoordGeom contains no line/arc geometry.")
    start_station = _finite_float(node.get("staStart", 0), "Alignment start station")
    if not math.isfinite(start_station + sum(segment.length for segment in segments)):
        raise ValueError("Alignment station range must be finite.")
    normalize_station_equations(station_equations)
    return Alignment(node.get("name", "Unnamed alignment"), start_station, segments, unit, station_equations)
