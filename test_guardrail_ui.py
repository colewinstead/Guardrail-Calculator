"""Exercise real Tk callbacks without entering an interactive main loop."""

import sys
import tempfile
import tkinter as tk
import unittest
from pathlib import Path
from unittest.mock import patch

import guardrail_validation as validation
from test_guardrail_app import app


class InputStateTests(unittest.TestCase):
    def setUp(self):
        self.ui = {}

        def capture(root):
            root.withdraw()
            self.ui.update(sys._getframe(1).f_locals)

        try:
            with patch.object(tk.Tk, "mainloop", capture):
                app.ui_main()
        except tk.TclError as exc:
            self.skipTest(f"Tk is unavailable: {exc}")
        self.root = self.ui["root"]
        self.addCleanup(self.root.destroy)
        job = self.ui["auto_calculate_job"]["id"]
        if job:
            self.root.after_cancel(job)

    def divided(self):
        self.ui["facility_var"].set("Divided Highway")
        self.ui["update_conditional_fields"]()

    def test_linked_dimensions_refresh_pdf_and_drawing_state(self):
        self.divided()
        self.ui["compute_added_distance"]()
        for field, value, expected in [("median_w_var", "60", 108),
                                       ("lanes_this_var", "3", 120),
                                       ("div_lane_w_var", "10", 110)]:
            self.ui[field].set(value)
            _, payload, roadway = self.ui["calculate_model"]()
            self.assertEqual(float(payload["Opp-side L2 (ft)"]), 10 + expected)
            self.assertEqual(roadway["added_distance"], expected)
            self.assertEqual(float(self.ui["add_dist_var"].get()), expected)
            validation.require_drawing_crossing(roadway)
        self.assertEqual(str(self.ui["add_dist_entry"]["state"]), "readonly")

    def test_fractional_lanes_clear_linked_distance_and_reject_calculation(self):
        self.divided()
        self.ui["compute_added_distance"]()
        self.ui["lanes_this_var"].set("2.5")
        self.assertEqual(self.ui["add_dist_var"].get(), "")
        with self.assertRaisesRegex(ValueError, "whole number"):
            self.ui["calculate_model"]()

    def test_manual_distance_mismatch_prevents_dxf_dialog(self):
        self.divided()
        self.ui["add_dist_var"].set("88")
        self.ui["median_w_var"].set("60")
        _, payload, roadway = self.ui["calculate_model"]()
        self.assertEqual(payload["Opp-side L2 (ft)"], "98.0000")
        self.assertEqual(roadway["added_distance"], 88)
        with patch("tkinter.messagebox.showerror") as error, patch.object(tk, "Toplevel") as dialog:
            self.ui["generate_dxf_action"]()
        dialog.assert_not_called()
        self.assertIn("opposing distance disagrees", error.call_args.args[1])

    def test_dxf_uses_snapshot_even_when_ui_changes_during_dialog(self):
        self.divided()
        self.ui["compute_added_distance"]()

        def accept(root, window):
            local = sys._getframe(1).f_locals
            self.ui["median_w_var"].set("60")
            local["accept_dialog"]()

        with patch.object(tk.Misc, "wait_window", accept), \
                patch("tkinter.filedialog.asksaveasfilename", return_value="snapshot.dxf"), \
                patch("tkinter.messagebox.showinfo"), patch("tkinter.messagebox.showerror") as errors, \
                patch.object(app.guardrail_dxf, "export_guardrail_dxf") as export:
            self.ui["generate_dxf_action"]()
        errors.assert_not_called()
        drawing = export.call_args.args[1]
        self.assertEqual(drawing.median_width, 40)
        self.assertEqual(drawing.opposing_added_distance, 88)
        self.assertEqual(self.ui["median_w_var"].get(), "60")

    def landxml_dialog(self, exercise):
        def inspect(root, window):
            local = sys._getframe(1).f_locals
            local["mode_var"].set("landxml")
            try:
                exercise(local)
            finally:
                if window.winfo_exists():
                    window.destroy()
        with patch.object(tk.Misc, "wait_window", inspect), patch("tkinter.messagebox.showerror") as errors:
            self.ui["generate_dxf_action"]()
        errors.assert_not_called()

    def test_import_warns_about_rejected_alignments_and_retains_valid_ones(self):
        with tempfile.TemporaryDirectory() as folder:
            path = Path(folder) / "mixed.xml"
            path.write_text('<LandXML><Units><Imperial linearUnit="foot"/></Units><Alignments>'
                            '<Alignment name="Good"><CoordGeom><Line length="1000">'
                            '<Start>0 0</Start><End>0 1000</End></Line></CoordGeom></Alignment>'
                            '<Alignment name="Bad"><CoordGeom><Spiral/></CoordGeom></Alignment>'
                            '</Alignments></LandXML>', encoding="utf-8")

            def exercise(local):
                with patch("tkinter.filedialog.askopenfilename", return_value=str(path)), \
                        patch("tkinter.messagebox.showwarning") as warnings:
                    local["browse_landxml"]()
                self.assertEqual([a.name for a in local["loaded_alignments"].values()], ["Good"])
                self.assertIn("Bad", warnings.call_args.args[1])
                self.assertIn("Spiral", warnings.call_args.args[1])

            self.landxml_dialog(exercise)

    def test_landxml_path_changes_and_failed_reload_clear_old_geometry(self):
        with tempfile.TemporaryDirectory() as folder:
            valid = Path(folder) / "valid.xml"
            valid.write_text('<LandXML><Units><Imperial linearUnit="foot"/></Units>'
                             '<Alignments><Alignment name="Good"><CoordGeom><Line length="1000">'
                             '<Start>0 0</Start><End>0 1000</End></Line></CoordGeom></Alignment>'
                             '</Alignments></LandXML>', encoding="utf-8")
            broken = Path(folder) / "broken.xml"
            broken.write_text("<invalid", encoding="utf-8")

            def exercise(local):
                self.assertEqual(str(local["landxml_entry"]["state"]), "readonly")
                with patch("tkinter.filedialog.askopenfilename", return_value=str(valid)):
                    local["browse_landxml"]()
                self.assertTrue(local["loaded_alignments"])
                local["bridge_start_var"].set("4+00")
                local["landxml_path_var"].set("another.xml")
                self.assertFalse(local["loaded_alignments"])
                self.assertEqual(local["alignment_var"].get(), "")
                self.assertEqual(local["bridge_start_var"].get(), "")
                with patch("tkinter.filedialog.askopenfilename", return_value=str(valid)):
                    local["browse_landxml"]()
                with patch("tkinter.filedialog.askopenfilename", return_value=str(broken)), \
                        patch("tkinter.messagebox.showerror") as errors:
                    local["browse_landxml"]()
                self.assertFalse(local["loaded_alignments"])
                self.assertEqual(local["landxml_path_var"].get(), str(broken))
                errors.assert_called_once()

            self.landxml_dialog(exercise)


if __name__ == "__main__":
    unittest.main()
