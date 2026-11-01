"""Characterization captured from corrected baseline a280080, not MDOT approval."""

import hashlib
import itertools
import json
from io import BytesIO, StringIO
from contextlib import redirect_stdout
from pathlib import Path
import tempfile
import unittest
from dataclasses import FrozenInstanceError, replace
import subprocess
import sys
from unittest.mock import patch

from pypdf import PdfReader
import guardrail_dxf as dxf
import guardrail_landxml as landxml
from test_guardrail_app import app
from test_guardrail_dxf import model
from test_guardrail_phase2 import circular_alignment
from guardrail_design import Facility, DividedLayout, PlacementMode, ReportStyle
from guardrail_models import (
    CalculationInputs, HazardBarrierInputs, ProjectMetadata, ReportModel,
    AlignmentSelection, DrawingExportConfiguration,
)
from guardrail_engine import calculate, create_snapshot
from guardrail_drawing import build_drawing, drawing_inputs, LineEntity, TextEntity
from guardrail_pdf import render_report
from guardrail_report import report_payload
from guardrail_validation import create_roadway

FIXTURE = json.loads(Path(__file__).with_name("test_fixtures").joinpath("phase3_baseline.json").read_text())


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def engineering_cases():
    return itertools.product((30, 35, 40, 45, 50, 55, 60, 65, 70),
        (0, 749, 750, 1000, 1500, 5000, 6000, 10000),
        ((30, 10, 22), (28, 10, 22), (5, 10, 22)),
        (0, app.DEFAULT_L1_FT), (0, 25), (0, 13, 30))


class BaselineCharacterizationTests(unittest.TestCase):
    def test_all_2592_engineering_outputs(self):
        results = [app.compute_guardrail_outputs(speed, adt, *geometry, L1, terminal, flare)
                   for speed, adt, geometry, L1, terminal, flare in engineering_cases()]
        self.assertEqual(len(results), 2592)
        self.assertEqual(digest(results), FIXTURE["engineering"])

    def test_typed_engine_has_same_2592_outputs(self):
        outputs = []
        for speed, adt, (LA, L2, L2_opp), L1, terminal, flare in engineering_cases():
            road = create_roadway(Facility.TWO_LANE_TWO_WAY, L2, L2_opp - L2)
            inputs = CalculationInputs(speed, adt, road, HazardBarrierInputs(LA, L1, terminal, flare))
            outputs.append(calculate(inputs).as_dict())
        self.assertEqual(len(outputs), 2592)
        self.assertEqual(digest(outputs), FIXTURE["engineering"])

    def test_report_payload_and_pdf_layout_for_all_styles(self):
        for facility, style, flare in itertools.product(
                ("two_lane_two_way", "divided_highway"), (1, 2, 3), (0, 30)):
            key = f"{facility}-{style}-{flare}"
            with self.subTest(case=key):
                results = app.compute_guardrail_outputs(65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, flare)
                data = app.build_pdf_data("A <b>B</b> & C", facility, 65, 6000, 30, 10, 22, 12,
                    app.DEFAULT_L1_FT, 25, flare, style, results, generated_time="2026-10-01 12:00",
                    route_location="SR 8", job_number="123", prepared_by="Author", checked_by="Reviewer",
                    calculation_date="2026-10-01")
                self.assertEqual(digest(data), FIXTURE["reports"][key]["payload"])
                buffer = BytesIO()
                app.generate_pdf_calc_sheet(buffer, data)
                pages = [{"box": list(page.mediabox),
                          "stream": hashlib.sha256(page.get_contents().get_data()).hexdigest(),
                          "text": hashlib.sha256(page.extract_text().encode()).hexdigest()}
                         for page in PdfReader(buffer).pages]
                self.assertEqual(pages, FIXTURE["reports"][key]["pages"])

    def test_straight_and_curved_drawing_fingerprints_for_both_layouts(self):
        with tempfile.TemporaryDirectory() as folder:
            for facility, layout, curve in itertools.product(
                    ("two_lane_two_way", "divided_highway"), ("inside", "outside"), ("line", "ccw", "cw")):
                key = f"{facility}-{layout}-{curve}"
                with self.subTest(case=key):
                    alignment = dxf.LineAlignment(0, 900) if curve == "line" else circular_alignment()
                    if curve == "cw":
                        arc = alignment.segments[0]
                        alignment = landxml.Alignment("CW", 0, [landxml.Arc(
                            arc.start, (arc.end[0], -arc.end[1]), (arc.center[0], -arc.center[1]),
                            arc.radius, arc.length, "cw")])
                    writer = dxf.export_guardrail_dxf(Path(folder) / "plan.dxf",
                        model(facility, divided_layout=layout, alignment=alignment))
                    records = [[round(v, 8) if isinstance(v, float) else v for v in row] for row in writer.records]
                    self.assertEqual({"count": len(records), "hash": digest(records)}, FIXTURE["drawings"][key])


