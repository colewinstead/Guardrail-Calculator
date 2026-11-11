"""Table 12-2-B recoverable fill-slope transcription and selection regressions."""

from dataclasses import replace
from io import BytesIO
import unittest

from pypdf import PdfReader

from guardrail_design import (
    ClearZoneCriteria, ClearZoneSelection, Facility, HazardOffsetSource,
    ReportStyle, SideSlope, TABLE_12_2_B,
)
from guardrail_engine import create_snapshot, resolve_clear_zone
from guardrail_models import CalculationInputs, HazardBarrierInputs, ProjectMetadata, ReportModel
from guardrail_pdf import generate_pdf_calc_sheet
from guardrail_report import report_payload
from guardrail_validation import create_roadway


class ClearZoneTests(unittest.TestCase):
    def test_all_fill_ranges_match_mdot_2020_table_12_2_b_page_12_11(self):
        expected = {
            '40_or_less': [(3.5, 5, 3.5, 5), (5, 6, 6, 7), (6, 7, 7, 8), (7, 8, 8, 9)],
            '45_50': [(5, 6, 6, 7), (7, 8, 8, 10), (8, 9, 10, 13), (10, 11, 12, 14)],
            '55': [(6, 7, 7, 9), (8, 9, 10, 12), (10, 11, 12, 15), (11, 12, 13, 16)],
            '60': [(8, 9, 10, 12), (10, 12, 13, 16), (13, 15, 16, 20), (15, 16, 18, 22)],
            '65': [(9, 10, 10, 13), (12, 13, 14, 18), (14, 16, 17, 21), (15, 17, 19, 23)],
        }
        self.assertEqual(set(TABLE_12_2_B), set(expected))
        for speed, rows in expected.items():
            self.assertEqual(list(TABLE_12_2_B[speed]),
                             ['under_750', '750_1500', '1501_6000', 'over_6000'])
            for actual, row in zip(TABLE_12_2_B[speed].values(), rows):
                with self.subTest(speed=speed, row=row):
                    self.assertEqual(set(actual), {'6:1_or_flatter', '5:1_to_4:1'})
                    self.assertEqual(actual['6:1_or_flatter'] + actual['5:1_to_4:1'], row)

    def test_adt_boundaries_and_all_supported_speeds(self):
        for speed, expected in [(30, 3.5), (35, 3.5), (40, 3.5), (45, 5),
                                (50, 5), (55, 6), (60, 8), (65, 9)]:
            with self.subTest(speed=speed):
                self.assertEqual(resolve_clear_zone(speed, 0, '6:1_or_flatter', 'min', criteria='3r'), expected)
        for adt, expected in [(749, 8.5), (750, 11), (1500, 11), (1501, 14),
                              (6000, 14), (6001, 15.5)]:
            with self.subTest(adt=adt):
                self.assertEqual(resolve_clear_zone(60, adt, '6:1_or_flatter', 'mid', criteria='3r'), expected)

    def test_range_choices_and_original_default(self):
        self.assertEqual(resolve_clear_zone(60, 3000, '6:1_or_flatter', 'mid'), 28)
        self.assertEqual(resolve_clear_zone(70, 3000, '6:1_or_flatter', 'mid'), 30)
        for selection, expected in [('min', 16), ('mid', 18), ('max', 20), ('custom', 15)]:
            with self.subTest(selection=selection):
                self.assertEqual(resolve_clear_zone(60, 3000, '5:1_to_4:1', selection, 15, criteria='3r'), expected)

    def test_unsupported_inputs_do_not_fall_back_to_another_table(self):
        for speed in (0, 41, 55.5, 66, 70, float('nan'), float('inf')):
            for selection in ('mid', 'custom'):
                with self.subTest(speed=speed, selection=selection), self.assertRaises(ValueError):
                    resolve_clear_zone(speed, 3000, '6:1_or_flatter', selection, 15, criteria='3r')
        for kwargs in ({'criteria': 'unknown'}, {'criteria': '3r', 'slope': 'nonrecoverable'},
                       {'criteria': '3r', 'adt': -1}, {'criteria': '3r', 'selection': 'custom', 'custom_value': 0}):
            args = dict(speed=60, adt=3000, slope='6:1_or_flatter', selection='mid')
            args.update(kwargs)
            with self.subTest(kwargs=kwargs), self.assertRaises(ValueError):
                resolve_clear_zone(**args)

    def snapshot(self):
        road = create_roadway(Facility.TWO_LANE_TWO_WAY, 10, 12)
        barrier = HazardBarrierInputs(14, 18, 25, 30, HazardOffsetSource.CLEAR_ZONE,
                                      SideSlope.FLAT, ClearZoneSelection.MIDPOINT, ClearZoneCriteria.THREE_R)
        return create_snapshot(ProjectMetadata('3R example'), CalculationInputs(60, 3000, road, barrier))

    def test_snapshot_rejects_inconsistent_clear_zone_and_manual_remains_independent(self):
        snapshot = self.snapshot()
        with self.assertRaisesRegex(ValueError, 'LA disagrees'):
            create_snapshot(snapshot.project, replace(snapshot.inputs, barrier=replace(snapshot.inputs.barrier, LA=28)))
        manual = replace(snapshot.inputs.barrier, offset_source=HazardOffsetSource.DIRECT, LA=30)
        create_snapshot(snapshot.project, replace(snapshot.inputs, speed=70, barrier=manual))

    def test_all_pdf_styles_record_snapshot_criteria_and_uncapped_note(self):
        snapshot = self.snapshot()
        for style in ReportStyle:
            with self.subTest(style=style):
                data = report_payload(ReportModel(snapshot, style, '2026-11-10 12:00'))
                self.assertEqual(data['LA (ft)'], '14.0000')
                pdf = BytesIO()
                generate_pdf_calc_sheet(pdf, data)
                text = ' '.join(' '.join(page.extract_text() for page in PdfReader(pdf).pages).split())
                for expected in ('Table 12-2-B', '3R Rural Non-Freeway', 'Recoverable fill slopes',
                                 'no automatic cap is applied', 'mid'):
                    self.assertIn(expected, text)
