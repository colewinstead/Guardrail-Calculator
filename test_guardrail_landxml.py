"""Regression tests for LandXML rotation, station ambiguity, and geometry validation."""

import math
import tempfile
import unittest
from pathlib import Path

import guardrail_landxml as landxml


def load_geometry(geometry, start="0", equations=""):
    text = (
        '<LandXML><Units><Imperial linearUnit="foot"/></Units><Alignments>'
        f'<Alignment name="Regression" staStart="{start}">{equations}'
        f'<CoordGeom>{geometry}</CoordGeom></Alignment></Alignments></LandXML>'
    )
    with tempfile.TemporaryDirectory() as folder:
        path = Path(folder) / "alignment.xml"
        path.write_text(text, encoding="utf-8")
        return landxml.load_alignments(path)[0]


def line(length="1000", start="0 0", end="0 1000"):
    return f'<Line length="{length}"><Start>{start}</Start><End>{end}</End></Line>'


def arc(rotation="ccw", length=None, radius="50", start="0 50", end="0 -50", center="0 0"):
    length = str(math.pi * 50) if length is None else length
    return (
        f'<Curve length="{length}" radius="{radius}" rot="{rotation}">'
        f'<Start>{start}</Start><Center>{center}</Center><End>{end}</End></Curve>'
    )


class ArcRotationTests(unittest.TestCase):
    def test_semicircle_respects_declared_rotation_and_tangent(self):
        for rotation, y, start_tangent in [("cw", -50, (0, -1)), ("ccw", 50, (0, 1))]:
            with self.subTest(rotation=rotation):
                alignment = load_geometry(arc(rotation))
                x_mid, y_mid = alignment.xy_at_station(math.pi * 25)
                self.assertAlmostEqual(x_mid, 0)
                self.assertAlmostEqual(y_mid, y)
                tx, ty = alignment.tangent_at_station(math.pi * 25)
                self.assertAlmostEqual(tx, -1)
                self.assertAlmostEqual(ty, 0)
                tx, ty = alignment.tangent_at_station(0)
                self.assertAlmostEqual(tx, start_tangent[0])
                self.assertAlmostEqual(ty, start_tangent[1])
                x_end, y_end = alignment.xy_at_station(math.pi * 50)
                self.assertAlmostEqual(x_end, -50)
                self.assertAlmostEqual(y_end, 0)

    def test_quarter_and_major_arcs(self):
        for rotation, length, end in [
            ("ccw", math.pi * 25, "50 0"), ("cw", math.pi * 25, "-50 0"),
            ("ccw", math.pi * 75, "-50 0"), ("cw", math.pi * 75, "50 0"),
        ]:
            with self.subTest(rotation=rotation, length=length):
                alignment = load_geometry(arc(rotation, str(length), end=end))
                expected = tuple(reversed([float(v) for v in end.split()]))
                actual = alignment.xy_at_station(length)
                self.assertAlmostEqual(actual[0], expected[0])
                self.assertAlmostEqual(actual[1], expected[1])

    def test_full_circle(self):
        for rotation, y in [("cw", -50), ("ccw", 50)]:
            with self.subTest(rotation=rotation):
                alignment = load_geometry(arc(rotation, str(math.tau * 50), end="0 50"))
                self.assertAlmostEqual(alignment.xy_at_station(math.pi * 25)[1], y)


class StationEquationTests(unittest.TestCase):
    def setUp(self):
        self.alignment = load_geometry(
            line("2000", end="0 2000"),
            equations='<StaEquation staInternal="1000" staBack="1000" staAhead="500"/>',
        )

    def test_ambiguous_unsuffixed_station_requires_region(self):
        with self.assertRaisesRegex(ValueError, "[Aa]mbiguous.*R1.*R2"):
            self.alignment.civil_to_internal("7+00")

    def test_explicit_and_unambiguous_stations_remain_supported(self):
        self.assertEqual(self.alignment.civil_to_internal("7+00R1"), 700)
        self.assertEqual(self.alignment.civil_to_internal("7+00R2"), 1200)
        self.assertEqual(self.alignment.civil_to_internal("2+00"), 200)
        self.assertEqual(self.alignment.civil_to_internal("12+00"), 1700)

    def test_same_internal_location_at_equation_boundary_is_not_ambiguous(self):
        alignment = load_geometry(
            line("2000", end="0 2000"),
            equations='<StaEquation staInternal="1000" staBack="1000" staAhead="1000"/>',
        )
        self.assertEqual(alignment.civil_to_internal("10+00"), 1000)

    def test_nonfinite_station_input_is_rejected(self):
        for value in ("NaN", "inf", "-inf", "1e309", math.nan, math.inf):
            with self.subTest(value=value), self.assertRaises(ValueError):
                self.alignment.civil_to_internal(value)


