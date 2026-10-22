"""Tk desktop workbench. Source and language profiles stay local."""

import csv
import json
import os
from pathlib import Path
import tempfile
import sys
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from tkinter.scrolledtext import ScrolledText

from .profiles import Profile, ricepy_profile, calculator_profile
from .worker import Job

ROOT = Path(__file__).resolve().parent.parent
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


class Studio:
    def __init__(self, root):
        self.root = root
        self.profile = ricepy_profile()
        self.rules = [dict(item) for item in self.profile.to_dict()["rules"]]
        self.job = None
        self.poll_id = None
        self.result = None
        self.source_path = None
        self.source_dirty = False
        self.profile_dirty = False
        self.rule_dirty = False
        self.loading = True
        self.history = []
        self.root.title("Compiler Studio — Python language workbench")
        width = min(1280, self.root.winfo_screenwidth() - 60)
        height = min(900, self.root.winfo_screenheight() - 100)
        self.root.geometry(f"{width}x{height}")
        self.root.minsize(min(980, width), min(800, height))
        self.root.configure(bg=BG)
        self._style()
        self._build()
        self._load_profile(self.profile)
        self._set_source((ROOT / "examples" / "ricepy.ricepy").read_text(encoding="utf-8"))
        self.loading = False
        self.root.protocol("WM_DELETE_WINDOW", self.close)
        for shortcut, callback in [("<F5>", self.run), ("<Control-Return>", self.run),
                                   ("<F6>", lambda: self.run("lexer")), ("<F7>", lambda: self.run("validate")),
                                   ("<Control-o>", self.open_source), ("<Control-s>", self.save_source)]:
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

    def _build(self):
        header = ttk.Frame(self.root, padding=(22, 16, 22, 10))
        header.pack(fill="x")
        ttk.Label(header, text="Compiler Studio", style="Title.TLabel").pack(side="left")
        ttk.Label(header, text="PYTHON  /  LEXER + PARSER", style="Muted.TLabel").pack(side="right")
        subtitle = ttk.Frame(self.root, padding=(23, 0, 22, 12))
        subtitle.pack(fill="x")
        ttk.Label(subtitle, text="Define a language. Inspect every token. Understand its structure.", style="Muted.TLabel").pack(side="left")
        self.profile_name = tk.StringVar()
        ttk.Label(subtitle, textvariable=self.profile_name, foreground=BLUE).pack(side="right")
        toolbar = ttk.Frame(self.root, padding=(18, 0, 18, 12))
        toolbar.pack(fill="x")
        for index, (text, command, accent) in enumerate([
            ("Run pipeline  F5", self.run, True), ("Lexer only  F6", lambda: self.run("lexer"), False),
            ("Validate language  F7", lambda: self.run("validate"), False), ("Cancel", self.cancel, False),
            ("Open source", self.open_source, False), ("Save source", self.save_source, False),
            ("Export report", self.export_json, False), ("Export tokens", self.export_csv, False),
        ]):
            ttk.Button(toolbar, text=text, command=command, style="Accent.TButton" if accent else "TButton").grid(row=index // 4, column=index % 4, sticky="ew", padx=3, pady=2)
        for column in range(4):
            toolbar.columnconfigure(column, weight=1)
        self.tabs = ttk.Notebook(self.root)
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 10))
        self.workbench = ttk.Frame(self.tabs, padding=10)
        self.language_tab = ttk.Frame(self.tabs, padding=10)
        self.guide_tab = ttk.Frame(self.tabs, padding=12)
        self.tabs.add(self.workbench, text="Workbench")
        self.tabs.add(self.language_tab, text="Language designer")
        self.tabs.add(self.guide_tab, text="Guide & history")
        self._workbench()
        self._language_designer()
        self._guide()
        self.status = tk.StringVar(value="Ready · F5 analyzes source; F6 scans tokens only")
        self.tabs.pack_forget()
        ttk.Label(self.root, textvariable=self.status, padding=(22, 5, 20, 12), style="Muted.TLabel").pack(side="bottom", fill="x")
        self.tabs.pack(fill="both", expand=True, padx=20, pady=(0, 10))

    def _workbench(self):
        split = ttk.Panedwindow(self.workbench, orient="horizontal")
        split.pack(fill="both", expand=True)
        left, right = ttk.Frame(split), ttk.Frame(split)
        split.add(left, weight=5)
        split.add(right, weight=6)
        source_bar = ttk.Frame(left)
        source_bar.pack(fill="x", pady=(0, 8))
        self.file_label = tk.StringVar(value="SOURCE / untitled")
        ttk.Label(source_bar, textvariable=self.file_label, font=("Segoe UI", 11, "bold")).pack(side="left")
        ttk.Button(source_bar, text="Generate sample", command=self.generate).pack(side="right", padx=5)
        self.source = self._editor(left)
        self.source.bind("<<Modified>>", self._source_changed)
        self.source.tag_configure("keyword", foreground="#2457b5")
        self.source.tag_configure("literal", foreground="#8a286e")
        self.source.tag_configure("comment", foreground="#557260")
        self.source.tag_configure("problem", background="#ffe3e5", underline=True)
        self.source.tag_configure("selection_target", background="#dbe8ff")
        self.source.bind("<KeyRelease>", self._cursor)
        self.source.bind("<ButtonRelease-1>", self._cursor)
        self.cursor = tk.StringVar(value="Line 1, column 1")
        ttk.Label(left, textvariable=self.cursor, style="Muted.TLabel", padding=5).pack(anchor="w")
        self.outputs = ttk.Notebook(right)
        self.outputs.pack(fill="both", expand=True, padx=(10, 0))
        tokens_tab, tree_tab, diagnostics_tab = [ttk.Frame(self.outputs, padding=6) for _ in range(3)]
        self.outputs.add(tokens_tab, text="Tokens")
        self.outputs.add(tree_tab, text="Syntax tree")
        self.outputs.add(diagnostics_tab, text="Diagnostics")
        self.token_count = tk.StringVar(value="Run analysis to inspect the token stream.")
        ttk.Label(tokens_tab, textvariable=self.token_count, style="Muted.TLabel", wraplength=520).pack(anchor="w", pady=(2, 8))
        self.tokens = self._table(tokens_tab, ("kind", "value", "location"), ("Token", "Value", "Line:col"), (145, 250, 70))
        self.tokens.bind("<<TreeviewSelect>>", self._select_token)
        self.tree_count = tk.StringVar(value="A successful parse produces a concrete syntax tree.")
        ttk.Label(tree_tab, textvariable=self.tree_count, style="Muted.TLabel", wraplength=520).pack(anchor="w", pady=(2, 8))
        self.tree = self._table(tree_tab, (), (), (), tree=True)
        self.tree.heading("#0", text="Grammar rule / token")
        self.tree.bind("<<TreeviewSelect>>", self._select_tree)
        self.diagnostics = self._table(diagnostics_tab, ("stage", "location", "message"), ("Stage", "Line:col", "Message"), (85, 70, 380))
        self.diagnostics.bind("<<TreeviewSelect>>", self._select_diagnostic)
        self.tree_locations = {}

    @staticmethod
    def _editor(parent, height=15):
        editor = ScrolledText(parent, wrap="none", undo=True, font=("Consolas", 11),
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
        form.columnconfigure(1, weight=1)
        self.fields = {}
        for row, (key, label) in enumerate([("name", "Token name"), ("pattern", "Regex pattern"),
                                           ("priority", "Priority"), ("channel", "Channel"), ("label", "Display / error label")]):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 8), pady=3)
            value = tk.StringVar()
            self.fields[key] = value
            value.trace_add("write", lambda *_: self._field_changed())
            widget = ttk.Combobox(form, textvariable=value, values=("token", "skip", "comment", "error"), state="readonly") if key == "channel" else ttk.Entry(form, textvariable=value)
            widget.grid(row=row, column=1, sticky="ew", pady=3)
        self.selected_rule = None
        self.form_loading = False
        buttons = ttk.Frame(left)
        buttons.pack(fill="x")
        for label, callback in [("Apply rule", self.apply_rule), ("Add rule", self.add_rule), ("Delete rule", self.delete_rule)]:
            ttk.Button(buttons, text=label, command=callback).pack(side="left", padx=(0, 5))
        for text, direction in [("Up", -1), ("Down", 1)]:
            ttk.Button(buttons, text=text, command=lambda delta=direction: self.move_rule(delta)).pack(side="left", padx=(0, 4))
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

    def _guide(self):
        text = ScrolledText(self.guide_tab, wrap="word", font=("Segoe UI", 11), bg="white", fg=INK, relief="flat", padx=18, pady=15)
        text.pack(fill="both", expand=True)
        text.insert("1.0", """YOUR COMPILER FRONT END, IN PYTHON

SOURCE → REGEX LEXER → TOKENS → LALR PARSER → SYNTAX TREE → CONTEXT CHECKS

Run pipeline (F5) checks both lexical and grammatical structure. Lexer only (F6) keeps scanning separate from grammar. Validate language (F7) checks your token rules and builds the parser without requiring valid source.

Click a token, tree node or diagnostic to select its source text. Edits invalidate results immediately. Exports always describe the current source and language. Large results remain complete in JSON; tables display up to 5,000 items.

DESIGNING A LANGUAGE

Start with MiniCalc to experiment. In Language designer, add or select a token rule, edit its regex and click Apply rule. Add a MINUS token with pattern \\- and extend the sum rule with: | sum MINUS product -> subtraction. Validate, then test 9 - 2 * 3. No Python code changes are required.

Token channels:
  token — shown in the table and passed to the parser.
  skip — whitespace or other discarded text.
  comment — shown in the table, ignored by the parser.
  error — shown as a lexical diagnostic, preventing a successful parse.

Regexes use Python re syntax. Higher priority wins before match length. Equal priority and length use the first row. Keyword patterns need word boundaries so intValue remains an identifier. Patterns must never match empty text. Unknown characters are errors; nothing is silently dropped.

Syntax rules use Lark's EBNF. Use named tokens from the rule table, not inline literals or regexes. Rule names are lowercase; token names are uppercase. -> alias names a tree branch. Grammar imports/directives and embedded Python actions are disabled. Save profiles as JSON to reuse or share language definitions. LALR conflicts must be resolved by changing the grammar; arbitrary ambiguous grammars are not supported.

RICEPY++ DEFAULT

The default profile follows assignment 2: int function add(a: int, b: int) { return a + b; }, calls such as answer := add(1, 2);, classes using begin/end, and semicolons after if/elif/else and while blocks. It supports pointers, one-dimensional arrays, global and const declarations, arithmetic, comparisons and boolean expressions. break/continue require a loop body. return requires a function.

Assignment 1's full token vocabulary remains available in lexer-only mode, including for, self, derives and ^. These are not syntax extensions in assignment 2. Operators use conventional left/right and less/greater display labels where the old files disagree. Strings have no embedded double quotes or line breaks; comments use # or triple double quotes. // is not a source comment.

SCOPE & LIMITS

This is a compiler front end, not a Python-source compiler or executable-code generator. It does not evaluate source, infer types, resolve symbols, enforce const assignments or run programs. The tree is a concrete syntax tree, preserving punctuation. Lexing reports multiple errors; parsing stops at the first syntax error with expected token names.

Analysis runs in a separate process with a 12-second timeout. Limits: 250,000 source characters, 40,000 visible tokens, 150 syntax-tree levels. A custom pathological regex can time out; cancel or simplify it. Files and profiles stay local. Open/save/export never use network services.

Keyboard: F5 / Ctrl+Enter pipeline · F6 lexer · F7 validate · Ctrl+O open · Ctrl+S save
""")
        text.configure(state="disabled")
        self.history_text = tk.StringVar(value="Session history appears after analysis.")
        ttk.Label(self.guide_tab, textvariable=self.history_text, style="Muted.TLabel", wraplength=1100, padding=(0, 10)).pack(fill="x")

    def _cursor(self, event=None):
        line, column = self.source.index("insert").split(".")
        self.cursor.set(f"Line {line}, column {int(column) + 1}")

    def _source_changed(self, event=None):
        if self.source.edit_modified():
            self.source.edit_modified(False)
            if not self.loading:
                self.source_dirty = True
                self.invalidate("Source changed · run analysis to refresh results")

    def _grammar_changed(self, event=None):
        if self.grammar.edit_modified():
            self.grammar.edit_modified(False)
            self._profile_changed()

    def _profile_changed(self):
        if not self.loading:
            self.profile_dirty = True
            self.invalidate("Language changed · validate or run the pipeline")

    def _field_changed(self):
        if not self.loading and not getattr(self, "form_loading", True):
            self.rule_dirty = True
            self._profile_changed()

    def invalidate(self, message):
        self.cancel(silent=True)
        if self.result is not None:
            self.result = None
            self._clear_results()
        self.status.set(message)

    def _clear_results(self):
        for table in (self.tokens, self.tree, self.diagnostics):
            table.delete(*table.get_children())
        self.tree_locations.clear()
        for tag in ("keyword", "literal", "comment", "problem", "selection_target"):
            self.source.tag_remove(tag, "1.0", "end")
        self.token_count.set("Results need analysis.")
        self.tree_count.set("No current syntax tree.")

    def _set_source(self, source, path=None):
        self.source.delete("1.0", "end")
        self.source.insert("1.0", source)
        self.source.edit_modified(False)
        self.source.edit_reset()
        self.source_path = path
        self.source_dirty = False
        self.file_label.set("SOURCE / " + (Path(path).name if path else "untitled"))
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
            messagebox.showerror("Token rule", str(exc), parent=self.root)
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
            raise ValueError("Correct the selected token rule before continuing.")
        return Profile.from_dict(dict(version=1, name=self.name.get(), rules=self.rules,
                                     grammar=self.grammar.get("1.0", "end-1c"), context_checks=self.context.get()))

    def _load_profile(self, profile):
        previous = self.loading
        self.loading = True
        self.profile = profile
        self.rules = profile.to_dict()["rules"]
        self.name.set(profile.name)
        self.profile_name.set(profile.name)
        self.context.set(profile.context_checks)
        self.grammar.delete("1.0", "end")
        self.grammar.insert("1.0", profile.grammar)
        self.grammar.edit_modified(False)
        self.grammar.edit_reset()
        self._refresh_rules()
        self.profile_dirty = False
        self.loading = previous
        self.invalidate("Language loaded · existing results cleared")

    def _discard_source(self):
        return not self.source_dirty or messagebox.askyesno("Unsaved source", "Discard unsaved source edits?", parent=self.root)

    def _discard_profile(self):
        return not self.profile_dirty or messagebox.askyesno("Unsaved language", "Discard unsaved language edits?", parent=self.root)

    def preset(self, name):
        if not self._discard_profile():
            return
        self._load_profile(ricepy_profile() if name == "ricepy" else calculator_profile())

    def generate(self):
        if not self._discard_source():
            return
        if self.name.get().startswith("RicePy"):
            from .samples import ricepy_sample
            source = ricepy_sample()
        elif self.name.get().startswith("MiniCalc"):
            from .samples import calculator_sample
            source = calculator_sample()
        else:
            messagebox.showinfo("Custom language", "Samples are available for the RicePy++ and MiniCalc presets. Use your own source for a custom profile.", parent=self.root)
            return
        self._set_source(source)

    def open_source(self):
        if not self._discard_source():
            return
        path = filedialog.askopenfilename(parent=self.root, filetypes=[("Source", "*.ricepy *.txt *.src"), ("All files", "*.*")])
        if path:
            try:
                if Path(path).stat().st_size > 1_000_000:
                    raise ValueError("Source file exceeds 1 MB.")
                content = Path(path).read_text(encoding="utf-8-sig")
                self._set_source(content, path)
            except (OSError, UnicodeError, ValueError) as exc:
                self._file_error(exc)

    def save_source(self):
        path = filedialog.asksaveasfilename(parent=self.root, defaultextension=".ricepy", initialfile=Path(self.source_path).name if self.source_path else "program.ricepy")
        if path:
            try:
                atomic_write(path, self.source.get("1.0", "end-1c"))
                self.source_path = path
                self.source_dirty = False
                self.file_label.set("SOURCE / " + Path(path).name)
                self.status.set("Source saved")
            except (OSError, UnicodeError) as exc:
                self._file_error(exc)

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
        except (OSError, UnicodeError, ValueError) as exc:
            self._file_error(exc)

    def run(self, mode="pipeline"):
        try:
            self.root.focus_set()
            self.root.update_idletasks()
            profile = self.current_profile()
            self.invalidate("Analyzing… · editing source or language cancels this run")
            self._clear_results()
            self.profile_name.set(profile.name)
            self.job = Job(self.source.get("1.0", "end-1c"), profile, mode)
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
            self.status.set(str(exc))
            messagebox.showerror("Analysis", str(exc), parent=self.root)
            return
        if result is None:
            self.poll_id = self.root.after(40, self._poll)
            return
        self.job = None
        self.result = result
        self._render(result)

    def cancel(self, silent=False):
        if self.poll_id is not None:
            self.root.after_cancel(self.poll_id)
            self.poll_id = None
        if self.job is not None:
            self.job.close()
            self.job = None
            if not silent:
                self.status.set("Analysis cancelled")

    def _render(self, result):
        self._clear_results()
        tokens = result["tokens"]
        for index, token in enumerate(tokens[:5000]):
            value = token["value"].replace("\r", "\\r").replace("\n", "\\n").replace("\t", "\\t")
            self.tokens.insert("", "end", iid=str(index), values=(token["kind"], value[:250], f"{token['line']}:{token['column']}"))
            tag = "comment" if token["channel"] == "comment" else "keyword" if token["label"] == "keyword" else "literal" if "literal" in token["label"] else None
            if tag:
                self.source.tag_add(tag, f"1.0+{token['offset']}c", f"1.0+{token['end']}c")
        self.token_count.set(f"{len(tokens):,} tokens · comments shown, whitespace skipped" + (" · first 5,000 displayed" if len(tokens) > 5000 else ""))
        for index, diagnostic in enumerate(result["diagnostics"][:5000]):
            self.diagnostics.insert("", "end", iid=str(index), values=(diagnostic["stage"], f"{diagnostic['line']}:{diagnostic['column']}", diagnostic["message"]))
            if diagnostic["stage"] != "configuration":
                self.source.tag_add("problem", f"1.0+{diagnostic['offset']}c", f"1.0+{max(diagnostic['offset'] + 1, diagnostic['end'])}c")
        if result["tree"]:
            pending = [("", result["tree"], 0)]
            count = 0
            while pending and count < 5000:
                parent, node, depth = pending.pop()
                label = node["kind"] + (f"  {node['value']}" if node["value"] is not None else "")
                iid = self.tree.insert(parent, "end", text=label[:240], open=depth < 3)
                self.tree_locations[iid] = node
                pending.extend((iid, child, depth + 1) for child in reversed(node["children"]))
                count += 1
            self.tree_count.set(f"{count:,} tree nodes displayed" + (" · display capped at 5,000; JSON contains the full tree" if pending else " · click a node to locate its source"))
        else:
            self.tree_count.set("Lexer-only and language-validation modes do not produce a tree." if result["mode"] != "pipeline" else "Fix the reported error to build a syntax tree.")
        outcome = "VALID" if result["ok"] else f"{len(result['diagnostics'])} ERROR(S)"
        self.status.set(f"{outcome} · {result['mode']} · {len(tokens):,} tokens · {result['timings']['total_ms']:.1f} ms engine time")
        self.history.append(self.status.get())
        self.history = self.history[-5:]
        self.history_text.set("RECENT RUNS\n" + "\n".join(reversed(self.history)))
        if result["diagnostics"]:
            self.outputs.select(2)
            if result["diagnostics"][0]["stage"] != "configuration":
                self.tabs.select(self.workbench)
        elif result["mode"] != "validate":
            self.tabs.select(self.workbench)
            self.outputs.select(0)

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
        if not self._discard_source() or not self._discard_profile():
            return
        self.cancel(silent=True)
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
