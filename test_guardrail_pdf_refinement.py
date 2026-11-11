"""Presentation changes preserve values while making the package easier to read."""

from contextlib import redirect_stdout
from io import BytesIO, StringIO
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from pypdf import PdfReader
from guardrail_presentation import _safe_filename
from test_guardrail_app import app, pdf_data


class PdfRefinementTests(unittest.TestCase):
    def test_clean_filename_fallback_and_windows_sanitizing(self):
        self.assertEqual(_safe_filename(''), 'Guardrail Calculations.pdf')
        self.assertEqual(_safe_filename('SR8 - Guardrail Calculations'), 'SR8 - Guardrail Calculations.pdf')
        self.assertEqual(_safe_filename('SR8/9 - Guardrail Calculations'), 'SR8_9 - Guardrail Calculations.pdf')

    def test_console_exports_complete_package_without_style_prompt(self):
        answers = ['SR8', '1', '65', '6000', '2', '30', '10', '12', '1', '1', '30', 'y', '', '']
        output = StringIO()
        with patch('builtins.input', side_effect=answers) as prompt, \
                patch('guardrail_cli.write_calc_pdf', return_value=True) as write, redirect_stdout(output):
            app.main()
        self.assertEqual(write.call_args.args[1]['__pdf_style'], 3)
        self.assertEqual(Path(write.call_args.args[0]).name, 'SR8 - Guardrail Calculations.pdf')
        self.assertNotIn('PDF style:', output.getvalue())
        self.assertIn('SR8 - Guardrail Calculations.pdf', prompt.call_args.args[0])

    def test_math_is_searchable_serif_text_for_flared_and_nonflared_cases(self):
        for flare in (0, 30):
            results = app.compute_guardrail_outputs(65, 6000, 30, 10, 22, app.DEFAULT_L1_FT, 25, flare)
            data = app.build_pdf_data('QA', 'two_lane_two_way', 65, 6000, 30, 10, 22, 12,
                                      app.DEFAULT_L1_FT, 25, flare, 3, results)
            pdf = BytesIO()
            app.generate_pdf_calc_sheet(pdf, data)
            reader = PdfReader(pdf)
            text = ' '.join(' '.join(page.extract_text() for page in reader.pages).split()).replace('−', '-')
            for field in ('X(min) near (ft)', 'X(min) opp (ft)', 'A (near) (ft)', 'D (opp) (ft)'):
                self.assertIn(data[field], text)
            fonts = {str(font.get_object().get('/BaseFont')) for page in reader.pages
                     for font in page['/Resources']['/Font'].values()}
            self.assertTrue(any('STIXGeneral' in name for name in fonts))
            self.assertNotIn('/Courier', fonts)
            self.assertIn('Substitutions show rounded values', text)
            self.assertIn('NEAR SIDE', reader.pages[1].extract_text())
            opposing = next(page.extract_text() for page in reader.pages if 'OPPOSING SIDE' in page.extract_text())
            self.assertIn('Opposing-Side Length of Need', opposing)

    def test_math_equation_alignment_is_fixed_and_numbers_remain_searchable(self):
        from guardrail_pdf_math import MathEquation
        first = MathEquation(r"X_{\min}", r"\dfrac{L_A}{L_R}")
        second = MathEquation("", r"\mathbf{88.7376}\;\mathrm{ft}", r"\approx")
        self.assertGreater(first.height, second.height)
        self.assertGreater(first.width, 70)
        data = pdf_data(style=2)
        pdf = BytesIO()
        app.generate_pdf_calc_sheet(pdf, data)
        text = ' '.join(page.extract_text() for page in PdfReader(pdf).pages)
        self.assertIn('155.6458', text)
        self.assertIn('68.1458', text)

    def test_only_reference_figure_rotates_and_source_file_is_unchanged(self):
        source = Path(__file__).with_name('gr manual.pdf')
        original = source.read_bytes()
        with tempfile.TemporaryDirectory() as folder:
            out = Path(folder) / 'package.pdf'
            app.write_calc_pdf(str(out), pdf_data())
            pages = PdfReader(out).pages
            figure = next(page for page in pages if 'Figure 9-6-A' in page.extract_text())
            self.assertEqual((float(figure.mediabox.width), float(figure.mediabox.height)), (792, 612))
            self.assertEqual(figure.rotation, 0)
            self.assertIn('APPENDIX A', figure.extract_text())
            self.assertEqual((float(pages[4].mediabox.width), float(pages[4].mediabox.height)), (612, 792))
        self.assertEqual(source.read_bytes(), original)
