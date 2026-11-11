"""Exercise real Tk callbacks without entering an interactive main loop."""

import sys
import tempfile
import tkinter as tk
from tkinter import ttk
import unittest
from pathlib import Path
from unittest.mock import patch

import guardrail_validation as validation
from guardrail_design import ReportStyle
from guardrail_models import ReportModel
from guardrail_report import report_payload
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
        self.addCleanup(self.cancel_auto_calculation)
        self.cancel_auto_calculation()

    def cancel_auto_calculation(self):
        job = self.ui["auto_calculate_job"]["id"]
        if job:
            self.root.after_cancel(job)
            self.ui["auto_calculate_job"]["id"] = None

    def divided(self):
        self.ui["facility_var"].set("Divided Highway")
        self.ui["update_conditional_fields"]()

    def test_clear_zone_reference_follows_hazard_offset_source(self):
        label = self.ui["clear_zone_reference_label"]
        self.assertEqual(label.cget("text"), "Using Clear-Zone Table 9-2-A (New Construction)")
        self.assertEqual(label.winfo_manager(), "grid")
        self.ui["la_mode_var"].set("Enter Hazard Offset Directly")
        self.assertEqual(label.winfo_manager(), "")
        self.ui["la_mode_var"].set("Select from Clear-Zone Table")
        self.assertEqual(label.winfo_manager(), "grid")

    def test_3r_selector_updates_preview_snapshot_and_report(self):
        from guardrail_design import ClearZoneCriteria
        self.ui["adt_var"].set("3000")
        self.ui["criteria_var"].set("3R Rural Non-Freeway")
        self.assertIn("14.0000 FT", self.ui["clear_zone_used_var"].get())
        self.assertIn("12-2-B", self.ui["clear_zone_reference_label"].cget("text"))
        self.assertEqual(self.ui["clear_zone_note_label"].winfo_manager(), "grid")
        snapshot = self.ui["calculate_model"]()
        self.assertEqual(snapshot.inputs.barrier.clear_zone_criteria, ClearZoneCriteria.THREE_R)
        self.ui["criteria_var"].set("New Construction")
        self.assertIn("28.0000 FT", self.ui["clear_zone_used_var"].get())
        payload = report_payload(ReportModel(snapshot, ReportStyle.COMPLETE, "2026-11-10 12:00"))
        self.assertIn("12-2-B", payload["Clear-Zone Criteria"])
        self.assertEqual(payload["LA (ft)"], "14.0000")

    def test_3r_rejects_70_mph_and_manual_la_disables_selector(self):
        self.ui["criteria_var"].set("3R Rural Non-Freeway")
        self.ui["speed_var"].set("70")
        self.assertIn("3R clear-zone lookup supports", self.ui["clear_zone_used_var"].get())
        with self.assertRaisesRegex(ValueError, "3R clear-zone lookup"):
            self.ui["calculate_model"]()
        self.ui["la_mode_var"].set("Enter Hazard Offset Directly")
        self.ui["update_conditional_fields"]()
        self.assertTrue(self.ui["criteria_combo"].instate(["disabled"]))
        self.assertEqual(self.ui["clear_zone_note_label"].winfo_manager(), "")
        self.assertEqual(self.ui["calculate_model"]().inputs.barrier.LA, 30)

    def test_primary_button_contrast_in_each_interactive_state(self):
        def luminance(color):
            channels = [int(color[index:index + 2], 16) / 255 for index in (1, 3, 5)]
            linear = [value / 12.92 if value <= 0.04045 else ((value + 0.055) / 1.055) ** 2.4
                      for value in channels]
            return sum(value * weight for value, weight in zip(linear, (0.2126, 0.7152, 0.0722)))

        style = ttk.Style(self.root)
        for state in ((), ("active",), ("pressed",), ("active", "pressed"), ("focus",)):
            with self.subTest(state=state):
                foreground = luminance(style.lookup("Primary.TButton", "foreground", state))
                background = luminance(style.lookup("Primary.TButton", "background", state))
                high, low = sorted((foreground, background), reverse=True)
                self.assertGreaterEqual((high + 0.05) / (low + 0.05), 4.5)

    def test_keyboard_focus_reveals_controls_in_both_scroll_directions(self):
        self.root.state("normal")
        self.root.geometry("900x700")
        self.root.deiconify()
        self.root.update()
        self.root.focus_force()
        canvas = self.ui["canvas"]
        export = next(widget for widget in self.ui["actions"].winfo_children()
                      if widget.winfo_class() == "TButton" and widget.cget("text") == "Export DXF")
        for widget in (export, self.ui["facility_combo"]):
            with self.subTest(control=str(widget)):
                widget.focus_set()
                self.root.update()
                self.assertEqual(self.root.focus_get(), widget)
                self.assertGreaterEqual(widget.winfo_rooty(), canvas.winfo_rooty())
                self.assertLessEqual(widget.winfo_rooty() + widget.winfo_height(),
                                     canvas.winfo_rooty() + canvas.winfo_height())

    def test_dxf_dialog_initial_focus_and_escape_cancel(self):
        self.root.deiconify()
        self.root.update()
        self.root.focus_force()

        def cancel(root, window):
            local = sys._getframe(1).f_locals
            window.update()
            self.assertEqual(window.focus_get(), local["bridge_length_entry"])
            window.event_generate("<Escape>")
            window.update()
            self.assertFalse(window.winfo_exists())

        with patch.object(tk.Misc, "wait_window", cancel), \
                patch("tkinter.filedialog.asksaveasfilename") as save, \
                patch("tkinter.messagebox.showerror") as errors:
            self.ui["generate_dxf_action"]()
        save.assert_not_called()
        errors.assert_not_called()
        self.assertEqual(self.ui["status_var"].get(), "DXF generation cancelled.")

    def test_linked_dimensions_refresh_pdf_and_drawing_state(self):
        self.divided()
        self.ui["compute_added_distance"]()
        for field, value, expected in [("median_w_var", "60", 108),
                                       ("lanes_this_var", "3", 120),
                                       ("div_lane_w_var", "10", 110)]:
            self.ui[field].set(value)
            snapshot = self.ui["calculate_model"]()
            payload = report_payload(ReportModel(snapshot, ReportStyle.COMPLETE, "2026-10-01 12:00"))
            roadway = snapshot.inputs.roadway.as_dict()
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
        snapshot = self.ui["calculate_model"]()
        payload = report_payload(ReportModel(snapshot, ReportStyle.COMPLETE, "2026-10-01 12:00"))
        roadway = snapshot.inputs.roadway.as_dict()
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

    def test_pdf_uses_snapshot_when_form_changes_during_save_dialog(self):
        self.ui["project_var"].set("Original Project")
        expected = self.ui["calculate_model"]()

        def choose(**kwargs):
            self.ui["project_var"].set("Changed Project")
            self.ui["L2_var"].set("20")
            return "snapshot.pdf"

        with patch("tkinter.filedialog.asksaveasfilename", side_effect=choose), \
                patch("guardrail_ui.write_report", return_value=True) as write, \
                patch("tkinter.messagebox.showinfo"), patch("tkinter.messagebox.showerror") as errors:
            self.ui["generate_pdf_action"]()
        errors.assert_not_called()
        report = write.call_args.args[1]
        self.assertEqual(report.snapshot.project.project, "Original Project")
        self.assertEqual(report.snapshot.inputs.roadway.L2, 10)
        self.assertEqual(report.snapshot.result, expected.result)

    def test_unexpected_callback_errors_retain_traceback(self):
        with patch("guardrail_ui.create_snapshot", side_effect=KeyError("programming error")), \
                patch("tkinter.messagebox.showerror") as error, self.assertLogs("guardrail_ui", level="ERROR") as logs:
            self.ui["calculate_action"]()
        self.assertIn("KeyError", "\n".join(logs.output))
        self.assertIn("programming error", error.call_args.args[1])

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
