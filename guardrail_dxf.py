"""To-scale R12 DXF plan export based on MDOT GR-4 and GR-4A."""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Protocol

import guardrail_validation as validation


LAYERS = {
    "alignment": "GR_ALIGNMENT", "road": "GR_ROAD", "bridge": "GR_BRIDGE",
    "lane": "GR_LANE_LINES", "shoulder": "GR_SHOULDER_FLARE", "normal_shoulder": "GR_NORMAL_SHOULDER",
    "foreslope": "GR_FORESLOPE_W",
    "rail": "GR_GUARDRAIL", "post": "GR_GUARDRAIL_POSTS", "terminal": "GR_TERMINAL", "gating": "GR_GATING",
    "dimension": "GR_DIMENSION", "leader": "GR_LEADERS", "text": "GR_TEXT",
    "traffic": "GR_TRAFFIC_ARROWS",
}

BRIDGE_END_SECTION = 18.0 + 1.75 / 12.0
GATING_LENGTH = 12.5
SHOULDER_FLARE_LENGTH = 75.0
SHOULDER_TRANSITION_LENGTH = 150.0
NORMAL_SHOULDER_EXTENSION = 50.0
PATH_TOLERANCE = 0.01  # Maximum sampled chord deviation, in feet.
TEXT_HEIGHT = 2.5
ENGINEERING_TEXT_STYLE = "Engineering Regular"
ENGINEERING_FONT_FILE = "EngineeringRegular.ttf"
SHOULDER_CLEARANCE_BEHIND_RAIL = 3.0
TERMINAL_LATERAL_FLARE = 4.0 + 8.0 / 12.0
TERMINAL_END_LATERAL_FLARE = 2.0
GATING_LATERAL_FLARE = TERMINAL_LATERAL_FLARE - TERMINAL_END_LATERAL_FLARE
TERMINAL_SHOULDER_CLEARANCE = 4.0
GUARDRAIL_POST_SPACING = 6.25


class Alignment(Protocol):
    def station_range(self) -> tuple[float, float]: ...
    def xy_at_station(self, station: float) -> tuple[float, float]: ...
    def tangent_at_station(self, station: float) -> tuple[float, float]: ...


@dataclass(frozen=True)
class LineAlignment:
    start: float
    end: float

    def __post_init__(self) -> None:
        validation.require_finite(start=self.start, end=self.end)
        if self.end <= self.start:
            raise ValueError("Alignment end must be greater than start.")

    def station_range(self) -> tuple[float, float]: return self.start, self.end
    def xy_at_station(self, station: float) -> tuple[float, float]:
        if station < self.start or station > self.end: raise ValueError("Station outside standalone alignment.")
        return station, 0.0
    def tangent_at_station(self, station: float) -> tuple[float, float]:
        self.xy_at_station(station); return 1.0, 0.0


@dataclass(frozen=True)
class DrawingModel:
    facility: str
    bridge_start: float
    bridge_end: float
    alignment: Alignment
    A: float
    B: float
    C: float
    D: float
    L1: float
    terminal: float
    L2: float
    LA: float
    lane_width: float
    lanes_this: int = 1
    lanes_opposing: int = 1
    median_width: float = 0.0
    flare_rate: float = 30.0
    divided_layout: str = "outside"
    project: str = ""
    route: str = ""
    insunits: int = 2
    opposing_added_distance: float | None = None


