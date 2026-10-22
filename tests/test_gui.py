"""Exercise actual Tk widgets and process jobs; skip only without Tk/display."""

import csv
import json
from pathlib import Path
import tempfile
import time
import unittest
from unittest.mock import patch

try:
    import tkinter as tk
except ImportError:
    tk = None


@unittest.skipIf(tk is None, "Tkinter unavailable")
class GuiTests(unittest.TestCase):
    def setUp(self):
        try:
            self.root = tk.Tk()
        except tk.TclError as exc:
            self.skipTest(str(exc))
        self.root.withdraw()
        from compiler_studio.gui import Studio
        self.app = Studio(self.root)
        self.root.update()

    def tearDown(self):
        if hasattr(self, "app"):
            self.app.cancel(silent=True)
            self.root.destroy()

    def wait_for_result(self):
        deadline = time.monotonic() + 15
        while self.app.job is not None and time.monotonic() < deadline:
            self.root.update()
            time.sleep(0.01)
        self.assertIsNone(self.app.job)
        self.assertIsNotNone(self.app.result)

    def test_pipeline_actual_widgets_locations_and_edit_invalidation(self):
        self.app.run()
        self.wait_for_result()
        self.assertTrue(self.app.result["ok"])
        self.assertGreater(len(self.app.tokens.get_children()), 50)
        self.assertTrue(self.app.tree.get_children())
        self.app.tokens.selection_set("0")
        self.app._select_token()
        self.assertTrue(self.app.source.tag_ranges("selection_target"))
        self.app.source.insert("end", "\n@")
        self.root.update()
        self.assertIsNone(self.app.result)
        self.assertFalse(self.app.tokens.get_children())
        self.app.run()
        self.wait_for_result()
        self.assertFalse(self.app.result["ok"])
        self.assertTrue(self.app.diagnostics.get_children())

    def test_custom_language_designer_and_profile_save_load(self):
        self.app.preset("calculator")
        self.app._set_source("9 - 2 * 3")
        self.app.add_rule()
        self.app.fields["name"].set("MINUS")
        self.app.fields["pattern"].set(r"\-")
        self.assertTrue(self.app.apply_rule())
        grammar = self.app.grammar.get("1.0", "end-1c").replace("| product\n", "| sum MINUS product -> subtraction\n    | product\n", 1)
        self.app.grammar.delete("1.0", "end")
        self.app.grammar.insert("1.0", grammar)
        self.root.update()
        self.app.run()
        self.wait_for_result()
        self.assertTrue(self.app.result["ok"], self.app.result["diagnostics"])
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "custom.json")
            with patch("compiler_studio.gui.filedialog.asksaveasfilename", return_value=path):
                self.app.save_profile()
            self.assertEqual(json.loads(Path(path).read_text())["rules"][-1]["name"], "MINUS")
            self.app.preset("ricepy")
            with patch("compiler_studio.gui.filedialog.askopenfilename", return_value=path):
                self.app.open_profile()
            self.assertEqual(self.app.current_profile().rules[-1].name, "MINUS")

    def test_json_csv_exports_and_no_stale_export(self):
        self.app.run()
        self.wait_for_result()
        with tempfile.TemporaryDirectory() as directory:
            report = str(Path(directory) / "report.json")
            with patch("compiler_studio.gui.filedialog.asksaveasfilename", return_value=report):
                self.app.export_json()
            self.assertTrue(json.loads(Path(report).read_text())["ok"])
            output = str(Path(directory) / "tokens.csv")
            with patch("compiler_studio.gui.filedialog.asksaveasfilename", return_value=output):
                self.app.export_csv()
            with open(output, encoding="utf-8", newline="") as stream:
                rows = list(csv.reader(stream))
            self.assertEqual(len(rows), len(self.app.result["tokens"]) + 1)
            self.assertEqual(rows[1][1], self.app.result["tokens"][0]["value"])
            assign_row = next(row for row in rows[1:] if row[0] == "ASSIGN")
            self.assertEqual(assign_row[1], "'=")
            self.app.name.set("Changed language")
            with patch("compiler_studio.gui.messagebox.showinfo") as dialog:
                self.app.export_json()
                dialog.assert_called_once()

    def test_file_error_preserves_source_and_cancel_stops_worker(self):
        original = self.app.source.get("1.0", "end-1c")
        with patch("compiler_studio.gui.filedialog.askopenfilename", return_value="missing-file"), patch("compiler_studio.gui.messagebox.showerror") as dialog:
            self.app.open_source()
            dialog.assert_called_once()
        self.assertEqual(self.app.source.get("1.0", "end-1c"), original)
        self.app.run()
        process = self.app.job.process
        self.app.cancel()
        self.assertIsNone(self.app.job)
        self.assertFalse(process.is_alive())

    def test_rule_reordering_and_small_window_controls(self):
        self.app.tabs.select(self.app.language_tab)
        self.root.deiconify()
        self.root.geometry("1000x800")
        self.root.update()
        first_name = self.app.rules[0]["name"]
        self.app.move_rule(1)
        self.assertEqual(self.app.rules[1]["name"], first_name)
        self.assertEqual(self.app.selected_rule, 1)
        self.assertGreater(self.app.rule_table.winfo_height(), 25)
        form = self.app.rule_table.master.master
        buttons = [widget for container in form.winfo_children() for widget in container.winfo_children()
                   if str(widget.winfo_class()) == "TButton"]
        self.assertTrue(buttons)
        for button in buttons:
            self.assertLess(button.winfo_rooty() + button.winfo_height(), self.root.winfo_rooty() + self.root.winfo_height())


if __name__ == "__main__":
    unittest.main()
