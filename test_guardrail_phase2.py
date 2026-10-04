"""Regression coverage for the second, limited software-correction phase."""

import hashlib
import json
import math
import tempfile
import unittest
from dataclasses import replace
from io import BytesIO
from pathlib import Path

import guardrail_dxf as dxf
import guardrail_landxml as landxml
import guardrail_validation as validation
from test_guardrail_app import app, pdf_data
from test_guardrail_dxf import model


def circular_alignment(radius=1000):
    length = 1800.0
    end = (radius * math.sin(length / radius), radius * (1 - math.cos(length / radius)))
    return landxml.Alignment("Curve", 0, [landxml.Arc((0, 0), end, (0, radius), radius, length, "ccw")])


class DrawingGeometryTests(unittest.TestCase):
    def test_straight_drawing_records_remain_identical(self):
        hashes = {
            "two_lane_two_way": "f61574e47d834e42b5e063adc99a885bebe4639e899ccf97c93d7b5b363ebabf",
            "divided_highway": "99764fb68b3be326ae7e0fbd2541b026f514a35c91ee5f1c3f7019215648a3c1",
        }
        with tempfile.TemporaryDirectory() as folder:
            for facility, expected in hashes.items():
                with self.subTest(facility=facility):
                    writer = dxf.export_guardrail_dxf(Path(folder) / "plan.dxf", model(facility))
                    records = [[round(v, 8) if isinstance(v, float) else v for v in row] for row in writer.records]
                    self.assertEqual(hashlib.sha256(json.dumps(records).encode()).hexdigest(), expected)

    def test_curved_features_follow_alignment_within_tolerance(self):
        alignment = circular_alignment()
        with tempfile.TemporaryDirectory() as folder:
            writer = dxf.export_guardrail_dxf(Path(folder) / "curve.dxf", model(alignment=alignment))
        layers = {dxf.LAYERS[key] for key in ("shoulder", "normal_shoulder", "foreslope", "rail", "terminal", "gating")}
        checked = {layer: 0 for layer in layers}
        for record in writer.records:
            if record[0] != "LINE" or record[5] not in layers:
                continue
            _, x1, y1, x2, y2, layer = record
            stations = [1000 * (math.atan2(y - 1000, x) + math.pi / 2) for x, y in [(x1, y1), (x2, y2)]]
            offsets = [1000 - math.hypot(x, y - 1000) for x, y in [(x1, y1), (x2, y2)]]
            station, offset = sum(stations) / 2, sum(offsets) / 2
            expected = dxf._point(alignment, station, offset)
            actual = ((x1 + x2) / 2, (y1 + y2) / 2)
            self.assertLessEqual(math.dist(expected, actual), 0.01001, (layer, record))
            checked[layer] += 1
        self.assertTrue(all(checked.values()), checked)

    def test_sampling_includes_alignment_breakpoints(self):
        radius, arc_length = 1000, 300
        alignment = landxml.Alignment("Joined", 0, [
            landxml.Line((0, 0), (300, 0), 300),
            landxml.Arc((300, 0), (300 + radius * math.sin(.3), radius * (1 - math.cos(.3))),
                        (300, radius), radius, arc_length, "ccw"),
        ])
        points = dxf._path(alignment, 100, 550, 5, step=200)
        self.assertIn((300, 5), points)

    def test_clockwise_variable_offsets_refine_coarse_sampling_in_both_directions(self):
        radius, length = 1000, 1000
        alignment = landxml.Alignment("CW", 0, [landxml.Arc(
            (0, 0), (radius * math.sin(1), -radius * (1 - math.cos(1))),
            (0, -radius), radius, length, "cw",
        )])
        for start, end in ((0, length), (length, 0)):
            points = dxf._path(alignment, start, end, lambda station: 5 + station / 100, count=1)
            self.assertGreater(len(points), 2)
            self.assertEqual(points[0], dxf._point(alignment, start, 5 + start / 100))
            self.assertEqual(points[-1], dxf._point(alignment, end, 5 + end / 100))
            for a, b in zip(points, points[1:]):
                stations = [radius * math.atan2(x, y + radius) for x, y in (a, b)]
                station = sum(stations) / 2
                actual = tuple((x + y) / 2 for x, y in zip(a, b))
                self.assertLessEqual(math.dist(actual, dxf._point(alignment, station, 5 + station / 100)), .01001)

    def test_nonfinite_alignment_coordinates_are_rejected_before_writing(self):
        class InvalidAlignment(dxf.LineAlignment):
            def xy_at_station(self, station):
                return math.nan, 0
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "invalid.dxf"
            with self.assertRaisesRegex(ValueError, "finite"):
                dxf.export_guardrail_dxf(path, model(alignment=InvalidAlignment(0, 1000)))
            self.assertFalse(path.exists())

    def test_dimensions_keep_station_distance_labels(self):
        alignment = circular_alignment()
        writer = dxf.DxfWriter()
        dxf._dimension(writer, alignment, 100, 250, 20, "B = 150.00'")
        self.assertIn("B = 150.00'", [r[3] for r in writer.records if r[0] == "TEXT"])
        baseline = writer.records[0]
        self.assertLess(math.hypot(baseline[3] - baseline[1], baseline[4] - baseline[2]), 150)

    def test_default_short_taper_is_rejected_before_writing(self):
        results = app.compute_guardrail_outputs(60, 6000, 28, 10, 22, app.DEFAULT_L1_FT, 25, 30)
        drawing = model(**{key: results[key] for key in ("A", "B", "C", "D")}, LA=28)
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "short.dxf"
            with self.assertRaisesRegex(ValueError, "insufficient.*75"):
                dxf.export_guardrail_dxf(path, drawing)
            self.assertFalse(path.exists())

    def test_zero_terminal_calculation_is_allowed_but_dxf_is_rejected(self):
        results = app.compute_guardrail_outputs(65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 0, 30)
        drawing = model(**{key: results[key] for key in ("A", "B", "C", "D")}, terminal=0)
        with self.assertRaisesRegex(ValueError, "terminal.*greater than zero"):
            dxf.validate_model(drawing)

    def test_inconsistent_models_and_invalid_numeric_fields(self):
        for field, value in [
            ("A", 140), ("C", 90), ("B", -1), ("L1", -1), ("terminal", -1),
            ("median_width", -1), ("flare_rate", -1), ("lanes_this", 1.5),
            ("lanes_opposing", 0), ("lane_width", 0), ("bridge_start", math.nan),
            ("LA", math.inf), ("D", math.nan), ("facility", "unknown"),
        ]:
            with self.subTest(field=field, value=value), self.assertRaises(ValueError):
                dxf.validate_model(replace(model(), **{field: value}))