class DxfWriter:
    def __init__(self) -> None:
        self.entities: list[str] = []
        self.text_boxes: list[tuple[float, float, float, float]] = []
        self.records: list[tuple] = []

    def _append(self, *pairs: object) -> None: self.entities.extend(str(v) for v in pairs)

    def add_line(self, p1: tuple[float, float], p2: tuple[float, float], layer: str) -> None:
        validation.require_finite(x1=p1[0], y1=p1[1], x2=p2[0], y2=p2[1])
        self.records.append(("LINE", float(p1[0]), float(p1[1]), float(p2[0]), float(p2[1]), layer))
        self._append(0, "LINE", 8, layer, 10, round(p1[0], 6), 20, round(p1[1], 6), 30, 0,
                     11, round(p2[0], 6), 21, round(p2[1], 6), 31, 0)

    def add_polyline(self, points: list[tuple[float, float]], layer: str) -> None:
        for p1, p2 in zip(points, points[1:]): self.add_line(p1, p2, layer)

    @staticmethod
    def text_box(
        point: tuple[float, float], text: str, height: float, rotation: float,
        alignment: str = "LEFT",
    ) -> tuple[float, float, float, float]:
        width = max(height, len(text) * height * 0.62)
        angle = math.radians(rotation)
        ux, uy = math.cos(angle), math.sin(angle)
        vx, vy = -uy, ux
        corners = []
        along_limits = (-width / 2.0, width / 2.0) if alignment == "CENTER" else (0.0, width)
        for along in along_limits:
            for vertical in (-0.35 * height, 0.75 * height):
                corners.append((point[0] + ux * along + vx * vertical, point[1] + uy * along + vy * vertical))
        xs, ys = [p[0] for p in corners], [p[1] for p in corners]
        return min(xs) - 0.5, min(ys) - 0.5, max(xs) + 0.5, max(ys) + 0.5

    @staticmethod
    def boxes_overlap(a, b, gap: float = 0.5) -> bool:
        return not (a[2] + gap <= b[0] or b[2] + gap <= a[0] or a[3] + gap <= b[1] or b[3] + gap <= a[1])

    def add_label(self, anchor: tuple[float, float], text: str, rotation: float = 0.0,
                  preferred_shift: tuple[float, float] = (0.0, 0.0), auto_leader: bool = True,
                  alignment: str = "LEFT") -> tuple[float, float]:
        alignment = alignment.upper()
        x, y = anchor[0] + preferred_shift[0], anchor[1] + preferred_shift[1]
        # Shift along the text-normal until the new box is clear of every prior label.
        nx, ny = -math.sin(math.radians(rotation)), math.cos(math.radians(rotation))
        for _ in range(80):
            box = self.text_box((x, y), text, TEXT_HEIGHT, rotation, alignment)
            if not any(self.boxes_overlap(box, other) for other in self.text_boxes): break
            x += nx * (TEXT_HEIGHT + 1.5); y += ny * (TEXT_HEIGHT + 1.5)
        else: raise ValueError(f"Could not place DXF label without overlap: {text}")
        self.text_boxes.append(box)
        self.records.append((
            "TEXT", float(x), float(y), text.replace("\n", " "), TEXT_HEIGHT,
            LAYERS["text"], float(rotation), alignment,
        ))
        self._append(0, "TEXT", 8, LAYERS["text"], 10, round(x, 6), 20, round(y, 6), 30, 0,
                     40, TEXT_HEIGHT, 1, text.replace("\n", " "), 50, round(rotation, 6))
        if auto_leader and math.hypot(x - anchor[0], y - anchor[1]) > 5.0:
            self.add_line(anchor, (x, y), LAYERS["leader"])
        return x, y

    def save(self, path: str | Path, insunits: int = 2) -> None:
        try:
            import ezdxf
        except ImportError as exc:
            raise RuntimeError("DXF export requires ezdxf. Install it with: py -m pip install ezdxf") from exc
        doc = ezdxf.new("R2000", setup=False)
        doc.header["$INSUNITS"] = int(insunits)
        if not doc.styles.has_entry(ENGINEERING_TEXT_STYLE):
            doc.styles.add(ENGINEERING_TEXT_STYLE, font=ENGINEERING_FONT_FILE)
        # Match the Superelevation Calculator's MDOT/ORD handoff. The extended
        # family data makes ORD treat EngineeringRegular.ttf as TrueType rather
        # than attempting to resolve it as a missing SHX font.
        engineering_style = doc.styles.get(ENGINEERING_TEXT_STYLE)
        engineering_style.dxf.font = ENGINEERING_FONT_FILE
        engineering_style.set_extended_font_data(
            family=ENGINEERING_TEXT_STYLE,
            italic=False,
            bold=False,
        )
        styles = {
            LAYERS["alignment"]: (8, 18), LAYERS["road"]: (7, 35), LAYERS["bridge"]: (7, 50),
            LAYERS["lane"]: (8, 18), LAYERS["shoulder"]: (3, 25), LAYERS["normal_shoulder"]: (3, 25),
            LAYERS["foreslope"]: (94, 18), LAYERS["rail"]: (1, 50), LAYERS["post"]: (1, 35),
            LAYERS["terminal"]: (30, 50), LAYERS["gating"]: (6, 50), LAYERS["dimension"]: (5, 18),
            LAYERS["leader"]: (8, 18), LAYERS["text"]: (7, 18), LAYERS["traffic"]: (7, 35),
        }
        if not doc.linetypes.has_entry("DASHED"):
            doc.linetypes.add("DASHED", pattern=[0.6, 0.3, -0.3], description="Guardrail shoulder line")
        for layer, (color, weight) in styles.items():
            linetype = "DASHED" if layer == LAYERS["normal_shoulder"] else "CONTINUOUS"
            if not doc.layers.has_entry(layer): doc.layers.add(layer, color=color, linetype=linetype)
            doc.layers.get(layer).dxf.linetype = linetype
            doc.layers.get(layer).dxf.lineweight = weight
        space = doc.modelspace()
        from ezdxf.enums import TextEntityAlignment

        for record in self.records:
            if record[0] == "LINE":
                _, x1, y1, x2, y2, layer = record
                space.add_line((x1, y1, 0), (x2, y2, 0), dxfattribs={"layer": layer})
            else:
                _, x, y, text, height, layer, rotation, alignment = record
                space.add_text(
                    text,
                    dxfattribs={
                        "height": height,
                        "rotation": rotation,
                        "layer": layer,
                        "style": ENGINEERING_TEXT_STYLE,
                    },
                ).set_placement(
                    (x, y, 0),
                    align=(
                        TextEntityAlignment.MIDDLE_CENTER
                        if alignment == "CENTER"
                        else TextEntityAlignment.LEFT
                    ),
                )
        doc.saveas(path)


