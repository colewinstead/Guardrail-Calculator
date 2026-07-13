import math
import tempfile
import unittest
from pathlib import Path

import guardrail_dxf as dxf
import guardrail_landxml as landxml


def model(facility="two_lane_two_way", alignment=None, **changes):
    values = dict(facility=facility, bridge_start=400.0, bridge_end=500.0,
                  alignment=alignment or dxf.LineAlignment(0.0, 900.0), A=143.145833, B=100.0,
                  C=68.145833, D=25.0, L1=dxf.BRIDGE_END_SECTION, terminal=25.0,
                  L2=10.0, LA=30.0, lane_width=12.0, lanes_this=2,
                  lanes_opposing=2, median_width=40.0, flare_rate=30.0,
                  divided_layout="outside", project="QA", route="SR 8")
    values.update(changes)
    return dxf.DrawingModel(**values)


def landxml_text(unit="foot", extra="", alignments=None):
    body = alignments or '''
    <Alignment name="Main" staStart="0"><CoordGeom>
      <Line length="1000"><Start>0 0 0</Start><End>1000 0 0</End></Line>
    </CoordGeom></Alignment>'''
    return f'''<LandXML><Units><Imperial linearUnit="{unit}"/></Units><Alignments>{body}</Alignments>{extra}</LandXML>'''


