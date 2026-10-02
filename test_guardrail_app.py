"""Regression tests for application input and PDF/file handling."""

import importlib.util
import math
import os
import subprocess
import sys
import tempfile
import unittest
from io import BytesIO
from pathlib import Path
from unittest.mock import patch

from pypdf import PdfReader


MODULE_PATH = Path(__file__).resolve().with_name("guardrail_V8.5.py")
SPEC = importlib.util.spec_from_file_location("guardrail_app", MODULE_PATH)
app = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(app)


def pdf_data(style=3):
    results = app.compute_guardrail_outputs(
        65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, 30,
    )
    return app.build_pdf_data(
        "Baseline", "two_lane_two_way", 65, 6000, 30, 10, 22, 12,
        app.DEFAULT_L1_FT, 25, 30, style, results,
        generated_time="2026-10-01 12:00", calculation_date="2026-10-01",
    )


class NumericInputTests(unittest.TestCase):
    def test_grouped_and_plain_numbers(self):
        for text, expected in [
            ("6,000", 6000), ("1,234,567.25", 1234567.25),
            (" -6,000.5 ", -6000.5), ("+12.5", 12.5),
            (".5", 0.5), ("18.", 18), ("1e3", 1000),
        ]:
            with self.subTest(text=text):
                self.assertEqual(app._first_number(text), expected)

    def test_comma_adt_has_same_results_as_plain_adt(self):
        outputs = []
        for text in ("6000", "6,000"):
            adt = app._first_number(text)
            LA = app.resolve_clear_zone(60, adt, "6:1_or_flatter", "mid")
            outputs.append(app.compute_guardrail_outputs(
                60, adt, LA, 10, 22, app.DEFAULT_L1_FT, 25, 30,
            ))
        self.assertEqual(outputs[0], outputs[1])
        self.assertAlmostEqual(outputs[1]["A"], 130.64583333333331)

    def test_malformed_values_are_rejected(self):
        for text in ("", " ", "6,00", "6000, 2030", "12abc34", "12 ft",
                     "18'-1.75\"", "1.2.3", "1e", "--2", "1,000,", "1_000"):
            with self.subTest(text=text), self.assertRaises(ValueError):
                app._first_number(text)

    def test_nonfinite_values_are_rejected(self):
        for text in ("NaN", "nan", "inf", "-Infinity", "+inf", "1e309", "9" * 400):
            with self.subTest(text=text), self.assertRaises(ValueError):
                app._first_number(text)

    def test_calculation_entry_points_reject_nonfinite_inputs(self):
        for invalid in (math.nan, math.inf, -math.inf):
            for index in range(8):
                inputs = [60, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, 30]
                inputs[index] = invalid
                with self.subTest(value=invalid, index=index), self.assertRaises(ValueError):
                    app.compute_guardrail_outputs(*inputs)
            with self.subTest(value=invalid, operation="custom clear zone"), self.assertRaises(ValueError):
                app.resolve_clear_zone(60, 6000, "6:1_or_flatter", "custom", invalid)

    def test_existing_engineering_outputs_are_preserved(self):
        # Characterization of the existing implementation, not engineering approval.
        for flare, expected in [(30, (155.64583333333331, 112.5, 68.14583333333333, 25)),
                                (0, (205.64583333333331, 162.5, 80.64583333333333, 37.5))]:
            outputs = app.compute_guardrail_outputs(
                65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, flare,
            )
            for key, value in zip(("A", "B", "C", "D"), expected):
                with self.subTest(flare=flare, key=key):
                    self.assertAlmostEqual(outputs[key], value)


