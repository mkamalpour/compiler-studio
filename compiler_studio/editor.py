"""Small code-editor conveniences built from standard Tk widgets."""

import tkinter as tk
from tkinter import font as tkfont
from tkinter.scrolledtext import ScrolledText


class CodeEditor(ScrolledText):
    def __init__(self, parent, **options):
        super().__init__(parent, **options)
        self.gutter = tk.Canvas(self.frame, width=44, bg="#edf2f8", highlightthickness=0)
        self.gutter.pack(side="left", fill="y", before=self._w)
        self.number_font = tkfont.Font(font=self["font"])
        self.redraw_id = None
        self.configure(yscrollcommand=self._scrolled)
        for event in ("<Configure>", "<KeyRelease>", "<ButtonRelease-1>"):
            self.bind(event, self._schedule, add=True)
        self.bind("<Destroy>", self._destroyed, add=True)
        self.bind("<Tab>", self._indent)
        self.bind("<Shift-Tab>", self._unindent)
        self.bind("<Return>", self._newline)
        self.tag_configure("current_line", background="#f0f5ff")
        self._schedule()

    def _scrolled(self, *args):
        self.vbar.set(*args)
        self._schedule()

    def _schedule(self, event=None):
        if self.redraw_id is None:
            self.redraw_id = self.after_idle(self._redraw)

    def _redraw(self):
        self.redraw_id = None
        self.gutter.delete("all")
        width = max(42, self.number_font.measure(self.index("end-1c").split(".")[0]) + 18)
        self.gutter.configure(width=width)
        index = self.index("@0,0")
        while True:
            info = self.dlineinfo(index)
            if info is None:
                break
            self.gutter.create_text(width - 9, info[1], anchor="ne", text=index.split(".")[0],
                                    font=self.number_font, fill="#6c7d93")
            next_index = self.index(f"{index}+1line")
            if self.compare(next_index, "<=", index):
                break
            index = next_index
        self.tag_remove("current_line", "1.0", "end")
        self.tag_add("current_line", "insert linestart", "insert lineend+1c")
        self.tag_lower("current_line")

    def _indent(self, event):
        self.edit_separator()
        if self.tag_ranges("sel"):
            for line in self._selected_lines():
                self.insert(f"{line}.0", "    ")
        else:
            self.insert("insert", "    ")
        self.edit_separator()
        return "break"

    def _unindent(self, event):
        self.edit_separator()
        for line in self._selected_lines():
            start = f"{line}.0"
            prefix = self.get(start, start + "+4c")
            count = 1 if prefix.startswith("\t") else len(prefix) - len(prefix.lstrip(" "))
            if count:
                self.delete(start, start + f"+{count}c")
        self.edit_separator()
        return "break"

    def _selected_lines(self):
        selected = self.tag_ranges("sel")
        if not selected:
            return [int(self.index("insert").split(".")[0])]
        first = int(self.index(selected[0]).split(".")[0])
        last, column = map(int, self.index(selected[1]).split("."))
        if column == 0 and last > first:
            last -= 1
        return range(first, last + 1)

    def _newline(self, event):
        selected = self.tag_ranges("sel")
        if selected:
            self.delete(*selected)
        prefix = self.get("insert linestart", "insert")
        indentation = prefix[:len(prefix) - len(prefix.lstrip(" \t"))]
        if prefix.rstrip().endswith(("{", ":")):
            indentation += "    "
        self.insert("insert", "\n" + indentation)
        self.see("insert")
        return "break"

    def _destroyed(self, event):
        if event.widget is self and self.redraw_id is not None:
            self.after_cancel(self.redraw_id)
            self.redraw_id = None
