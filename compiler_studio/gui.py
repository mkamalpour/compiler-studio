"""Tk desktop workbench. Source and language profiles stay local."""

import csv
from dataclasses import dataclass
import json
import os
from pathlib import Path
import tempfile
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from .profiles import Profile, ricepy_profile, calculator_profile
from .worker import AnalysisWorker
from .editor import CodeEditor
from .friendly_ui import FriendlyUI
from .example_library import STARTER
from .presentation import token_group, token_name, STAGES, explain_diagnostic

BLUE, INK, MUTED, BG = "#2457d6", "#18243b", "#53647c", "#f3f5fa"


def atomic_write(path, text):
    """Replace only after the complete UTF-8 document is safely written."""
    target = Path(path)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="", dir=target.parent,
                                         prefix=".compiler-studio-", delete=False) as stream:
            temporary = Path(stream.name)
            stream.write(text)
        os.replace(temporary, target)
    finally:
        if temporary is not None and temporary.exists():
            temporary.unlink()


@dataclass
class Document:
    frame: object
    editor: object
    title: str
    path: str | None = None
    dirty: bool = False
    result: dict | None = None


class Studio(FriendlyUI):
    @property
    def source(self):
        return self.active_document.editor

    @property
    def source_path(self):
        return self.active_document.path if self.active_document else None

    @source_path.setter
    def source_path(self, value):
        self.active_document.path = value

    @property
    def source_dirty(self):
        return self.active_document.dirty if self.active_document else False

    @source_dirty.setter
    def source_dirty(self, value):
        self.active_document.dirty = value

    @property
    def result(self):
        return self.active_document.result if self.active_document else None

    @result.setter
    def result(self, value):
        self.active_document.result = value

    def __init__(self, root):
        self.root = root
        self.profile = ricepy_profile()
        self.rules = [dict(item) for item in self.profile.to_dict()["rules"]]
        self.job = None
        self.poll_id = None
        self.documents = []
        self.active_document = None
        self.document_serial = 0
        self.worker = AnalysisWorker()
        self.filter_id = None
        self.profile_dirty = False
        self.rule_dirty = False
        self.loading = True
        self.root.title("Compiler Studio — Python language workbench")
        width = min(1280, self.root.winfo_screenwidth() - 60)
        height = min(900, self.root.winfo_screenheight() - 100)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(980, width), min(800, height))
        self.root.configure(bg=BG)
        self._style()
        self._build()
        self._load_profile(self.profile)
        self.active_document.title = "RicePy example"
        self._set_source(STARTER)
        self.loading = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        for shortcut, callback in [("<F5>", self.run), ("<Control-Return>", self.run),
                                   ("<F6>", lambda: self.run("lexer")), ("<F7>", lambda: self.run("validate")),
                                   ("<Control-o>", self.open_source), ("<Control-s>", self.save_source),
                                   ("<Control-n>", self.new_document), ("<Control-w>", self.close_document),
                                   ("<Control-f>", self.focus_find), ("<F3>", self.find_next),
                                   ("<Control-Shift-S>", lambda: self.save_source(save_as=True))]:
            self.root.bind(shortcut, lambda event, cb=callback: (cb(), "break")[1])

    def _style(self):
        style = ttk.Style(self.root)
        style.theme_use("clam")
        style.configure(".", font=("Segoe UI", 10), foreground=INK, background=BG)
        style.configure("TButton", padding=(10, 7), background="#e5eaf5")
        style.map("TButton", background=[("active", "#d5dff3")])
        style.configure("Accent.TButton", background=BLUE, foreground="white")
        style.map("Accent.TButton", background=[("active", "#1945b5"), ("disabled", "#8798b9")])
        style.configure("TNotebook", borderwidth=0)
        style.configure("TNotebook.Tab", padding=(13, 9))
        style.map("TNotebook.Tab", background=[("selected", "white")], foreground=[("selected", BLUE)])
        style.configure("Treeview", background="white", fieldbackground="white", rowheight=27)
        style.configure("Treeview.Heading", font=("Segoe UI", 10, "bold"), padding=6)
        style.configure("Title.TLabel", font=("Segoe UI", 24, "bold"))
        style.configure("Muted.TLabel", foreground=MUTED)
        style.configure("Card.TFrame", background="white")
        style.configure("Card.TLabel", background="white", foreground=MUTED, font=("Segoe UI", 9))
        style.configure("Number.TLabel", background="white", foreground=INK, font=("Segoe UI", 16, "bold"))
        style.configure("TNotebook.Tab", padding=(14, 8))
        style.configure("Treeview.Heading", background="#e8eef8", foreground="#344c70")
        style.map("Treeview", background=[("selected", "#dce9ff")], foreground=[("selected", "#17366b")])
        style.configure("Horizontal.TProgressbar", background=BLUE, troughcolor="#e0e7f1", borderwidth=0)

    def _build(self):
        header = tk.Frame(self.root, bg="#14243e", padx=16, pady=6)
        header.pack(fill="x")
        tk.Label(header, text="Compiler Studio", font=("Segoe UI", 17, "bold"), fg="white", bg="#14243e").pack(side="left")
        tk.Label(header, text="Check your code. Understand the results.", font=("Segoe UI", 11), fg="#b9dedb", bg="#14243e").pack(side="right")
        toolbar = ttk.Frame(self.root, padding=(12, 5, 12, 4))
        toolbar.pack(fill="x")
        self.analyze_button = ttk.Button(toolbar, text="Analyze code  F5", command=self.run, style="Accent.TButton")
        self.analyze_button.pack(side="left", padx=3)
        self.tokens_button = ttk.Button(toolbar, text="Check tokens only  F6", command=lambda: self.run("lexer"))
        self.tokens_button.pack(side="left", padx=3)
        ttk.Button(toolbar, text="Try an example", command=lambda: self.tabs.select(self.examples_tab)).pack(side="left", padx=3)
        self.cancel_button = ttk.Button(toolbar, text="Cancel", command=self.cancel, state="disabled")
        self.cancel_button.pack(side="left", padx=3)
        ttk.Button(toolbar, text="Customize language", command=self.show_language_settings).pack(side="right", padx=3)
        self.progress = ttk.Progressbar(toolbar, mode="indeterminate", length=80)
        self._build_banner(self.root)
        self.status = tk.StringVar(value="Ready - click Analyze code to check the example")
        ttk.Label(self.root, textvariable=self.status, padding=(22, 5, 20, 10), style="Muted.TLabel").pack(side="bottom", fill="x")
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 8))
        self.workbench = ttk.Frame(self.tabs, padding=10)
        self.examples_tab = ttk.Frame(self.tabs, padding=14)
        self.statistics_tab = ttk.Frame(self.tabs, padding=16)
        self.history_tab = ttk.Frame(self.tabs, padding=16)
        self.guide_tab = ttk.Frame(self.tabs, padding=12)
        self.language_tab = ttk.Frame(self.tabs, padding=10)
        for frame, label in [(self.workbench, "Analyze"), (self.examples_tab, "Examples"),
                             (self.statistics_tab, "Statistics"), (self.history_tab, "History"),
                             (self.guide_tab, "Help"), (self.language_tab, "Language settings")]:
            self.tabs.add(frame, text=label)
        self._workbench()
        self._build_examples()
        self._build_statistics()
        self._build_history()
        self._language_designer()
        self._build_help()
        self.tabs.bind("<<NotebookTabChanged>>", self._main_tab_changed)
        self._menu()

    def _menu(self):
        menu = tk.Menu(self.root)
        file = tk.Menu(menu, tearoff=False)
        for label, callback, shortcut in [
            ("New source tab", self.new_document, "Ctrl+N"), ("Open source...", self.open_source, "Ctrl+O"),
            ("Save", self.save_source, "Ctrl+S"), ("Save as...", lambda: self.save_source(save_as=True), "Ctrl+Shift+S"),
            ("Close source tab", self.close_document, "Ctrl+W"),
        ]:
            file.add_command(label=label, command=callback, accelerator=shortcut)
        file.add_separator()
        file.add_command(label="Export analysis JSON...", command=self.export_json)
        file.add_command(label="Export token CSV...", command=self.export_csv)
        file.add_separator()
        file.add_command(label="Exit", command=self.close)
        menu.add_cascade(label="File", menu=file)
        edit = tk.Menu(menu, tearoff=False)
        edit.add_command(label="Undo", command=lambda: self.source.event_generate("<<Undo>>"), accelerator="Ctrl+Z")
        edit.add_command(label="Redo", command=lambda: self.source.event_generate("<<Redo>>"), accelerator="Ctrl+Y")
        edit.add_command(label="Find", command=self.focus_find, accelerator="Ctrl+F")
        menu.add_cascade(label="Edit", menu=edit)
        export = tk.Menu(menu, tearoff=False)
        export.add_command(label="Analysis JSON...", command=self.export_json)
        export.add_command(label="Token CSV...", command=self.export_csv)
        menu.add_cascade(label="Export", menu=export)
        tools = tk.Menu(menu, tearoff=False)
        tools.add_command(label="Language settings (advanced)...", command=self.show_language_settings)
        tools.add_command(label="Validate language rules", command=lambda: self.run("validate"), accelerator="F7")
        menu.add_cascade(label="Tools", menu=tools)
        menu.add_command(label="Help", command=lambda: self.tabs.select(self.guide_tab))
        self.root.configure(menu=menu)

    def _workbench(self):
        split = ttk.Panedwindow(self.workbench, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=6)
        split.add(right, weight=6)
        source_bar = ttk.Frame(left)
        source_bar.pack(fill="x", pady=(0, 7))
        ttk.Label(source_bar, text="SOURCE", font=("Segoe UI", 10, "bold")).pack(side="left")
        for text, command in [("New", self.new_document), ("Open", self.open_source), ("Save", self.save_source), ("Close", self.close_document), ("Clear", self.clear_source)]:
            ttk.Button(source_bar, text=text, command=command, width=5, padding=(4, 4)).pack(side="left", padx=(5, 0))
        search = ttk.Frame(left)
        search.pack(fill="x", pady=(0, 7))
        ttk.Label(search, text="Find").pack(side="left")
        self.search = tk.StringVar()
        self.search_entry = ttk.Entry(search, textvariable=self.search, width=18)
        self.search_entry.pack(side="left", fill="x", expand=True, padx=6)
        self.search_entry.bind("<Return>", lambda event: self.find_next())
        ttk.Button(search, text="Next  F3", command=self.find_next, padding=(6, 3)).pack(side="left")
        self.cursor = tk.StringVar(value="Line 1, column 1")
        self.file_label = tk.StringVar(value="Untitled")
        footer = ttk.Frame(left)
        footer.pack(side="bottom", fill="x")
        ttk.Label(footer, textvariable=self.cursor, style="Muted.TLabel", padding=4).pack(side="left")
        self.source_tabs = ttk.Notebook(left)
        self.source_tabs.pack(fill="both", expand=True)
        self.source_tabs.enable_traversal()
        self.new_document()
        self.source_tabs.bind("<<NotebookTabChanged>>", self._document_selected)
        self.outputs = ttk.Notebook(right)
        self.outputs.pack(fill="both", expand=True, padx=(10, 0))
        tokens_tab, tree_tab, diagnostics_tab = [ttk.Frame(self.outputs, padding=6) for _ in range(3)]
        self.outputs.add(tokens_tab, text="Tokens")
        self.outputs.add(tree_tab, text="Structure")
        self.outputs.add(diagnostics_tab, text="Issues")
        self.tokens_tab, self.structure_tab, self.issues_tab = tokens_tab, tree_tab, diagnostics_tab
        self.token_count = tk.StringVar(value="Run analysis to inspect the token stream.")
        ttk.Label(tokens_tab, textvariable=self.token_count, style="Muted.TLabel", wraplength=550).pack(anchor="w", pady=(2, 7))
        filters = ttk.Frame(tokens_tab)
        filters.pack(fill="x", pady=(0, 7))
        ttk.Label(filters, text="Filter").pack(side="left")
        self.token_filter = tk.StringVar()
        ttk.Entry(filters, textvariable=self.token_filter, width=18).pack(side="left", fill="x", expand=True, padx=6)
        self.hide_comments = tk.BooleanVar(value=False)
        ttk.Checkbutton(filters, text="Hide comments", variable=self.hide_comments, command=self._filter_tokens).pack(side="left")
        self.token_filter.trace_add("write", self._schedule_filter)
        self.tokens = self._table(tokens_tab, ("kind", "value", "location"), ("Type", "Text", "Line:col"), (140, 220, 70))
        for group, color in {"Keywords": "#174ea6", "Names": "#9a4c00", "Values": "#8338a1",
                             "Operators & symbols": "#216b38", "Needs fixing": "#b42318", "Comments": "#667085",
                             "Other tokens": "#344054"}.items():
            self.tokens.tag_configure(group, foreground=color)
        self.show_token_names = tk.BooleanVar(value=False)
        ttk.Checkbutton(tokens_tab, text="Show technical token names", variable=self.show_token_names,
                        command=self._filter_tokens).pack(side="bottom", anchor="w", pady=(5, 0))
        self.tokens.master.pack_forget()
        self.tokens.master.pack(fill="both", expand=True)
        self.tokens.bind("<<TreeviewSelect>>", self._select_token)
        self.tree_count = tk.StringVar(value="A successful parse produces a syntax tree.")
        ttk.Label(tree_tab, textvariable=self.tree_count, style="Muted.TLabel", wraplength=550).pack(anchor="w", pady=(2, 8))
        self.tree = self._table(tree_tab, (), (), (), tree=True)
        self.tree.heading("#0", text="Grammar rule / token · expand a branch to explore")
        self.tree.bind("<<TreeviewSelect>>", self._select_tree)
        self.tree.bind("<<TreeviewOpen>>", self._tree_open)
        self.diagnostic_detail = ScrolledText(diagnostics_tab, height=6, width=30, wrap="word", font=("Segoe UI", 10),
                                             bg="#eef3fb", fg=INK, relief="flat", padx=10, pady=8, state="disabled")
        issue_actions = ttk.Frame(diagnostics_tab)
        issue_actions.pack(side="bottom", fill="x", pady=(6, 0))
        ttk.Button(issue_actions, text="Jump to problem", command=self.jump_to_problem).pack(side="left")
        self.technical_details = tk.BooleanVar(value=False)
        ttk.Checkbutton(issue_actions, text="Technical details", variable=self.technical_details,
                        command=self._select_diagnostic).pack(side="right")
        self.diagnostic_detail.pack(side="bottom", fill="x", pady=(8, 0))
        self.diagnostics = self._table(diagnostics_tab, ("stage", "location", "message"), ("Stage", "Line:col", "Message"), (75, 65, 330))
        self.diagnostics.bind("<<TreeviewSelect>>", self._select_diagnostic)
        self.tree_locations = {}
        self._build_summary()

    @staticmethod
    def _editor(parent, height=15):
        editor = CodeEditor(parent, wrap="none", undo=True, font=("Consolas", 11),
                              bg="white", fg=INK, insertbackground=INK, relief="flat", borderwidth=1,
                              padx=12, pady=10, height=height, width=30, tabs=(32,))
        editor.pack(fill="both", expand=True)
        horizontal = ttk.Scrollbar(parent, orient="horizontal", command=editor.xview)
        horizontal.pack(fill="x")
        editor.configure(xscrollcommand=horizontal.set)
        editor.horizontal_scrollbar = horizontal
        return editor

    @staticmethod
    def _table(parent, columns, headings, widths, tree=False):
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        table = ttk.Treeview(frame, columns=columns, show="tree" if tree else "headings", selectmode="browse")
        table.grid(row=0, column=0, sticky="nsew")
        for col, heading, width in zip(columns, headings, widths):
            table.heading(col, text=heading)
            table.column(col, width=width, minwidth=50, stretch=True)
        scroll = ttk.Scrollbar(frame, orient="vertical", command=table.yview)
        scroll.grid(row=0, column=1, sticky="ns")
        horizontal = ttk.Scrollbar(frame, orient="horizontal", command=table.xview)
        horizontal.grid(row=1, column=0, sticky="ew")
        table.configure(yscrollcommand=scroll.set, xscrollcommand=horizontal.set)
        return table

    def _language_designer(self):
        bar = ttk.Frame(self.language_tab)
        bar.pack(fill="x", pady=(0, 10))
        ttk.Label(bar, text="Language name").pack(side="left")
        self.name = tk.StringVar()
        ttk.Entry(bar, textvariable=self.name, width=32).pack(side="left", padx=8)
        self.name.trace_add("write", lambda *_: self._profile_changed())
        for label, callback in [("RicePy++ preset", lambda: self.preset("ricepy")),
                                ("MiniCalc preset", lambda: self.preset("calculator")),
                                ("Open profile", self.open_profile), ("Save profile", self.save_profile)]:
            ttk.Button(bar, text=label, command=callback).pack(side="left", padx=3)
        self.language_feedback = tk.StringVar(value="Edit token rules and grammar, then validate with F7.")
        ttk.Label(self.language_tab, textvariable=self.language_feedback, style="Muted.TLabel", wraplength=1000, padding=(0, 5)).pack(side="bottom", fill="x")
        split = ttk.Panedwindow(self.language_tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=5)
        split.add(right, weight=5)
        ttk.Label(left, text="1 / TOKEN RULES", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=7)
        ttk.Label(left, text="Higher priority wins; longest match breaks ties. Earlier rows win remaining ties.",
                  style="Muted.TLabel", wraplength=500).pack(anchor="w", pady=(0, 8))
        self.rule_table = self._table(left, ("name", "priority", "channel"), ("Name", "Priority", "Channel"), (170, 70, 90))
        self.rule_table.bind("<<TreeviewSelect>>", self._rule_selected)
        form = ttk.Frame(left, padding=(0, 8))
        form.pack(fill="x")
        form.columnconfigure(1, weight=3)
        form.columnconfigure(5, weight=1)
        self.fields = {}
        layouts = [
            ("name", "Name", 0, 0, 1, 1),
            ("priority", "Priority", 0, 2, 3, 1),
            ("channel", "Channel", 0, 4, 5, 1),
            ("pattern", "Regex", 1, 0, 1, 5),
            ("label", "Label / error", 2, 0, 1, 5),
        ]
        for key, label, row, label_col, field_col, span in layouts:
            ttk.Label(form, text=label).grid(row=row, column=label_col, sticky="w", padx=(0, 6), pady=4)
            value = tk.StringVar()
            self.fields[key] = value
            value.trace_add("write", lambda *_: self._field_changed())
            if key == "channel":
                widget = ttk.Combobox(form, textvariable=value, values=("token", "skip", "comment", "error"), width=8, state="readonly")
            elif key == "priority":
                widget = ttk.Spinbox(form, textvariable=value, from_=-100, to=100, width=4)
            else:
                widget = ttk.Entry(form, textvariable=value, width=12 if key == "name" else 1)
            widget.grid(row=row, column=field_col, columnspan=span, sticky="ew", padx=(0, 5), pady=4)
        self.selected_rule = None
        self.form_loading = False
        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        for label, callback in [("Apply", self.apply_rule), ("Add", self.add_rule), ("Delete", self.delete_rule)]:
            ttk.Button(buttons, text=label, command=callback, width=7).pack(side="left", padx=(0, 5))
        for text, direction in [("Up", -1), ("Down", 1)]:
            ttk.Button(buttons, text=text, width=5, command=lambda delta=direction: self.move_rule(delta)).pack(side="left", padx=(0, 4))
        # Reserve the rule form before giving remaining height to the token list.
        # Otherwise a small/high-DPI window can push Apply/Add/Delete offscreen.
        self.rule_table.master.pack_forget()
        form.pack_forget()
        buttons.pack_forget()
        buttons.pack(side="bottom", fill="x")
        form.pack(side="bottom", fill="x")
        self.rule_table.configure(height=5)
        self.rule_table.master.pack(fill="both", expand=True)
        ttk.Label(right, text="2 / SYNTAX GRAMMAR", font=("Segoe UI", 11, "bold"), padding=(10, 7)).pack(anchor="w")
        ttk.Label(right, text="Lowercase rules, UPPERCASE tokens. Start with start: ...\nUse | for alternatives, ? optional, * zero or more, + one or more.",
                  style="Muted.TLabel", padding=(10, 0, 0, 8), wraplength=480).pack(anchor="w")
        self.grammar = self._editor(right)
        self.grammar.bind("<<Modified>>", self._grammar_changed)
        self.context = tk.BooleanVar()
        context_toggle = ttk.Checkbutton(right, text="RicePy context checks (loop control and function returns)",
                                        variable=self.context, command=self._profile_changed)
        # Reserve this control before the expanding grammar editor.
        self.grammar.pack_forget()
        horizontal = self.grammar.horizontal_scrollbar
        horizontal.pack_forget()
        context_toggle.pack(side="bottom", anchor="w", padx=10, pady=8)
        horizontal.pack(side="bottom", fill="x")
        self.grammar.pack(fill="both", expand=True)

    def _cursor(self, event=None):
        line, column = self.source.index("insert").split(".")
        self.cursor.set(f"Line {line}, column {int(column) + 1}")

    def new_document(self, text="", path=None, title=None):
        self.document_serial += 1
        frame = ttk.Frame(self.source_tabs)
        editor = self._editor(frame)
        document = Document(frame, editor, title or (Path(path).name if path else f"Untitled {self.document_serial}"), path)
        self.documents.append(document)
        self.source_tabs.add(frame, text=document.title)
        self.active_document = document
        editor.bind("<<Modified>>", lambda event, doc=document: self._document_changed(doc))
        for tag, options in {
            "keyword": dict(foreground="#2457b5"), "literal": dict(foreground="#8a286e"),
            "comment": dict(foreground="#557260"), "problem": dict(background="#ffe3e5", underline=True),
            "selection_target": dict(background="#dbe8ff"), "search_match": dict(background="#ffecad"),
        }.items():
            editor.tag_configure(tag, **options)
        editor.bind("<KeyRelease>", self._cursor, add=True)
        editor.bind("<ButtonRelease-1>", self._cursor, add=True)
        editor.insert("1.0", text)
        editor.mark_set("insert", "1.0")
        editor.edit_modified(False)
        editor.edit_reset()
        self.source_tabs.select(frame)
        if hasattr(self, "outputs"):
            self.cancel(silent=True)
            self._clear_results()
            self._update_document_title(document)
            self.status.set("New source tab · F5 runs the active document")
            self.tabs.select(self.workbench)
            editor.focus_set()
        return document

    def _update_document_title(self, document):
        title = Path(document.path).name if document.path else document.title
        self.source_tabs.tab(document.frame, text=("* " if document.dirty else "") + title)
        if document is self.active_document:
            self.file_label.set(document.path or title)

    def _document_changed(self, document):
        if document.editor.edit_modified():
            document.editor.edit_modified(False)
            if not self.loading:
                document.dirty = True
                self._update_document_title(document)
                if document is self.active_document:
                    self.invalidate("Source changed · run analysis to refresh results")
                else:
                    document.result = None

    def _source_changed(self, event=None):
        self._document_changed(self.active_document)

    def _document_selected(self, event=None):
        selected = self.source_tabs.select()
        document = next((doc for doc in self.documents if str(doc.frame) == selected), None)
        if document is None or document is self.active_document:
            return
        self.cancel(silent=True)
        self.active_document = document
        self._update_document_title(document)
        self._clear_results()
        if document.result is not None:
            self._render(document.result, record_history=False)
        else:
            self.status.set("Ready · analyze this document with F5")
        self._cursor()
        self.source.focus_set()

    def close_document(self):
        self._source_changed()
        if not self._discard_source():
            return False
        self.cancel(silent=True)
        document = self.active_document
        index = self.documents.index(document)
        self.documents.remove(document)
        self.source_tabs.forget(document.frame)
        document.frame.destroy()
        self.active_document = None
        if not self.documents:
            self.new_document()
        else:
            self.source_tabs.select(self.documents[min(index, len(self.documents) - 1)].frame)
            self._document_selected()
        return True

    def focus_find(self):
        self.tabs.select(self.workbench)
        self.search_entry.focus_set()
        self.search_entry.selection_range(0, "end")

    def find_next(self):
        text = self.search.get()
        self.source.tag_remove("search_match", "1.0", "end")
        if not text:
            return
        start = self.source.search(text, "insert+1c", stopindex="end", nocase=True)
        if not start:
            start = self.source.search(text, "1.0", stopindex="end", nocase=True)
        if start:
            self.source.tag_add("search_match", start, start + f"+{len(text)}c")
            self.source.mark_set("insert", start)
            self.source.see(start)
            self.status.set("Match found · F3 finds the next match")
        else:
            self.status.set("No match in this source tab")

    def _grammar_changed(self, event=None):
        if self.grammar.edit_modified():
            self.grammar.edit_modified(False)
            self._profile_changed()

    def _profile_changed(self):
        if not self.loading:
            self.profile_dirty = True
            self.language_feedback.set("Language edited · validate with F7 when ready")
            self._invalidate_language("Language changed · all source tabs need fresh analysis")

    def _invalidate_language(self, message):
        self.cancel(silent=True)
        for document in self.documents:
            document.result = None
        self._clear_results()
        self.status.set(message)

    def _field_changed(self):
        if not self.loading and not getattr(self, "form_loading", True):
            self.rule_dirty = True
            self._profile_changed()

    def invalidate(self, message):
        self.cancel(silent=True)
        if self.result is not None:
            self.result = None
            self._clear_results()
        else:
            self._friendly_clear()
        self.status.set(message)

    def _clear_results(self):
        for table in (self.tokens, self.tree, self.diagnostics):
            table.delete(*table.get_children())
        self.tree_locations.clear()
        for tag in ("keyword", "literal", "comment", "problem", "selection_target"):
            self.source.tag_remove(tag, "1.0", "end")
        self._friendly_clear()
        self.token_count.set("Analyze code to explore its words and symbols.")
        self.tree_count.set("No current syntax tree.")
        if hasattr(self, "metrics"):
            for variable in self.metrics.values():
                variable.set("—")
        if hasattr(self, "diagnostic_detail"):
            self._set_detail("Select a diagnostic to see its full message and repair hint.")

    def _set_source(self, source, path=None):
        self.source.delete("1.0", "end")
        self.source.insert("1.0", source)
        self.source.mark_set("insert", "1.0")
        self.source.edit_modified(False)
        self.source.edit_reset()
        self.source_path = path
        self.source_dirty = False
        self._update_document_title(self.active_document)
        self.invalidate("Ready · run pipeline or inspect tokens")

    def _refresh_rules(self, index=0):
        self.rule_table.delete(*self.rule_table.get_children())
        for i, rule in enumerate(self.rules):
            self.rule_table.insert("", "end", iid=str(i), values=(rule["name"], rule["priority"], rule["channel"]))
        self.selected_rule = None
        self.rule_dirty = False
        if self.rules:
            index = min(index, len(self.rules) - 1)
            self.rule_table.selection_set(str(index))
            self.rule_table.see(str(index))
            self._show_rule(index)

    def _show_rule(self, index):
        self.form_loading = True
        self.selected_rule = index
        for key, variable in self.fields.items():
            variable.set(self.rules[index].get(key, ""))
        self.form_loading = False
        self.rule_dirty = False

    def _rule_selected(self, event=None):
        selection = self.rule_table.selection()
        if not selection:
            return
        index = int(selection[0])
        if index == self.selected_rule:
            return
        if self.rule_dirty and not self.apply_rule():
            self.rule_table.selection_set(str(self.selected_rule))
            return
        self._show_rule(index)

    def apply_rule(self):
        if self.selected_rule is None:
            return True
        try:
            candidate = {key: value.get() for key, value in self.fields.items()}
            candidate["priority"] = int(candidate["priority"])
            rules = list(self.rules)
            rules[self.selected_rule] = candidate
            Profile.from_dict(dict(version=1, name="Validation", rules=rules, grammar="start:"))
        except (ValueError, TypeError) as exc:
            self.language_feedback.set(str(exc))
            self.show_language_settings()
            return False
        self.rules = rules
        self.rule_table.item(str(self.selected_rule), values=(candidate["name"], candidate["priority"], candidate["channel"]))
        self.rule_dirty = False
        return True

    def add_rule(self):
        if self.rule_dirty and not self.apply_rule():
            return
        names = {r["name"] for r in self.rules}
        index = 1
        while f"TOKEN_{index}" in names:
            index += 1
        self.rules.append(dict(name=f"TOKEN_{index}", pattern="TODO", priority=0, channel="token", label=""))
        self._refresh_rules(len(self.rules) - 1)
        self._profile_changed()

    def delete_rule(self):
        if self.selected_rule is not None:
            del self.rules[self.selected_rule]
            self._refresh_rules()
            self._profile_changed()

    def move_rule(self, direction):
        if self.selected_rule is None or (self.rule_dirty and not self.apply_rule()):
            return
        destination = self.selected_rule + direction
        if 0 <= destination < len(self.rules):
            self.rules[self.selected_rule], self.rules[destination] = self.rules[destination], self.rules[self.selected_rule]
            self._refresh_rules(destination)
            self._profile_changed()

    def current_profile(self):
        if self.rule_dirty and not self.apply_rule():
            raise ValueError(self.language_feedback.get())
        return Profile.from_dict(dict(version=1, name=self.name.get(), rules=self.rules,
                                     grammar=self.grammar.get("1.0", "end-1c"), context_checks=self.context.get()))

    def _load_profile(self, profile):
        previous = self.loading
        self.loading = True
        self.profile = profile
        self.rules = profile.to_dict()["rules"]
        self.name.set(profile.name)
        self.context.set(profile.context_checks)
        self.grammar.delete("1.0", "end")
        self.grammar.insert("1.0", profile.grammar)
        self.grammar.edit_modified(False)
        self.grammar.edit_reset()
        self._refresh_rules()
        self.profile_dirty = False
        self.loading = previous
        self.language_feedback.set("Edit token rules and grammar, then validate with F7.")
        self._invalidate_language("Language loaded · all source tabs need fresh analysis")

    def _discard_source(self):
        if not self.source_dirty:
            return True
        answer = messagebox.askyesnocancel("Unsaved source", f"Save changes to {self.active_document.title} before closing?", parent=self.root)
        if answer is None:
            return False
        return self.save_source() if answer else True

    def _discard_profile(self):
        if not self.profile_dirty:
            return True
        answer = messagebox.askyesnocancel("Unsaved language", "Save language edits before replacing or closing this profile?", parent=self.root)
        if answer is None:
            return False
        return self.save_profile() if answer else True

    def preset(self, name):
        if not self._discard_profile():
            return
        self._load_profile(ricepy_profile() if name == "ricepy" else calculator_profile())

    def generate(self):
        self.tabs.select(self.examples_tab)

    def open_source(self):
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Source", "*.ricepy *.txt *.src"), ("All files", "*.*")])
        if path:
            try:
                if Path(path).stat().st_size > 1_000_000:
                    raise ValueError("Source file exceeds 1 MB.")
                content = Path(path).read_text(encoding="utf-8-sig")
                existing = next((doc for doc in self.documents if doc.path and Path(doc.path).resolve() == Path(path).resolve()), None)
                if existing:
                    self.source_tabs.select(existing.frame)
                    self._document_selected()
                else:
                    self.new_document(content, path=path)
            except (OSError, UnicodeError, ValueError) as exc:
                self._file_error(exc)

    def save_source(self, save_as=False):
        path = None if save_as else self.source_path
        if not path:
            path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".ricepy", initialfile=Path(self.source_path).name if self.source_path else "program.ricepy")
        if not path:
            return False
        try:
            if any(doc is not self.active_document and doc.path and Path(doc.path).resolve() == Path(path).resolve() for doc in self.documents):
                raise ValueError("This file is already open in another tab. Save to a different path.")
            atomic_write(path, self.source.get("1.0", "end-1c"))
            self.source_path = path
            self.active_document.title = Path(path).name
            self.source_dirty = False
            self.source.edit_modified(False)
            self._update_document_title(self.active_document)
            self.status.set("Source saved")
            return True
        except (OSError, UnicodeError, ValueError) as exc:
            self._file_error(exc)
            return False

    def open_profile(self):
        if not self._discard_profile():
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Language profiles", "*.json")])
        if path:
            try:
                self._load_profile(Profile.load(path))
            except (OSError, UnicodeError, ValueError) as exc:
                self._file_error(exc)

    def save_profile(self):
        try:
            profile = self.current_profile()
            path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".json", initialfile="language.json")
            if path:
                atomic_write(path, profile.to_json() + "\n")
                self.profile_dirty = False
                self.status.set("Language profile saved")
                return True
        except (OSError, UnicodeError, ValueError) as exc:
            self._file_error(exc)
        return False

    def run(self, mode="pipeline"):
        if self.job is not None:
            self.status.set("A check is already running. Cancel it to stop.")
            return
        if mode == "validate":
            self.show_language_settings()
        elif not self.source.get("1.0", "end-1c").strip():
            self._source_changed()
            self._clear_results()
            self._set_banner("Add some code first", "Type a few lines, open a file, or choose a ready-made example.")
            self.summary_title.set("Nothing to check yet")
            self.summary_text.set("Examples can create a small program for you. Open one, then click Analyze code.")
            self.tabs.select(self.workbench)
            self.outputs.select(self.summary_tab)
            return
        try:
            self.root.focus_set()
            self.root.update_idletasks()
            profile = self.current_profile()
            self.invalidate("Analyzing… · editing source or language cancels this run")
            self._clear_results()
            self.job = self.worker.submit(self.source.get("1.0", "end-1c"), profile, mode)
            self.progress.pack(side="right", padx=6)
            self.progress.start(12)
            self._busy(True)
            self._set_banner("Checking language settings..." if mode == "validate" else "Checking your code...",
                             "You can cancel this check at any time. Your code will not be executed.")
            self.poll_id = self.root.after(40, self._poll)
        except (ValueError, OSError) as exc:
            self._file_error(exc)

    def _poll(self):
        self.poll_id = None
        if self.job is None:
            return
        try:
            result = self.job.poll()
        except (RuntimeError, TimeoutError, OSError) as exc:
            self.job = None
            self._busy(False)
            self._set_banner("The check could not finish", str(exc), "warning")
            self.progress.stop()
            self.progress.pack_forget()
            self.status.set(str(exc))
            messagebox.showerror("Analysis", str(exc), parent=self.root)
            return
        if result is None:
            self.poll_id = self.root.after(40, self._poll)
            return
        self.job = None
        self._busy(False)
        self.progress.stop()
        self.progress.pack_forget()
        self.progress["value"] = 0
        self.result = result
        self._render(result)

    def cancel(self, silent=False):
        self._busy(False)
        if hasattr(self, "progress"):
            self.progress.stop()
            self.progress.pack_forget()
            self.progress["value"] = 0
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.job is not None:
            self.job.close()
            self.job = None
            if not silent:
                self.status.set("Check cancelled. Your code is safe.")
                self._set_banner("Check cancelled", "Your code has not been changed. Choose Analyze code when you are ready.")

    def _render(self, result, record_history=True):
        self._clear_results()
        tokens = result["tokens"]
        source_text = self.source.get("1.0", "end-1c")
        self._filter_tokens()
        for token in tokens[:5000]:
            tag = "comment" if token["channel"] == "comment" else "keyword" if token["label"] == "keyword" else "literal" if "literal" in token["label"] else None
            if tag:
                self.source.tag_add(tag, f"1.0+{token['offset']}c", f"1.0+{token['end']}c")
        for index, diagnostic in enumerate(result["diagnostics"][:5000]):
            message, _ = explain_diagnostic(diagnostic, source_text)
            self.diagnostics.insert("", "end", iid=str(index), values=(STAGES.get(diagnostic["stage"], diagnostic["stage"]), f"{diagnostic['line']}:{diagnostic['column']}", message))
            if diagnostic["stage"] != "configuration":
                self.source.tag_add("problem", f"1.0+{diagnostic['offset']}c", f"1.0+{max(diagnostic['offset'] + 1, diagnostic['end'])}c")
        if result["tree"]:
            root = self._insert_tree("", result["tree"], open_node=True)
            self._expand_tree(root)
        else:
            self.tree_count.set("This mode does not produce a tree." if result["mode"] != "pipeline" else "Fix the reported error to build a syntax tree.")
        self.metrics["tokens"].set(f"{len(tokens):,}")
        self.metrics["errors"].set(str(len(result["diagnostics"])))
        self.metrics["lexer"].set(f"{result['timings']['lexer_ms']:.1f} ms" if "lexer_ms" in result["timings"] else "—")
        self.metrics["parser"].set(f"{result['timings']['parser_ms']:.1f} ms" if "parser_ms" in result["timings"] else "—")
        if result["mode"] == "validate":
            self.language_feedback.set("Language ready · token rules and LALR grammar are valid." if result["ok"] else result["diagnostics"][0]["message"][:500])
        outcome = "VALID" if result["ok"] else f"{len(result['diagnostics'])} ERROR(S)"
        self.status.set(f"{outcome} · {result['mode']} · {len(tokens):,} tokens · {result['timings']['total_ms']:.1f} ms engine time")
        self._friendly_report(result, record_history)
        if result["diagnostics"]:
            self.outputs.select(self.issues_tab)
            if result["mode"] != "validate":
                self.tabs.select(self.workbench)
            self.diagnostics.selection_set("0")
            self._select_diagnostic()
        elif result["mode"] != "validate":
            self.tabs.select(self.workbench)
            self.outputs.select(self.tokens_tab)

    def _set_detail(self, text):
        self.diagnostic_detail.configure(state="normal")
        self.diagnostic_detail.delete("1.0", "end")
        self.diagnostic_detail.insert("1.0", text)
        self.diagnostic_detail.configure(state="disabled")

    def _schedule_filter(self, *_):
        if self.filter_id is not None:
            self.root.after_cancel(self.filter_id)
        self.filter_id = self.root.after(140, self._filter_tokens)

    def _filter_tokens(self):
        if self.filter_id is not None:
            self.root.after_cancel(self.filter_id)
            self.filter_id = None
        self.tokens.delete(*self.tokens.get_children())
        if self.result is None:
            return
        query = self.token_filter.get().casefold()
        matched, shown = 0, 0
        for index, token in enumerate(self.result["tokens"]):
            if self.hide_comments.get() and token["channel"] == "comment":
                continue
            if query and not any(query in str(token[key]).casefold() for key in ("kind", "label", "value")):
                continue
            matched += 1
            if shown < 5000:
                value = token["value"].replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
                self.tokens.insert("", "end", iid=str(index), values=(token["kind"] if self.show_token_names.get() else token_name(token), value[:250], f"{token['line']}:{token['column']}"), tags=(token_group(token),))
                shown += 1
        total = len(self.result["tokens"])
        self.token_count.set(f"{matched:,} of {total:,} tokens" + (" · first 5,000 matches shown" if matched > 5000 else " · click to locate source"))

    def _insert_tree(self, parent, node, open_node=False):
        label = node["kind"] + (f"  {node['value']}" if node["value"] is not None else "")
        iid = self.tree.insert(parent, "end", text=label[:240], open=open_node)
        self.tree_locations[iid] = node
        if node["children"]:
            self.tree.insert(iid, "end", text="Expand to load…", tags=("placeholder",))
        return iid

    def _tree_open(self, event=None):
        self._expand_tree(self.tree.focus())

    def _expand_tree(self, iid):
        if iid not in self.tree_locations:
            return
        children = self.tree.get_children(iid)
        if children and "placeholder" in self.tree.item(children[0], "tags"):
            self.tree.delete(*children)
            for child in self.tree_locations[iid]["children"]:
                if len(self.tree_locations) >= 5000:
                    self.tree.insert(iid, "end", text="Display limit reached · export JSON for the complete tree")
                    break
                self._insert_tree(iid, child)
        self.tree_count.set(f"{len(self.tree_locations):,} nodes loaded · expand branches to explore")

    def _highlight(self, record):
        self.source.tag_remove("selection_target", "1.0", "end")
        start = f"1.0+{record['offset']}c"
        self.source.tag_add("selection_target", start, f"1.0+{max(record['offset'] + 1, record['end'])}c")
        self.source.see(start)

    def _select_token(self, event=None):
        selected = self.tokens.selection()
        if selected and self.result:
            self._highlight(self.result["tokens"][int(selected[0])])

    def _select_tree(self, event=None):
        selected = self.tree.selection()
        if selected and selected[0] in self.tree_locations:
            self._highlight(self.tree_locations[selected[0]])

    def _select_diagnostic(self, event=None):
        selected = self.diagnostics.selection()
        if selected and self.result:
            record = self.result["diagnostics"][int(selected[0])]
            message, hint = explain_diagnostic(record, self.source.get("1.0", "end-1c"))
            detail = f"Line {record['line']}, column {record['column']}\n{message}\n\nWhat to try: {hint}" if hint else message
            if self.technical_details.get():
                detail += f"\n\nTechnical details ({record['code']}):\n{record['message']}"
            self._set_detail(detail)
            if record["stage"] != "configuration":
                self._highlight(record)

    def _export_path(self, extension):
        # Drain pending Tk modification events before consulting cached results.
        self.root.update_idletasks()
        self._source_changed()
        self._grammar_changed()
        if self.result is None or self.rule_dirty:
            messagebox.showinfo("No current report", "Run analysis before exporting current results.", parent=self.root)
            return None
        return filedialog.asksaveasfilename(parent=self.root, defaultextension=extension, initialfile="analysis" + extension)

    def export_json(self):
        path = self._export_path(".json")
        if path:
            try:
                atomic_write(path, json.dumps(self.result, indent=2, ensure_ascii=False) + "\n")
                self.status.set("Analysis report saved")
            except (OSError, UnicodeError) as exc:
                self._file_error(exc)

    def export_csv(self):
        path = self._export_path(".csv")
        if path:
            try:
                from io import StringIO
                output = StringIO(newline="")
                writer = csv.writer(output)
                writer.writerow(["Token", "Value", "Line", "Column", "Channel"])
                for token in self.result["tokens"]:
                    value = token["value"]
                    if value.lstrip().startswith(("=", "+", "-", "@")) or value.startswith(("\t", "\r", "\n")):
                        value = "'" + value
                    writer.writerow([token["kind"], value, token["line"], token["column"], token["channel"]])
                atomic_write(path, output.getvalue())
                self.status.set("Token CSV saved")
            except (OSError, UnicodeError) as exc:
                self._file_error(exc)

    def _file_error(self, exc):
        messagebox.showerror("Compiler Studio", str(exc), parent=self.root)

    def close(self):
        if not self._discard_profile():
            return
        for document in list(self.documents):
            self.source_tabs.select(document.frame)
            self._document_selected()
            self._source_changed()
            if not self._discard_source():
                return
        self.cancel(silent=True)
        self.worker.close()
        if self.filter_id is not None:
            self.root.after_cancel(self.filter_id)
        self.root.destroy()


def launch():
    if sys.platform == "win32":
        import ctypes
        ctypes.windll.user32.SetProcessDPIAware()
    try:
        root = tk.Tk()
    except tk.TclError as exc:
        raise RuntimeError(f"Cannot start Tk. Check the Python Tcl/Tk installation and desktop display: {exc}") from exc
    Studio(root)
    root.mainloop()