class PdfHandlingTests(unittest.TestCase):
    def test_metadata_markup_is_rendered_literally_in_all_styles(self):
        for style in (1, 2, 3):
            data = pdf_data(style)
            data.update({
                "Project": "A <b>B</b> & C",
                "Job Number": "Job <b>",
                "Route / Location": "Road <route> & east",
                "Prepared By": "Author <i>name</i>",
                "Checked By": "Reviewer <review>",
                "Calculation Date": "Date <date>",
            })
            with self.subTest(style=style):
                buffer = BytesIO()
                app.generate_pdf_calc_sheet(buffer, data)
                reader = PdfReader(buffer)
                text = " ".join(" ".join(page.extract_text().split()) for page in reader.pages)
                keys = ("Project", "Job Number") if style == 2 else (
                    "Project", "Job Number", "Route / Location", "Prepared By",
                    "Checked By", "Calculation Date",
                )
                for key in keys:
                    self.assertIn(data[key], text)
                self.assertIn("155.6458", text)
                self.assertEqual(reader.metadata.title, f"{data['Project']} Guardrail Calculations")

    def test_existing_predictable_temp_file_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder:
            out_path = Path(folder) / "report.pdf"
            collision = Path(folder) / "report_tmp.pdf"
            collision.write_bytes(b"unrelated existing file")
            app.write_calc_pdf(str(out_path), pdf_data(), include_appendix=False)
            self.assertEqual(collision.read_bytes(), b"unrelated existing file")
            self.assertEqual(len(PdfReader(out_path).pages), 2)
            self.assertEqual(set(Path(folder).iterdir()), {collision, out_path})

    def test_nested_exports_use_distinct_temp_files(self):
        with tempfile.TemporaryDirectory() as folder:
            out_path = Path(folder) / "report.pdf"
            temp_paths = []
            original_render = app.generate_pdf_calc_sheet

            def render(path, data):
                temp_paths.append(Path(path))
                self.assertEqual(Path(path).parent, out_path.parent)
                if len(temp_paths) == 1:
                    app.write_calc_pdf(str(out_path), data, include_appendix=False)
                original_render(path, data)

            with patch.object(app, "generate_pdf_calc_sheet", side_effect=render):
                app.write_calc_pdf(str(out_path), pdf_data(), include_appendix=False)
            self.assertEqual(len(set(temp_paths)), 2)
            self.assertEqual(list(Path(folder).iterdir()), [out_path])
            self.assertEqual(len(PdfReader(out_path).pages), 2)

    def test_failed_render_cleans_temp_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            out_path = Path(folder) / "report.pdf"
            out_path.write_bytes(b"existing report")
            temp_paths = []

            def fail(path, data):
                temp_paths.append(Path(path))
                Path(path).write_bytes(b"incomplete")
                raise RuntimeError("render failed")

            with patch.object(app, "generate_pdf_calc_sheet", side_effect=fail), \
                    self.assertRaisesRegex(RuntimeError, "render failed"):
                app.write_calc_pdf(str(out_path), pdf_data(), include_appendix=False)
            self.assertEqual(out_path.read_bytes(), b"existing report")
            self.assertFalse(temp_paths[0].exists())

    def test_failed_appendix_merge_cleans_temp_and_preserves_destination(self):
        with tempfile.TemporaryDirectory() as folder:
            out_path = Path(folder) / "report.pdf"
            out_path.write_bytes(b"existing report")

            def fail(main_path, appendices, completed_path):
                Path(completed_path).write_bytes(b"incomplete package")
                raise RuntimeError("merge failed")

            with patch.object(app, "merge_with_appendices", side_effect=fail), \
                    self.assertRaisesRegex(RuntimeError, "merge failed"):
                app.write_calc_pdf(str(out_path), pdf_data())
            self.assertEqual(out_path.read_bytes(), b"existing report")
            self.assertEqual(list(Path(folder).iterdir()), [out_path])

    def test_reference_appendices_still_merge(self):
        with tempfile.TemporaryDirectory() as folder:
            out_path = Path(folder) / "package.pdf"
            self.assertTrue(app.write_calc_pdf(str(out_path), pdf_data()))
            reader = PdfReader(out_path)
            self.assertEqual(len(reader.pages), 7)
            reference = PdfReader(MODULE_PATH.parent / "GR-4a.pdf")
            self.assertEqual(reader.pages[-1].mediabox, reference.pages[0].mediabox)
            self.assertEqual(len(reader.outline), 3)
            self.assertEqual(list(Path(folder).iterdir()), [out_path])


class ResourceLookupTests(unittest.TestCase):
    def test_source_import_from_different_working_directory(self):
        script = """
import importlib.util
import os
import sys
from pathlib import Path
sys.path.insert(0, str(Path(sys.argv[1]).parent))
spec = importlib.util.spec_from_file_location('app', sys.argv[1])
app = importlib.util.module_from_spec(spec)
spec.loader.exec_module(app)
for name in ('gr manual.pdf', 'GR-4.pdf', 'GR-4a.pdf'):
    resolved = Path(app.resource_path(name))
    assert resolved == Path(sys.argv[1]).parent / name, resolved
    assert resolved.is_file(), resolved
"""
        with tempfile.TemporaryDirectory() as folder:
            result = subprocess.run(
                [sys.executable, "-B", "-c", script, str(MODULE_PATH)],
                cwd=folder, capture_output=True, text=True, check=False,
            )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_pyinstaller_resource_directory_is_preserved(self):
        with tempfile.TemporaryDirectory() as folder, patch.object(sys, "_MEIPASS", folder, create=True):
            self.assertEqual(app.resource_path("GR-4.pdf"), os.path.join(folder, "GR-4.pdf"))


if __name__ == "__main__":
    unittest.main()