class GuardrailDxfTests(unittest.TestCase):
    def export(self, drawing):
        folder = tempfile.TemporaryDirectory(); path = Path(folder.name) / "guardrail.dxf"
        writer = dxf.export_guardrail_dxf(path, drawing)
        return folder, path.read_text("ascii"), writer

    def test_standalone_contains_complete_scaled_plan(self):
        folder, text, writer = self.export(model())
        try:
            for key, layer in dxf.LAYERS.items():
                if key != "leader": self.assertIn(layer, text)
            for label in ("A = 143.15'", "B = 100.00'", "C = 68.15'", "D = 25.00'", "GATING = 12.50'"):
                self.assertIn(label, text)
            self.assertNotIn("CLEAR-ZONE TAPER -", text)
            self.assertNotIn("TERMINAL FLARE -", text)
            self.assertNotIn("GUARDRAIL TAPER -", text)
            self.assertIn("LA = 30.00'", text)
            self.assertIn("CZ = 75.00'", text)
            self.assertIn("SHLDR = 150.00'", text)
            self.assertNotIn("W/LA =", text)
            # With a 12-ft ETL offset, L2=10 and LA=30 must land at 22 and 42 ft from centerline.
            self.assertIn("20\n22.0", text)
            self.assertIn("20\n42.0", text)
            rail_lines=[r for r in writer.records if r[0] == "LINE" and r[5] in {dxf.LAYERS["rail"], dxf.LAYERS["terminal"]}]
            shoulder_lines=[r for r in writer.records if r[0] == "LINE" and r[5] == dxf.LAYERS["shoulder"]]
            expected_rail_offset = 12.0 + 10.0 + 100.0 / 30.0
            expected_shoulder_offset = expected_rail_offset + 3.0
            terminal_rail_offset = expected_rail_offset + dxf.TERMINAL_END_LATERAL_FLARE
            gating_rail_offset = expected_rail_offset + dxf.TERMINAL_LATERAL_FLARE
            combined_length = 25.0 + dxf.GATING_LENGTH
            terminal_clearance = dxf.SHOULDER_CLEARANCE_BEHIND_RAIL + (dxf.TERMINAL_SHOULDER_CLEARANCE - dxf.SHOULDER_CLEARANCE_BEHIND_RAIL) * 25.0 / combined_length
            terminal_shoulder_offset = terminal_rail_offset + terminal_clearance
            gating_shoulder_offset = gating_rail_offset + dxf.TERMINAL_SHOULDER_CLEARANCE
            self.assertTrue(any(abs(value - expected_rail_offset) < 1e-6 for r in rail_lines for value in (r[2], r[4])))
            self.assertTrue(any(abs(value - expected_shoulder_offset) < 1e-6 for r in shoulder_lines for value in (r[2], r[4])))
            self.assertTrue(any(abs(value - terminal_rail_offset) < 1e-6 for r in rail_lines for value in (r[2], r[4])))
            self.assertTrue(any(abs(value - terminal_shoulder_offset) < 1e-6 for r in shoulder_lines for value in (r[2], r[4])))
            gating_lines=[r for r in writer.records if r[0] == "LINE" and r[5] == dxf.LAYERS["gating"]]
            self.assertTrue(any(abs(value - gating_rail_offset) < 1e-6 for r in gating_lines for value in (r[2], r[4])))
            self.assertTrue(any(abs(value - gating_shoulder_offset) < 1e-6 for r in shoulder_lines for value in (r[2], r[4])))
            normal_shoulder_offset = 12.0 + 10.0
            normal_shoulder_lines = [
                r for r in writer.records
                if r[0] == "LINE" and r[5] == dxf.LAYERS["normal_shoulder"]
            ]
            normal_shoulder_extensions = [
                r for r in normal_shoulder_lines
                if abs(abs(r[2]) - normal_shoulder_offset) < 1e-6
                and abs(abs(r[4]) - normal_shoulder_offset) < 1e-6
            ]
            self.assertEqual(len(normal_shoulder_extensions), 4)
            self.assertTrue(all(abs(r[3] - r[1]) > dxf.NORMAL_SHOULDER_EXTENSION for r in normal_shoulder_extensions))
            etl_tie_segments = [
                r for r in shoulder_lines
                if abs(abs(r[4]) - 12.0) < 1e-6
                and abs(abs(r[3] - r[1]) - dxf.SHOULDER_TRANSITION_LENGTH) < 1e-6
            ]
            self.assertEqual(len(etl_tie_segments), 4)
            clear_zone_lines = [r for r in writer.records if r[0] == "LINE" and r[5] == dxf.LAYERS["foreslope"]]
            # Full W is 12-ft ETL + 30-ft LA. The constant W segment lies beyond
            # the gating endpoint and the taper runs 75 ft back toward the bridge.
            self.assertTrue(any(abs(r[2] - 42.0) < 1e-6 and abs(r[4] - 42.0) < 1e-6 for r in clear_zone_lines))
            self.assertTrue(any(abs(abs(r[3] - r[1]) - 75.0) < 1e-6 for r in clear_zone_lines if abs(r[2] - r[4]) > 1e-6))
            la_labels = [r for r in writer.records if r[0] == "TEXT" and r[3].startswith("LA = ")]
            self.assertEqual(len(la_labels), 4)
            self.assertTrue(all(abs(r[6]) < 1e-6 for r in la_labels))
            bridge_labels = [r[3] for r in writer.records if r[0] == "TEXT" and r[3].startswith("BR ")]
            self.assertEqual(bridge_labels, ["BR START", "BR END"])
            self.assertTrue(any(r[0] == "LINE" and r[5] == dxf.LAYERS["post"] for r in writer.records))
            for i, box in enumerate(writer.text_boxes):
                self.assertFalse(any(writer.boxes_overlap(box, other) for other in writer.text_boxes[i + 1:]))
        finally: folder.cleanup()

    def test_divided_gr4_draws_ab_only_and_layout(self):
        folder, text, _ = self.export(model("divided_highway"))
        try:
            self.assertIn("GR-4 - DIVIDED / OUTSIDE CLEAR ZONE", text)
            self.assertIn("A = 143.15'", text); self.assertNotIn("C = ", text)
        finally: folder.cleanup()

    def test_dxf_uses_mdot_engineering_regular_text_style(self):
        import ezdxf

        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "engineering_text.dxf"
            dxf.export_guardrail_dxf(path, model())
            document = ezdxf.readfile(path)
            style = document.styles.get(dxf.ENGINEERING_TEXT_STYLE)
            self.assertEqual(style.dxf.font, dxf.ENGINEERING_FONT_FILE)
            self.assertTrue(style.has_extended_font_data)
            self.assertEqual(
                style.get_extended_font_data(),
                (dxf.ENGINEERING_TEXT_STYLE, False, False),
            )
            text_entities = list(document.modelspace().query("TEXT"))
            self.assertTrue(text_entities)
            self.assertTrue(
                all(entity.dxf.style == dxf.ENGINEERING_TEXT_STYLE for entity in text_entities)
            )
            dimension_prefixes = ("A =", "B =", "C =", "D =", "TERMINAL =", "GATING =", "CZ =", "SHLDR =")
            dimension_text = [
                entity for entity in text_entities
                if entity.dxf.text.startswith(dimension_prefixes)
            ]
            self.assertTrue(dimension_text)
            self.assertTrue(all(entity.dxf.halign == 1 for entity in dimension_text))
            self.assertTrue(all(entity.dxf.valign == 2 for entity in dimension_text))
            self.assertEqual(document.layers.get(dxf.LAYERS["shoulder"]).dxf.linetype, "CONTINUOUS")
            self.assertEqual(document.layers.get(dxf.LAYERS["normal_shoulder"]).dxf.linetype, "DASHED")

    def test_rejects_insufficient_alignment_and_bad_widths(self):
        with self.assertRaisesRegex(ValueError, "before bridge start"):
            dxf.validate_model(model(alignment=dxf.LineAlignment(300, 900)))
        with self.assertRaisesRegex(ValueError, "greater than or equal"):
            dxf.validate_model(model(L2=35, LA=30))

    def test_landxml_lists_multiple_alignments_and_places_stations(self):
        xml = landxml_text(alignments='''
          <Alignment name="Main" staStart="100"><CoordGeom><Line length="1000"><Start>500 1000 0</Start><End>1500 1000 0</End></Line></CoordGeom></Alignment>
          <Alignment name="Ramp" staStart="0"><CoordGeom><Line length="500"><Start>0 0 0</Start><End>0 500 0</End></Line></CoordGeom></Alignment>''')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"a.xml"; path.write_text(xml)
            alignments=landxml.load_alignments(path)
        self.assertEqual([a.name for a in alignments], ["Main", "Ramp"])
        self.assertEqual(alignments[0].xy_at_station(350), (1000.0, 750.0))
        self.assertEqual(alignments[1].tangent_at_station(100), (1.0, 0.0))

    def test_landxml_overlay_exports_in_project_coordinates(self):
        xml = landxml_text(alignments='''<Alignment name="Main" staStart="0"><CoordGeom>
          <Line length="1200"><Start>5000 10000 0</Start><End>6200 10000 0</End></Line>
          </CoordGeom></Alignment>''')
        with tempfile.TemporaryDirectory() as folder:
            xml_path=Path(folder)/"main.xml"; xml_path.write_text(xml)
            alignment=landxml.load_alignments(xml_path)[0]
            drawing=model(alignment=alignment, bridge_start=400, bridge_end=500, insunits=21)
            dxf_path=Path(folder)/"overlay.dxf"; dxf.export_guardrail_dxf(dxf_path, drawing)
            import ezdxf
            document=ezdxf.readfile(dxf_path)
            bridge_lines=[e for e in document.modelspace().query("LINE") if e.dxf.layer == dxf.LAYERS["bridge"]]
            coordinates={(round(e.dxf.start.x,3),round(e.dxf.start.y,3)) for e in bridge_lines}
            bridge_labels={e.dxf.text for e in document.modelspace().query("TEXT") if e.dxf.text.startswith("BR ")}
            self.assertEqual(document.header["$INSUNITS"], 21)
        self.assertIn((9988.0, 5400.0), coordinates)
        self.assertIn((10012.0, 5500.0), coordinates)
        self.assertEqual(bridge_labels, {"BR START 4+00.000", "BR END 5+00.000"})

    def test_landxml_circular_arc(self):
        xml = landxml_text(alignments=f'''<Alignment name="Arc" staStart="0"><CoordGeom>
          <Curve length="{math.pi*50}" radius="50" rot="ccw"><Start>0 50 0</Start><Center>0 0 0</Center><End>0 -50 0</End></Curve>
          </CoordGeom></Alignment>''')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"arc.xml"; path.write_text(xml); alignment=landxml.load_alignments(path)[0]
        x,y=alignment.xy_at_station(math.pi*25); self.assertAlmostEqual(x,0,5); self.assertAlmostEqual(y,50,5)

    def test_landxml_rejects_metric_and_spirals(self):
        cases = [
            (landxml_text(unit="meter"), "must use feet"),
            (landxml_text(alignments='<Alignment name="A"><CoordGeom><Spiral length="10"/></CoordGeom></Alignment>'), "spirals"),
        ]
        for xml, message in cases:
            with self.subTest(message=message), tempfile.TemporaryDirectory() as folder:
                path=Path(folder)/"bad.xml"; path.write_text(xml)
                with self.assertRaisesRegex(ValueError, message): landxml.load_alignments(path)

    def test_station_equations_map_civil_and_region_stationing(self):
        xml = landxml_text(alignments='''<Alignment name="Eq" staStart="0">
          <StaEquation staInternal="1000" staBack="1000" staAhead="500"/>
          <CoordGeom><Line length="2000"><Start>0 0</Start><End>0 2000</End></Line></CoordGeom>
          </Alignment>''')
        with tempfile.TemporaryDirectory() as folder:
            path=Path(folder)/"eq.xml"; path.write_text(xml); alignment=landxml.load_alignments(path)[0]
        self.assertEqual(len(alignment.station_equations), 1)
        self.assertAlmostEqual(alignment.civil_to_internal("7+00R2"), 1200.0)
        self.assertAlmostEqual(alignment.internal_to_civil(1200.0), 700.0)
        self.assertEqual(alignment.station_label(1200.0), "7+00.000R2")
        self.assertEqual(alignment.civil_region_labels(), ["0+00.000 to 10+00.000", "5+00.000R2 to 15+00.000R2"])
        self.assertAlmostEqual(alignment.xy_at_station(alignment.civil_to_internal("7+00R2"))[0], 1200.0)
        with self.assertRaisesRegex(ValueError, "Valid civil-station regions"):
            alignment.civil_to_internal("20+00")


if __name__ == "__main__": unittest.main()