def _upright_angle(tx: float, ty: float) -> float:
    angle = math.degrees(math.atan2(ty, tx))
    if angle > 90: angle -= 180
    if angle <= -90: angle += 180
    return angle


def _point(alignment: Alignment, station: float, offset: float) -> tuple[float, float]:
    validation.require_finite(station=station, offset=offset)
    x, y = alignment.xy_at_station(station); tx, ty = alignment.tangent_at_station(station)
    point = x - ty * offset, y + tx * offset
    validation.require_finite(x=point[0], y=point[1], tx=tx, ty=ty)
    return point


def _path(alignment: Alignment, start: float, end: float,
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


def _taper_path(alignment: Alignment, start: float, end: float,
                offset_start: float, offset_end: float, count: int = 1) -> list[tuple[float, float]]:
    def offset(station):
        ratio = 0 if start == end else (station - start) / (end - start)
        return offset_start + (offset_end - offset_start) * ratio
    return _path(alignment, start, end, offset, count=count)


def validate_supported_installations(model: DrawingModel) -> None:
    """Reject undefined drawing treatments without changing calculation behavior."""
    if model.terminal == 0:
        raise ValueError("DXF terminal length must be greater than zero; zero-terminal drawing treatment requires MDOT verification. Calculations and PDF output may still use zero.")
    validation.require_positive(terminal=model.terminal)
    lengths = [("A", model.A)]
    if model.facility == "two_lane_two_way":
        lengths.append(("C", model.C))
    for label, length in lengths:
        if length + GATING_LENGTH < SHOULDER_FLARE_LENGTH - 1e-6:
            raise ValueError(f"{label} installation has insufficient length for the 75-ft clear-zone taper; short-installation DXF treatment requires engineering verification.")


def validate_model(model: DrawingModel) -> None:
    validation.require_finite(bridge_start=model.bridge_start, bridge_end=model.bridge_end)
    validation.require_nonnegative(B=model.B, D=model.D, L1=model.L1, terminal=model.terminal,
                                   L2=model.L2, median_width=model.median_width, flare=model.flare_rate)
    validation.require_positive(A=model.A, C=model.C, LA=model.LA)
    roadway = validation.roadway_inputs(model.facility, model.L2, model.lane_width,
                                       model.lanes_this, model.lanes_opposing, model.median_width,
                                       model.opposing_added_distance)
    if model.opposing_added_distance is not None:
        validation.require_drawing_crossing(roadway)
    if model.divided_layout not in {"inside", "outside"}:
        raise ValueError("Invalid divided highway layout.")
    validation.installation_totals(model.A, model.B, model.C, model.D, model.L1, model.terminal)
    validate_supported_installations(model)
    if model.bridge_end <= model.bridge_start: raise ValueError("Bridge end station must be greater than bridge start station.")
    if model.L2 < 0 or model.LA <= 0 or model.LA < model.L2:
        raise ValueError("Drawing widths require LA (W) to be greater than or equal to L2.")
    required = (
        max(model.A, model.C)
        + GATING_LENGTH + SHOULDER_TRANSITION_LENGTH + NORMAL_SHOULDER_EXTENSION
    )
    lo, hi = model.alignment.station_range()
    validation.require_finite(alignment_start=lo, alignment_end=hi, required=required)
    if model.bridge_start - required < lo - 1e-6:
        raise ValueError(f"Alignment needs {required:.3f} ft before bridge start for guardrail and shoulder transition.")
    if model.bridge_end + required > hi + 1e-6:
        raise ValueError(f"Alignment needs {required:.3f} ft after bridge end for guardrail and shoulder transition.")


def _dimension(writer: DxfWriter, alignment: Alignment, s1: float, s2: float, offset: float, label: str) -> None:
    # Labels describe alignment station distances, not chords or offset-path lengths.
    p1, p2 = _point(alignment, s1, offset), _point(alignment, s2, offset)
    writer.add_line(p1, p2, LAYERS["dimension"])
    for station, p in ((s1, p1), (s2, p2)):
        tx, ty = alignment.tangent_at_station(station); writer.add_line((p[0] + ty * 2, p[1] - tx * 2), (p[0] - ty * 2, p[1] + tx * 2), LAYERS["dimension"])
    mid = (s1 + s2) / 2; tx, ty = alignment.tangent_at_station(mid)
    side = 1.0 if offset >= 0 else -1.0
    writer.add_label(
        _point(alignment, mid, offset), label, _upright_angle(tx, ty),
        (-ty * side * 4.0, tx * side * 4.0),
        auto_leader=False,
        alignment="CENTER",
    )


def _callout(writer: DxfWriter, alignment: Alignment, station: float, feature_offset: float,
             text_offset: float, text: str, landing_length: float = 14.0) -> None:
    """Draw an engineering-style two-segment leader with arrowhead and landing."""
    anchor = _point(alignment, station, feature_offset)
    tx, ty = alignment.tangent_at_station(station)
    rotation = _upright_angle(tx, ty)
    ux, uy = math.cos(math.radians(rotation)), math.sin(math.radians(rotation))
    desired = _point(alignment, station, text_offset)
    desired = (desired[0] + ux * landing_length, desired[1] + uy * landing_length)
    placed = writer.add_label(desired, text, rotation, auto_leader=False)
    landing_end = (placed[0] - ux * 1.5, placed[1] - uy * 1.5)
    elbow = (placed[0] - ux * landing_length, placed[1] - uy * landing_length)
    writer.add_line(anchor, elbow, LAYERS["leader"])
    writer.add_line(elbow, landing_end, LAYERS["leader"])
    # Filled-looking open arrowhead at the feature end.
    dx, dy = elbow[0] - anchor[0], elbow[1] - anchor[1]
    length = math.hypot(dx, dy) or 1.0; dx, dy = dx / length, dy / length
    px, py = -dy, dx
    writer.add_line(anchor, (anchor[0] + dx * 2.2 + px * 0.8, anchor[1] + dy * 2.2 + py * 0.8), LAYERS["leader"])
    writer.add_line(anchor, (anchor[0] + dx * 2.2 - px * 0.8, anchor[1] + dy * 2.2 - py * 0.8), LAYERS["leader"])


def _cross_dimension(writer: DxfWriter, alignment: Alignment, station: float, offset1: float,
                     offset2: float, label: str) -> None:
    p1, p2 = _point(alignment, station, offset1), _point(alignment, station, offset2)
    writer.add_line(p1, p2, LAYERS["dimension"])
    tx, ty = alignment.tangent_at_station(station)
    for point in (p1, p2):
        writer.add_line((point[0] - tx * 1.5, point[1] - ty * 1.5), (point[0] + tx * 1.5, point[1] + ty * 1.5), LAYERS["dimension"])
    mid_offset = (offset1 + offset2) / 2.0
    normal_angle = _upright_angle(-ty, tx)
    writer.add_label(_point(alignment, station, mid_offset), label, normal_angle, (tx * 3.0, ty * 3.0), auto_leader=False)


def _arrow(writer: DxfWriter, alignment: Alignment, station: float, offset: float, direction: float) -> None:
    x, y = _point(alignment, station, offset); tx, ty = alignment.tangent_at_station(station)
    tx, ty = tx * direction, ty * direction; nx, ny = -ty, tx
    writer.add_line((x - tx * 6, y - ty * 6), (x + tx * 6, y + ty * 6), LAYERS["traffic"])
    writer.add_line((x + tx * 6, y + ty * 6), (x + tx * 2 + nx * 2, y + ty * 2 + ny * 2), LAYERS["traffic"])
    writer.add_line((x + tx * 6, y + ty * 6), (x + tx * 2 - nx * 2, y + ty * 2 - ny * 2), LAYERS["traffic"])


def _feet(value: float) -> str:
    """Compact engineering-plan length used by dimension labels."""
    return f"{value:.2f}'"


def _installation(writer: DxfWriter, m: DrawingModel, bridge_station: float, outward: float,
                  side: float, road_edge: float, overall: float, normal: float,
                  overall_letter: str, normal_letter: str) -> None:
    # Stations progress from the bridge outward regardless of bridge end.
    at = lambda distance: bridge_station + outward * distance
    rail_offset = side * (road_edge + m.L2)
    normal_end = m.L1 + normal
    terminal_end = normal_end + m.terminal
    gate_end = terminal_end + GATING_LENGTH
    # B/D is the calculated flared guardrail portion. L1 stays tangent and the terminal
    # continues at the completed flare offset, matching the length-of-need calculation.
    flare_length = normal
    flare_start = m.L1
    flare_end = normal_end
    flare_delta = 0.0 if m.flare_rate == 0 else flare_length / m.flare_rate
    tapered_rail_offset = rail_offset + side * flare_delta
    terminal_gating_length = m.terminal + GATING_LENGTH
    terminal_flare_rate = m.terminal / TERMINAL_END_LATERAL_FLARE
    gating_flare_rate = GATING_LENGTH / GATING_LATERAL_FLARE
    terminal_rail_offset = tapered_rail_offset + side * TERMINAL_END_LATERAL_FLARE
    gating_rail_offset = tapered_rail_offset + side * TERMINAL_LATERAL_FLARE

    writer.add_polyline(_path(m.alignment, at(0), at(flare_start), rail_offset), LAYERS["rail"])
    flare_points = _taper_path(m.alignment, at(flare_start), at(flare_end), rail_offset, tapered_rail_offset, 16)
    writer.add_polyline(flare_points, LAYERS["rail"])
    terminal_points = _taper_path(m.alignment, at(flare_end), at(terminal_end), tapered_rail_offset, terminal_rail_offset, 8)
    writer.add_polyline(terminal_points, LAYERS["terminal"])
    gating_points = _taper_path(m.alignment, at(terminal_end), at(gate_end), terminal_rail_offset, gating_rail_offset, 4)
    writer.add_polyline(gating_points, LAYERS["gating"])

    def rail_offset_at(distance: float) -> float:
        if distance <= flare_start or m.flare_rate == 0:
            tapered = rail_offset
        elif distance <= flare_end:
            tapered = rail_offset + side * ((distance - flare_start) / m.flare_rate)
        else:
            tapered = tapered_rail_offset
        if distance <= flare_end:
            return tapered
        if distance <= terminal_end:
            return tapered_rail_offset + side * ((distance - flare_end) / terminal_flare_rate)
        if distance <= gate_end:
            return terminal_rail_offset + side * ((distance - terminal_end) / gating_flare_rate)
        return gating_rail_offset

    # GR-4A represents the guardrail with regularly spaced square post markers.
    post_count = int(math.floor(gate_end / GUARDRAIL_POST_SPACING))
    for index in range(post_count + 1):
        distance = min(gate_end, index * GUARDRAIL_POST_SPACING)
        station = at(distance); center = _point(m.alignment, station, rail_offset_at(distance))
        tx, ty = m.alignment.tangent_at_station(station); nx, ny = -ty, tx; half = 0.28
        corners = [
            (center[0] - tx * half - nx * half, center[1] - ty * half - ny * half),
            (center[0] + tx * half - nx * half, center[1] + ty * half - ny * half),
            (center[0] + tx * half + nx * half, center[1] + ty * half + ny * half),
            (center[0] - tx * half + nx * half, center[1] - ty * half + ny * half),
        ]
        writer.add_polyline(corners + [corners[0]], LAYERS["post"])

    # Along the rail, the hinge line is 3 ft behind the guardrail face: 1 ft rail
    # assembly + 2 ft clearance. From the gating end, the 150-ft transition ties
    # all the way into the ETL. The normal shoulder at ETL + L2 intersects that
    # taper sooner and continues separately as a dashed line.
    guardrail_shoulder_offset = rail_offset + side * SHOULDER_CLEARANCE_BEHIND_RAIL
    tapered_shoulder_offset = tapered_rail_offset + side * SHOULDER_CLEARANCE_BEHIND_RAIL
    normal_shoulder_offset = side * (road_edge + m.L2)
    etl_offset = side * road_edge
    terminal_shoulder_clearance = SHOULDER_CLEARANCE_BEHIND_RAIL + (
        (TERMINAL_SHOULDER_CLEARANCE - SHOULDER_CLEARANCE_BEHIND_RAIL) * (m.terminal / terminal_gating_length)
    )
    terminal_shoulder_offset = terminal_rail_offset + side * terminal_shoulder_clearance
    gating_shoulder_offset = gating_rail_offset + side * TERMINAL_SHOULDER_CLEARANCE
    shoulder_vertices = [(0, guardrail_shoulder_offset), (flare_start, guardrail_shoulder_offset),
                         (flare_end, tapered_shoulder_offset), (terminal_end, terminal_shoulder_offset),
                         (gate_end, gating_shoulder_offset), (gate_end + SHOULDER_TRANSITION_LENGTH, etl_offset)]
    shoulder_points = [_point(m.alignment, at(0), guardrail_shoulder_offset)]
    for (a, oa), (b, ob) in zip(shoulder_vertices, shoulder_vertices[1:]):
        shoulder_points.extend(_taper_path(m.alignment, at(a), at(b), oa, ob)[1:])
    writer.add_polyline(shoulder_points, LAYERS["shoulder"])

    gating_width_from_etl = abs(gating_shoulder_offset) - road_edge
    normal_tie_ratio = (
        max(0.0, min(1.0, (gating_width_from_etl - m.L2) / gating_width_from_etl))
        if gating_width_from_etl > 1e-9 else 0.0
    )
    normal_tie_distance = gate_end + SHOULDER_TRANSITION_LENGTH * normal_tie_ratio
    writer.add_polyline(
        _path(m.alignment, at(normal_tie_distance),
              at(gate_end + SHOULDER_TRANSITION_LENGTH + NORMAL_SHOULDER_EXTENSION),
              normal_shoulder_offset, count=1),
        LAYERS["normal_shoulder"],
    )

    def shoulder_offset_at(distance: float) -> float:
        if distance <= flare_start:
            return guardrail_shoulder_offset
        if distance <= flare_end:
            ratio = (distance - flare_start) / max(flare_length, 1e-9)
            return guardrail_shoulder_offset + (tapered_shoulder_offset - guardrail_shoulder_offset) * ratio
        if distance <= terminal_end:
            ratio = (distance - flare_end) / max(m.terminal, 1e-9)
            return tapered_shoulder_offset + (terminal_shoulder_offset - tapered_shoulder_offset) * ratio
        if distance <= gate_end:
            ratio = (distance - terminal_end) / GATING_LENGTH
            return terminal_shoulder_offset + (gating_shoulder_offset - terminal_shoulder_offset) * ratio
        ratio = min(1.0, (distance - gate_end) / SHOULDER_TRANSITION_LENGTH)
        return gating_shoulder_offset + (etl_offset - gating_shoulder_offset) * ratio

    # W=LA is measured outward from the edge of traveled lane. On the approach
    # beyond the gating endpoint it remains at full width. Looking toward the
    # bridge, it tapers into the actual shoulder line over 75 ft.
    w_offset = side * (road_edge + m.LA)
    clear_zone_join_distance = gate_end - SHOULDER_FLARE_LENGTH
    shoulder_join_offset = shoulder_offset_at(clear_zone_join_distance)
    writer.add_polyline(
        _path(m.alignment, at(gate_end + SHOULDER_TRANSITION_LENGTH + NORMAL_SHOULDER_EXTENSION),
              at(gate_end), w_offset, count=1)
        + _taper_path(m.alignment, at(gate_end), at(clear_zone_join_distance),
                      w_offset, shoulder_join_offset)[1:],
        LAYERS["foreslope"],
    )
    # Keep LA horizontal and adjacent to the full-width clear-zone line instead
    # of placing a vertical label across the roadway/guardrail geometry.
    la_station = at(gate_end + 55.0)
    la_tx, la_ty = m.alignment.tangent_at_station(la_station)
    writer.add_label(
        _point(m.alignment, la_station, w_offset),
        f"LA = {_feet(m.LA)}",
        _upright_angle(la_tx, la_ty),
        (side * -la_ty * 5.0, side * la_tx * 5.0),
        auto_leader=False,
    )

    outermost = max(road_edge + m.LA, abs(gating_shoulder_offset))
    band = side * (outermost + 18.0)
    _dimension(writer, m.alignment, at(0), at(overall), band, f"{overall_letter} = {_feet(overall)}")
    _dimension(writer, m.alignment, at(m.L1), at(normal_end), band + side * 9, f"{normal_letter} = {_feet(normal)}")
    _dimension(writer, m.alignment, at(normal_end), at(terminal_end), band + side * 18, f"TERMINAL = {_feet(m.terminal)}")
    _dimension(writer, m.alignment, at(terminal_end), at(gate_end), band + side * 27, f"GATING = {_feet(GATING_LENGTH)}")
    _dimension(
        writer, m.alignment, at(clear_zone_join_distance), at(gate_end),
        band + side * 36, f"CZ = {_feet(SHOULDER_FLARE_LENGTH)}",
    )
    _dimension(
        writer, m.alignment, at(gate_end), at(gate_end + SHOULDER_TRANSITION_LENGTH),
        band + side * 45, f"SHLDR = {_feet(SHOULDER_TRANSITION_LENGTH)}",
    )


def export_guardrail_dxf(path: str | Path, model: DrawingModel) -> DxfWriter:
    validate_model(model); w = DxfWriter()
    approach_extent = GATING_LENGTH + SHOULDER_TRANSITION_LENGTH + NORMAL_SHOULDER_EXTENSION
    start_extent = model.bridge_start - max(model.A, model.C) - approach_extent
    end_extent = model.bridge_end + max(model.A, model.C) + approach_extent
    half_road = model.lane_width if model.facility == "two_lane_two_way" else model.lane_width * model.lanes_this + model.median_width / 2

    w.add_polyline(_path(model.alignment, start_extent, end_extent, 0.0), LAYERS["alignment"])
    road_offsets = [-half_road, half_road]
    for offset in road_offsets: w.add_polyline(_path(model.alignment, start_extent, end_extent, offset), LAYERS["road"])
    if model.facility == "two_lane_two_way":
        # The alignment is the two-lane roadway centerline; add it to the lane-line layer as well.
        w.add_polyline(_path(model.alignment, start_extent, end_extent, 0.0), LAYERS["lane"])
    else:
        for i in range(1, model.lanes_this):
            for side in (-1, 1): w.add_polyline(_path(model.alignment, start_extent, end_extent, side * (model.median_width / 2 + i * model.lane_width)), LAYERS["lane"])
        for side in (-1, 1): w.add_polyline(_path(model.alignment, start_extent, end_extent, side * model.median_width / 2), LAYERS["lane"])

    # Bridge outline and end pavement rails.
    for offset in road_offsets: w.add_polyline(_path(model.alignment, model.bridge_start, model.bridge_end, offset), LAYERS["bridge"])
    for station in (model.bridge_start, model.bridge_end): w.add_line(_point(model.alignment, station, -half_road), _point(model.alignment, station, half_road), LAYERS["bridge"])
    annotation_edge = half_road + max(model.LA, model.L2 + SHOULDER_CLEARANCE_BEHIND_RAIL)
    for station, name in ((model.bridge_start, "BR START"), (model.bridge_end, "BR END")):
        if hasattr(model.alignment, "station_label"):
            label = f"{name} {model.alignment.station_label(station)}"
        else:
            # Standalone coordinates are only internal model-space placement
            # values, not civil stations meaningful to the user.
            label = name
        _callout(
            w, model.alignment, station, -half_road, -(annotation_edge + 72.0),
            label,
        )

    ends = ((model.bridge_start, -1.0), (model.bridge_end, 1.0))
    for bridge_station, outward in ends:
        _installation(w, model, bridge_station, outward, 1.0, half_road, model.A, model.B, "A", "B")
        if model.facility == "two_lane_two_way":
            _installation(w, model, bridge_station, outward, -1.0, half_road, model.C, model.D, "C", "D")
        else:
            # GR-4 A/B only; inside/outside selects the median-side 25:1 treatment.
            if model.divided_layout == "outside":
                median_offset = -model.median_width / 2
                taper_end = bridge_station + outward * min(model.A, 25.0 * max(2.0, model.L2))
                w.add_polyline(_taper_path(model.alignment, bridge_station, taper_end, median_offset, median_offset - 2.0), LAYERS["shoulder"])
        mid = bridge_station + outward * min(80.0, model.A / 2)
        _arrow(w, model.alignment, mid, model.lane_width / 2, -outward)
        _arrow(w, model.alignment, mid, -model.lane_width / 2, outward)

    mid_bridge = (model.bridge_start + model.bridge_end) / 2
    tx, ty = model.alignment.tangent_at_station(mid_bridge)
    title = "GR-4A - 2-LANE, 2-WAY" if model.facility == "two_lane_two_way" else f"GR-4 - DIVIDED / {model.divided_layout.upper()} CLEAR ZONE"
    w.add_label(_point(model.alignment, mid_bridge, annotation_edge + 72.0), title, _upright_angle(tx, ty))
    if model.project or model.route: w.add_label(_point(model.alignment, mid_bridge, annotation_edge + 81.0), f"{model.project} | {model.route}".strip(" |"), _upright_angle(tx, ty))
    w.save(path, model.insunits); return w