class GeometryValidationTests(unittest.TestCase):
    def test_invalid_line_lengths(self):
        for length in ("100", "-1000", "0", "nan", "inf", "1e309"):
            with self.subTest(length=length), self.assertRaises(ValueError):
                load_geometry(line(length))

    def test_nonfinite_and_malformed_coordinates(self):
        for point in ("nan 0", "0 inf", "0 0 nan", "0", "0 0 0 0", "bad 0", "0 1e309"):
            with self.subTest(point=point), self.assertRaises(ValueError):
                load_geometry(line(start=point))

    def test_invalid_arc_radius(self):
        for radius in ("0", "-50", "nan", "inf", "1e309"):
            with self.subTest(radius=radius), self.assertRaises(ValueError):
                load_geometry(arc(radius=radius))

    def test_inconsistent_arc_geometry(self):
        for geometry in (
            arc(length="-1"), arc(length="0"), arc(length="1"),
            arc(length=str(math.tau * 100)), arc(length="nan"),
            arc(length="inf"), arc(start="0 60"), arc(end="0 -60"),
            arc(center="nan 0"), arc(rotation="invalid"),
            arc("cw", str(math.pi * 25), end="50 0"),
        ):
            with self.subTest(geometry=geometry), self.assertRaises(ValueError):
                load_geometry(geometry)

    def test_disconnected_segments_are_rejected(self):
        with self.assertRaises(ValueError):
            load_geometry(line("10", end="0 10") + line("10", start="0 20", end="0 30"))

    def test_missing_geometry_fields_are_rejected_as_value_errors(self):
        for geometry in ('<Line length="10"><Start>0 0</Start></Line>',
                         '<Curve radius="50" length="10"><Start>0 50</Start><End>0 40</End></Curve>'):
            with self.subTest(geometry=geometry), self.assertRaises(ValueError):
                load_geometry(geometry)

    def test_nonfinite_start_station_is_rejected(self):
        for value in ("nan", "inf", "1e309"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                load_geometry(line(), start=value)

    def test_nonfinite_or_malformed_equations_are_rejected(self):
        for equation in (
            '<StaEquation staInternal="bad" staBack="1000" staAhead="500"/>',
            '<StaEquation staInternal="1000" staBack="nan" staAhead="500"/>',
            '<StaEquation staInternal="1000" staBack="1000" staAhead="inf"/>',
        ):
            with self.subTest(equation=equation), self.assertRaises(ValueError):
                load_geometry(line("2000", end="0 2000"), equations=equation)

    def test_coordinate_rounding_is_tolerated(self):
        alignment = load_geometry(
            line("10", end="0 10.000001") + line("10", start="0 10.000002", end="0 20.000002"),
        )
        self.assertEqual(alignment.station_range(), (0, 20))
        alignment = load_geometry(arc(length="157.079633"))
        self.assertAlmostEqual(alignment.xy_at_station(157.079633)[0], -50, places=5)

    def test_stationing_uses_horizontal_coordinates_with_elevation(self):
        alignment = load_geometry(line("10", start="0 0 100", end="0 10 120"))
        self.assertEqual(alignment.xy_at_station(5), (5, 0))

    def test_zero_length_coincident_line_remains_supported(self):
        alignment = load_geometry(line("0", end="0 0") + line())
        self.assertEqual(alignment.xy_at_station(100), (100, 0))


if __name__ == "__main__":
    unittest.main()