class BasicValidationTests(unittest.TestCase):
    def test_negative_inputs_are_rejected_by_engine_and_pdf_payload(self):
        for index in (1, 2, 3, 4, 5, 6, 7):
            inputs = [65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, 30]
            inputs[index] = -1
            with self.subTest(index=index), self.assertRaises(ValueError):
                app.compute_guardrail_outputs(*inputs)
        data = pdf_data()
        for field, value in [("Design ADT", "-1"), ("LA (ft)", "0"),
                             ("Lane width (ft)", "-1"), ("A (near) (ft)", "nan"),
                             ("Terminal section (ft)", "inf")]:
            with self.subTest(field=field), self.assertRaises(ValueError):
                app.generate_pdf_calc_sheet(BytesIO(), dict(data, **{field: value}))

    def test_direct_helpers_reject_nonfinite_and_negative_adt(self):
        for value in (-1, math.nan, math.inf):
            for function in (app.adt_bucket_index, app.adt_group_clearzone):
                with self.subTest(function=function.__name__, value=value), self.assertRaises(ValueError):
                    function(value)

    def test_direct_calculation_and_pdf_builder_reject_invalid_data(self):
        for invalid in (-1, math.nan, math.inf):
            with self.subTest(value=invalid), self.assertRaises(ValueError):
                app.compute_x_min(65, invalid, 30, 10, app.DEFAULT_L1_FT, 30)
        outputs = app.compute_guardrail_outputs(65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, 30)
        for name, value in (("A", -1), ("D", math.nan), ("LR", math.inf), ("A", 140)):
            with self.subTest(field=name), self.assertRaises(ValueError):
                app.build_pdf_data("QA", "two_lane_two_way", 65, 6000, 30, 10, 22, 12,
                                   app.DEFAULT_L1_FT, 25, 30, 1, dict(outputs, **{name: value}))
        with self.assertRaisesRegex(ValueError, "A must equal"):
            app.generate_pdf_calc_sheet(BytesIO(), dict(pdf_data(), **{"A (near) (ft)": "140"}))
        with self.assertRaisesRegex(ValueError, "speed"):
            app.compute_guardrail_outputs(64, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, 30)

    def test_finite_inputs_that_overflow_are_rejected(self):
        with self.assertRaisesRegex(ValueError, "finite"):
            app.compute_guardrail_outputs(65, 6000, 1e-300, 1e300, 22, app.DEFAULT_L1_FT, 25, 0)
        with self.assertRaisesRegex(ValueError, "finite"):
            validation.roadway_inputs("divided_highway", 10, 1e308, 2, 2, 40)

    def test_lane_counts_are_whole_positive_numbers(self):
        for value in (0, -1, 1.5, math.nan, math.inf, True):
            with self.subTest(value=value), self.assertRaises(ValueError):
                validation.roadway_inputs("divided_highway", 10, 12, value, 2, 40)

    def test_la_below_l2_stays_mathematically_supported(self):
        outputs = app.compute_guardrail_outputs(60, 6000, 5, 10, 22, app.DEFAULT_L1_FT, 25, 30)
        data = app.build_pdf_data("QA", "two_lane_two_way", 60, 6000, 5, 10, 22, 12,
                                  app.DEFAULT_L1_FT, 25, 30, 1, outputs)
        app.generate_pdf_calc_sheet(BytesIO(), data)
        self.assertTrue(math.isfinite(outputs["A"]))

    def test_derived_roadway_changes_keep_calculation_and_drawing_consistent(self):
        for median in (40, 60):
            roadway = validation.roadway_inputs("divided_highway", 10, 12, 2, 2, median)
            validation.require_drawing_crossing(roadway)
            self.assertEqual(roadway["added_distance"], 48 + median)
            self.assertEqual(roadway["L2_opp"], 58 + median)

    def test_manual_crossing_is_not_silently_reinterpreted(self):
        roadway = validation.roadway_inputs("divided_highway", 10, 12, 2, 2, 60, added_distance=88)
        self.assertEqual(roadway["L2_opp"], 98)
        with self.assertRaisesRegex(ValueError, "opposing distance disagrees"):
            validation.require_drawing_crossing(roadway)


