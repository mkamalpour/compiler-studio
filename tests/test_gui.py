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
            self.app.worker.close()
            if self.app.filter_id is not None:
                self.root.after_cancel(self.app.filter_id)
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

    def test_source_tabs_preserve_independent_edits_and_results(self):
        first = self.app.active_document
        self.app.run()
        self.wait_for_result()
        report = first.result
        second = self.app.new_document("int other = 4;", title="Second")
        self.root.update()
        self.assertIsNone(self.app.result)
        self.app.run()
        self.wait_for_result()
        self.assertTrue(self.app.result["ok"])
        self.app.source.insert("end", "\n@")
        self.root.update()
        self.assertTrue(second.dirty)
        self.assertIsNone(second.result)
        self.app.source_tabs.select(first.frame)
        self.root.update()
        self.assertIs(self.app.result, report)
        self.assertTrue(self.app.tokens.get_children())
        self.app.name.set("Changed shared language")
        self.assertTrue(all(doc.result is None for doc in self.app.documents))
        self.app.source_tabs.select(second.frame)
        self.root.update()
        self.assertIn("@", self.app.source.get("1.0", "end"))
        with patch("compiler_studio.gui.messagebox.askyesnocancel", return_value=None):
            self.assertFalse(self.app.close_document())
        self.assertIn(second, self.app.documents)
        with patch("compiler_studio.gui.messagebox.askyesnocancel", return_value=False):
            self.assertTrue(self.app.close_document())
        self.assertNotIn(second, self.app.documents)

    def test_find_token_filter_lazy_tree_and_error_detail(self):
        self.app.run()
        self.wait_for_result()
        self.app.search.set("function")
        self.app.find_next()
        self.assertTrue(self.app.source.tag_ranges("search_match"))
        self.app.token_filter.set("WHILE")
        self.app._filter_tokens()
        self.assertEqual(len(self.app.tokens.get_children()), 1)
        self.app.tokens.selection_set(self.app.tokens.get_children()[0])
        self.app._select_token()
        self.assertEqual(self.app.source.get(*self.app.source.tag_ranges("selection_target")), "while")
        root = self.app.tree.get_children()[0]
        child = next(iid for iid in self.app.tree.get_children(root)
                     if self.app.tree_locations[iid]["children"])
        before = len(self.app.tree_locations)
        self.app._expand_tree(child)
        self.assertGreater(len(self.app.tree_locations), before)
        self.app._set_source("int value")
        self.app.run()
        self.wait_for_result()
        self.assertIn("semicolon", self.app.diagnostic_detail.get("1.0", "end"))

    def test_open_preserves_other_tabs_and_save_cancel_keeps_dirty_document(self):
        first = self.app.active_document
        with tempfile.TemporaryDirectory() as directory:
            path = str(Path(directory) / "second.ricepy")
            Path(path).write_text("int x;", encoding="utf-8")
            with patch("compiler_studio.gui.filedialog.askopenfilename", return_value=path):
                self.app.open_source()
            self.root.update()
            second = self.app.active_document
            self.assertIsNot(first, second)
            self.app.source.insert("end", "\nint y;")
            self.root.update()
            with patch("compiler_studio.gui.filedialog.askopenfilename", return_value=path):
                self.app.open_source()
            self.assertEqual(len(self.app.documents), 2)
            self.assertIn("int y;", self.app.source.get("1.0", "end"))
            self.assertTrue(self.app.save_source())
            self.assertFalse(second.dirty)
            self.assertIn("int y;", Path(path).read_text())
            self.app.new_document("int draft;", title="Draft")
            self.app.source_dirty = True
            with patch("compiler_studio.gui.messagebox.askyesnocancel", return_value=True), patch("compiler_studio.gui.filedialog.asksaveasfilename", return_value=""):
                self.assertFalse(self.app.close_document())
            self.assertEqual(len(self.app.documents), 3)

    def test_editor_block_indentation_and_selected_text_replacement(self):
        self.app.new_document("int existing;")
        with self.assertRaises(tk.TclError):
            self.app.source.edit_undo()
        self.assertEqual(self.app.source.get("1.0", "end-1c"), "int existing;")
        self.app._set_source("one\ntwo\n")
        editor = self.app.source
        editor.tag_add("sel", "1.0", "3.0")
        editor._indent(None)
        self.assertEqual(editor.get("1.0", "end-1c"), "    one\n    two\n")
        editor.tag_remove("sel", "1.0", "end")
        editor.tag_add("sel", "1.0", "3.0")
        editor._unindent(None)
        self.assertEqual(editor.get("1.0", "end-1c"), "one\ntwo\n")
        self.app._set_source("if (true) {")
        editor.mark_set("insert", "end-1c")
        editor._newline(None)
        self.assertEqual(editor.get("1.0", "end-1c"), "if (true) {\n    ")
        editor.tag_add("sel", "1.0", "end-1c")
        editor._newline(None)
        self.assertEqual(editor.get("1.0", "end-1c"), "\n")

    def test_tab_switch_cancels_active_job_without_attaching_a_stale_report(self):
        first = self.app.active_document
        self.app.run()
        process = self.app.job.process
        second = self.app.new_document("int next;")
        self.root.update()
        self.assertFalse(process.is_alive())
        self.assertIsNone(self.app.job)
        self.assertIsNone(first.result)
        self.assertIsNone(second.result)
        self.app.run()
        self.wait_for_result()
        self.assertTrue(second.result["ok"])
        self.assertIsNone(first.result)

    def test_profile_save_dialog_cancel_preserves_language_edits(self):
        self.app.name.set("My custom language")
        with patch("compiler_studio.gui.messagebox.askyesnocancel", return_value=True), patch("compiler_studio.gui.filedialog.asksaveasfilename", return_value=""):
            self.assertFalse(self.app._discard_profile())
        self.assertTrue(self.app.profile_dirty)
        self.assertEqual(self.app.name.get(), "My custom language")

    def test_shared_language_edits_and_replacement_invalidate_all_cached_tabs(self):
        first = self.app.active_document
        self.app.run()
        self.wait_for_result()
        second = self.app.new_document("int other;")
        self.app.run()
        self.wait_for_result()
        self.assertIsNotNone(first.result)
        self.assertIsNotNone(second.result)
        self.app.name.set("Edited language")
        self.assertTrue(all(doc.result is None for doc in self.app.documents))
        for document in (first, second):
            self.app.source_tabs.select(document.frame)
            self.root.update()
            self.app.run()
            self.wait_for_result()
        self.assertTrue(all(doc.result is not None for doc in self.app.documents))
        with patch("compiler_studio.gui.messagebox.askyesnocancel", return_value=False):
            self.app.preset("calculator")
        self.assertTrue(all(doc.result is None for doc in self.app.documents))
        self.app.source_tabs.select(first.frame)
        self.root.update()
        self.assertIsNone(self.app.result)
        self.assertFalse(self.app.tokens.get_children())


if __name__ == "__main__":
    unittest.main()