class ResponsibilityBoundaryTests(unittest.TestCase):
    def snapshot(self):
        road = create_roadway(Facility.TWO_LANE_TWO_WAY, 10, 12)
        return create_snapshot(ProjectMetadata("QA", "SR 8", calculation_date="2026-10-01"),
            CalculationInputs(65, 6000, road, HazardBarrierInputs(30, app.DEFAULT_L1_FT, 25, 30)))

    def config(self):
        return DrawingExportConfiguration(
            AlignmentSelection(PlacementMode.STANDALONE, dxf.LineAlignment(0, 900), 400, 500),
            DividedLayout.OUTSIDE)

    def test_engine_imports_without_ui_or_output_dependencies(self):
        script = """
import builtins
original = builtins.__import__
blocked = {'tkinter', 'reportlab', 'pypdf', 'ezdxf', 'guardrail_pdf', 'guardrail_dxf', 'guardrail_ui'}
def restricted(name, *args, **kwargs):
    if name.split('.')[0] in blocked:
        raise AssertionError('Forbidden calculation dependency: ' + name)
    return original(name, *args, **kwargs)
builtins.__import__ = restricted
from guardrail_engine import calculate
from guardrail_design import Facility
from guardrail_models import CalculationInputs, HazardBarrierInputs
from guardrail_validation import create_roadway
road = create_roadway(Facility.TWO_LANE_TWO_WAY, 10, 12)
assert calculate(CalculationInputs(65,6000,road,HazardBarrierInputs(30,18.145833333333332,25,30))).B == 112.5
"""
        result = subprocess.run([sys.executable, "-B", "-c", script],
                                capture_output=True, text=True, cwd=Path(__file__).parent)
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_snapshot_is_immutable_and_numeric(self):
        snapshot = self.snapshot()
        for obj, field, value in ((snapshot.project, "project", "other"),
                                  (snapshot.inputs, "adt", 0),
                                  (snapshot.inputs.roadway, "L2", 0),
                                  (snapshot.inputs.barrier, "LA", 0),
                                  (snapshot.result, "A", 0)):
            with self.subTest(field=field), self.assertRaises(FrozenInstanceError):
                setattr(obj, field, value)
        self.assertTrue(all(isinstance(value, (int, float)) for value in snapshot.result.as_dict().values()))

    def test_report_and_drawing_do_not_recalculate_engineering_values(self):
        snapshot = self.snapshot()
        with patch("guardrail_engine.compute_guardrail_outputs", side_effect=AssertionError("Recalculation")):
            payload = report_payload(ReportModel(snapshot, ReportStyle.COMPLETE, "2026-10-01 12:00"))
            inputs = drawing_inputs(snapshot, self.config())
            drawing = build_drawing(inputs)
        self.assertEqual(payload["A (near) (ft)"], f"{snapshot.result.A:.4f}")
        self.assertEqual(inputs.A, snapshot.result.A)
        self.assertTrue(drawing.entities)
        self.assertTrue(all(isinstance(entity, (LineEntity, TextEntity)) for entity in drawing.entities))

    def test_drawing_generation_does_not_need_ezdxf_or_filesystem(self):
        snapshot = self.snapshot()
        with patch("guardrail_dxf.serialize_dxf", side_effect=AssertionError("Serialization")):
            scene = build_drawing(drawing_inputs(snapshot, self.config()))
        self.assertIsInstance(scene.entities, tuple)
        with self.assertRaises(FrozenInstanceError):
            scene.entities[0].x1 = 0

    def test_direct_typed_roadway_cannot_supply_conflicting_opposing_offset(self):
        snapshot = self.snapshot()
        road = replace(snapshot.inputs.roadway, L2_opp=999)
        with self.assertRaisesRegex(ValueError, "authoritative roadway"):
            calculate(replace(snapshot.inputs, roadway=road))

    def test_typed_report_preserves_legacy_pdf_page_streams(self):
        snapshot = self.snapshot()
        report = ReportModel(snapshot, ReportStyle.COMPLETE, "2026-10-01 12:00")
        typed, compatible = BytesIO(), BytesIO()
        render_report(typed, report)
        app.generate_pdf_calc_sheet(compatible, report_payload(report))
        self.assertEqual([p.get_contents().get_data() for p in PdfReader(typed).pages],
                         [p.get_contents().get_data() for p in PdfReader(compatible).pages])

    def test_compatibility_records_are_derived_from_typed_entities(self):
        writer = dxf.DxfWriter()
        writer.add_line((0, 0), (10, 0), "TEST")
        self.assertIsInstance(writer.entities[0], LineEntity)
        self.assertEqual(writer.records[0], ("LINE", 0, 0, 10, 0, "TEST"))
        records = writer.records
        records.clear()
        self.assertEqual(len(writer.entities), 1)
        self.assertEqual(len(writer.records), 1)

    def test_optional_console_entry_point_remains_available(self):
        answers = ["Console", "1", "65", "6,000", "2", "30", "10", "12", "1", "1", "30", "n"]
        output = StringIO()
        with patch("builtins.input", side_effect=answers), redirect_stdout(output):
            app.main()
        self.assertIn("A (near) = B + L1 + terminal: 155.6458 ft", output.getvalue())
        self.assertIn("C (opp)  = D + L1 + terminal: 68.1458 ft", output.getvalue())


if __name__ == "__main__":
    unittest.main()