class LandxmlImportTests(unittest.TestCase):
    def load(self, alignments, **kwargs):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "alignments.xml"
            path.write_text('<LandXML><Units><Imperial linearUnit="foot"/></Units><Alignments>'
                            + alignments + '</Alignments></LandXML>', encoding="utf-8")
            return landxml.load_alignments(path, **kwargs)

    def test_unknown_element_never_produces_partial_alignment(self):
        bad = ('<Alignment name="Bad"><CoordGeom><Line length="10"><Start>0 0</Start>'
               '<End>0 10</End></Line><UnknownCurve length="5"/></CoordGeom></Alignment>')
        with self.assertRaisesRegex(ValueError, "Bad.*UnknownCurve"):
            self.load(bad)

    def test_valid_alignments_survive_individual_rejections_with_diagnostics(self):
        valid = ('<Alignment name="Good"><CoordGeom><Line length="1000"><Start>0 0</Start>'
                 '<End>0 1000</End></Line></CoordGeom></Alignment>')
        bad = '<Alignment name="SpiralRoute"><CoordGeom><Spiral length="20"/></CoordGeom></Alignment>'
        rejected = []
        alignments = self.load(valid + bad, rejected_alignments=rejected)
        self.assertEqual([alignment.name for alignment in alignments], ["Good"])
        self.assertEqual(len(rejected), 1)
        self.assertIn("SpiralRoute", rejected[0])
        self.assertIn("Spiral", rejected[0])

    def test_all_rejected_alignments_report_their_errors(self):
        bad = '<Alignment name="SpiralRoute"><CoordGeom><Spiral/></CoordGeom></Alignment>'
        with self.assertRaisesRegex(ValueError, "SpiralRoute.*Spiral"):
            self.load(bad, rejected_alignments=[])

    def test_invalid_alignment_is_rejected_whole_beside_valid_geometry(self):
        line = '<Line length="100"><Start>0 0</Start><End>0 100</End></Line>'
        valid = '<Alignment name="Good"><CoordGeom>' + line + '</CoordGeom></Alignment>'
        invalid = '<Alignment name="Partial"><CoordGeom>' + line + '<UnknownCurve/></CoordGeom></Alignment>'
        rejected = []
        self.assertEqual([a.name for a in self.load(valid + invalid, rejected_alignments=rejected)], ["Good"])
        self.assertIn("Partial", rejected[0])
        self.assertIn("UnknownCurve", rejected[0])


if __name__ == "__main__":
    unittest.main()
