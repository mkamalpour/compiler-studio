"""Everyday workflows: examples, readable results, statistics and session history."""

from collections import Counter
import tkinter as tk
from tkinter import ttk, messagebox
from tkinter.scrolledtext import ScrolledText

from .example_library import TOPICS, LEVELS, make_example
from .presentation import report_summary, token_group, explain_diagnostic
from .profiles import ricepy_profile, calculator_profile


class FriendlyUI:
    def _build_banner(self, parent):
        self.banner = tk.Frame(parent, bg="#eaf1ff", padx=16, pady=10)
        self.banner.pack(fill="x", padx=20, pady=(3, 10))
        self.banner_title = tk.StringVar(value="Start with a small example")
        self.banner_detail = tk.StringVar(value="Edit the code or open a file, then click Analyze code.")
        self.banner_heading = tk.Label(self.banner, textvariable=self.banner_title, font=("Segoe UI", 16, "bold"),
                                       bg="#eaf1ff", fg="#204eaa", anchor="w")
        self.banner_heading.pack(fill="x")
        self.banner_text = tk.Label(self.banner, textvariable=self.banner_detail, font=("Segoe UI", 10),
                                    bg="#eaf1ff", fg="#425773", anchor="w", justify="left", wraplength=1100)
        self.banner_text.pack(fill="x", pady=(2, 0))
        self.banner.bind("<Configure>", lambda event: self.banner_text.configure(wraplength=max(250, event.width - 35)))

    def _set_banner(self, title, detail, tone="ready"):
        colors = {"ready": ("#eaf1ff", "#204eaa"), "success": ("#e8f6ee", "#216444"),
                  "warning": ("#fff2df", "#914910")}
        background, foreground = colors[tone]
        self.banner.configure(bg=background)
        self.banner_heading.configure(bg=background, fg=foreground)
        self.banner_text.configure(bg=background)
        self.banner_title.set(title)
        self.banner_detail.set(detail)

    def _build_summary(self):
        self.summary_tab = ttk.Frame(self.outputs, padding=16)
        self.outputs.insert(0, self.summary_tab, text="Summary")
        exports = ttk.Frame(self.summary_tab)
        exports.pack(side="bottom", anchor="w", pady=(10, 0))
        self.report_button = ttk.Button(exports, text="Save report (JSON)", command=self.export_json, state="disabled")
        self.report_button.pack(side="left", padx=(0, 5))
        self.csv_button = ttk.Button(exports, text="Save tokens (CSV)", command=self.export_csv, state="disabled")
        self.csv_button.pack(side="left")
        self.summary_title = tk.StringVar(value="Your results will appear here")
        self.summary_text = tk.StringVar(value="Write code or choose an example, then click Analyze code.")
        ttk.Label(self.summary_tab, textvariable=self.summary_title, font=("Segoe UI", 15, "bold"),
                  wraplength=400, justify="left").pack(anchor="w", pady=(4, 10))
        ttk.Label(self.summary_tab, textvariable=self.summary_text, wraplength=400, justify="left").pack(anchor="w", pady=(0, 12))
        self.check_explanation = tk.StringVar(value="A token is a word or symbol. Grammar describes how those pieces fit together.")
        ttk.Label(self.summary_tab, textvariable=self.check_explanation, wraplength=400, justify="left", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        actions = ttk.Frame(self.summary_tab)
        actions.pack(anchor="w", pady=(3, 5))
        self.explore_tokens = ttk.Button(actions, text="Words & symbols", command=lambda: self.outputs.select(self.tokens_tab), state="disabled")
        self.explore_tokens.pack(side="left", padx=(0, 5))
        self.explore_structure = ttk.Button(actions, text="Code structure", command=lambda: self.outputs.select(self.structure_tab), state="disabled")
        self.explore_structure.pack(side="left")
        ttk.Button(self.summary_tab, text="Choose another example", command=lambda: self.tabs.select(self.examples_tab)).pack(anchor="w", pady=3)
        self.outputs.select(self.summary_tab)

    def _build_examples(self):
        heading = ttk.Frame(self.examples_tab)
        heading.pack(fill="x", pady=(0, 10))
        ttk.Label(heading, text="Try it with an example", font=("Segoe UI", 18, "bold")).pack(anchor="w")
        ttk.Label(heading, text="Choose a topic, preview the code, then open it in a new tab. Your existing code stays safe.",
                  style="Muted.TLabel", wraplength=900).pack(anchor="w", pady=(3, 0))
        split = ttk.Panedwindow(self.examples_tab, orient="horizontal")
        split.pack(fill="both", expand=True)
        choices, preview = ttk.Frame(split, padding=(0, 0, 12, 0)), ttk.Frame(split)
        split.add(choices, weight=3)
        split.add(preview, weight=7)
        choice_footer = ttk.Frame(choices)
        choice_footer.pack(side="bottom", fill="x")
        ttk.Label(choices, text="1  Choose a language", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 6))
        self.example_language = tk.StringVar(value="RicePy++")
        languages = ttk.Combobox(choices, textvariable=self.example_language, values=("RicePy++", "MiniCalc"), state="readonly", width=24)
        languages.pack(fill="x")
        languages.bind("<<ComboboxSelected>>", self._example_language_changed)
        ttk.Label(choices, text="2  Pick a topic", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(15, 6))
        self.example_topic = tk.StringVar(value="Variables")
        self.example_topics = ttk.Combobox(choices, textvariable=self.example_topic, values=list(TOPICS), state="readonly", width=24)
        self.example_topics.pack(fill="x")
        self.example_topics.bind("<<ComboboxSelected>>", lambda event: self.refresh_example())
        choice_footer.pack_forget()
        choice_footer.pack(fill="x", pady=(3, 0))
        ttk.Label(choice_footer, text="3  Choose a difficulty", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(12, 6))
        self.example_level = tk.StringVar(value="Simple")
        levels = ttk.Combobox(choice_footer, textvariable=self.example_level, values=LEVELS, state="readonly", width=24)
        levels.pack(fill="x")
        levels.bind("<<ComboboxSelected>>", lambda event: self.refresh_example())
        self.example_description = tk.StringVar()
        ttk.Label(choice_footer, textvariable=self.example_description, style="Muted.TLabel", wraplength=285,
                  justify="left").pack(anchor="w", pady=(14, 8))
        self.generate_button = ttk.Button(choice_footer, text="Generate another", command=self.refresh_example)
        self.generate_button.pack(fill="x", pady=4)
        actions = ttk.Frame(preview)
        actions.pack(side="bottom", fill="x", pady=(9, 0))
        ttk.Button(actions, text="Open in editor", command=self.open_example).pack(side="left")
        ttk.Button(actions, text="Analyze this example", style="Accent.TButton", command=lambda: self.open_example(analyze=True)).pack(side="right")
        ttk.Label(preview, text="Preview — you can edit this before opening it", font=("Segoe UI", 11, "bold")).pack(anchor="w", pady=(2, 8))
        self.example_preview = self._editor(preview)
        self._example_language_changed()

    def _example_language_changed(self, event=None):
        topics = list(TOPICS) if self.example_language.get() == "RicePy++" else ["Arithmetic"]
        self.example_topics.configure(values=topics)
        self.example_topic.set(topics[0])
        self.refresh_example()

    def refresh_example(self):
        topic = self.example_topic.get()
        if not topic:
            return
        self.example_description.set(TOPICS.get(topic, "Try adding and multiplying numbers. Parentheses change how an expression is grouped."))
        code = make_example(self.example_language.get(), topic, self.example_level.get())
        self.example_preview.delete("1.0", "end")
        self.example_preview.insert("1.0", code)
        self.example_preview.mark_set("insert", "1.0")
        self.example_preview.edit_reset()
        self.example_preview.edit_modified(False)

    def open_example(self, analyze=False):
        language = self.example_language.get()
        target = ricepy_profile() if language == "RicePy++" else calculator_profile()
        try:
            current = self.current_profile()
        except ValueError as exc:
            self._file_error(exc)
            return False
        if current.rules != target.rules or current.grammar.strip() != target.grammar.strip():
            if not messagebox.askyesno("Example language", f"This example uses {language}. Switch the shared language to {language}? Your source tabs will be kept; previous results will need a new check.", parent=self.root):
                return False
            if not self._discard_profile():
                return False
            self._load_profile(target)
        topic = self.example_topic.get()
        self.new_document(self.example_preview.get("1.0", "end-1c"), title=f"{language} — {topic}")
        self.source_dirty = True
        self._update_document_title(self.active_document)
        if analyze:
            self.run()
        return True

    def _build_statistics(self):
        ttk.Label(self.statistics_tab, text="Understand the current code", font=("Segoe UI", 18, "bold")).pack(anchor="w", pady=(0, 4))
        self.statistics_file = tk.StringVar(value="Analyze a file to see its numbers here.")
        ttk.Label(self.statistics_tab, textvariable=self.statistics_file, style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        cards = ttk.Frame(self.statistics_tab)
        cards.pack(fill="x", pady=(0, 14))
        self.metrics = {}
        for column, (key, label) in enumerate([("tokens", "TOKENS FOUND"), ("errors", "ISSUES TO FIX"),
                                               ("lexer", "TOKEN CHECK"), ("parser", "GRAMMAR CHECK")]):
            cards.columnconfigure(column, weight=1)
            card = ttk.Frame(cards, style="Card.TFrame", padding=(12, 8))
            card.grid(row=0, column=column, sticky="ew", padx=(0, 8))
            ttk.Label(card, text=label, style="Card.TLabel").pack(anchor="w")
            self.metrics[key] = tk.StringVar(value="—")
            ttk.Label(card, textvariable=self.metrics[key], style="Number.TLabel").pack(anchor="w")
        self.statistics_timing = tk.StringVar(value="Timing appears after a check. One millisecond (ms) is 1/1,000 of a second.")
        ttk.Label(self.statistics_tab, textvariable=self.statistics_timing, style="Muted.TLabel", wraplength=1000).pack(anchor="w", pady=(0, 14))
        self.statistics_canvas = tk.Canvas(self.statistics_tab, bg="white", highlightthickness=0, height=310)
        self.statistics_canvas.pack(fill="both", expand=True)
        self.statistics_canvas.bind("<Configure>", lambda event: self._draw_statistics())

    def _draw_statistics(self):
        if not hasattr(self, "statistics_canvas"):
            return
        canvas = self.statistics_canvas
        canvas.delete("all")
        if self.result is None:
            canvas.create_text(20, 25, anchor="nw", text="Analyze code first. This chart will show the kinds of tokens it contains.", font=("Segoe UI", 11), fill="#53647c")
            return
        counts = Counter(token_group(token) for token in self.result["tokens"])
        colors = ["#2457d6", "#2a917a", "#9359ae", "#d58a34", "#6b879d", "#be5058", "#84939f"]
        labels = ["Keywords", "Names", "Values", "Operators & symbols", "Comments", "Needs fixing", "Other tokens"]
        maximum = max(counts.values(), default=1) or 1
        available = max(100, canvas.winfo_width() - 280)
        row_height = max(18, min(55, (canvas.winfo_height() - 25) // len(labels)))
        bar_height = min(22, row_height - 5)
        for index, (label, color) in enumerate(zip(labels, colors)):
            y = 18 + index * row_height
            width = counts[label] / maximum * available
            canvas.create_text(16, y + 11, anchor="w", text=label, font=("Segoe UI", 11), fill="#344c70")
            if width:
                canvas.create_rectangle(210, y, 210 + width, y + bar_height, fill=color, outline="")
            canvas.create_text(220 + width, y + 11, anchor="w", text=str(counts[label]), font=("Segoe UI", 11, "bold"), fill="#18243b")

    def _build_history(self):
        bar = ttk.Frame(self.history_tab)
        bar.pack(fill="x", pady=(0, 6))
        ttk.Label(bar, text="Your recent checks", font=("Segoe UI", 18, "bold")).pack(side="left")
        ttk.Button(bar, text="Clear history", command=self.clear_history).pack(side="right")
        ttk.Label(self.history_tab, text="This session only · summaries do not replace saved code or reports", style="Muted.TLabel").pack(anchor="w", pady=(0, 12))
        self.run_history = []
        self.history_serial = 0
        self.history_detail = ScrolledText(self.history_tab, height=6, width=40, wrap="word", font=("Segoe UI", 10), state="disabled", relief="flat", padx=10, pady=8)
        self.history_detail.pack(side="bottom", fill="x", pady=(10, 0))
        self.history_detail.configure(state="normal")
        self.history_detail.insert("1.0", "Select a check above to read its summary. History is kept for this session only.")
        self.history_detail.configure(state="disabled")
        self.history_table = self._table(self.history_tab, ("number", "file", "mode", "result", "tokens", "time"),
                                         ("Check", "File", "Checked", "Result", "Tokens", "Time (ms)"), (55, 240, 130, 180, 75, 90))
        self.history_table.bind("<<TreeviewSelect>>", self._history_selected)

    def _history_selected(self, event=None):
        selected = self.history_table.selection()
        if not selected:
            return
        record = next((item for item in self.run_history if str(item["id"]) == selected[0]), None)
        if record:
            self.history_detail.configure(state="normal")
            self.history_detail.delete("1.0", "end")
            self.history_detail.insert("1.0", f"{record['file']}\n{record['title']}\n{record['detail']}\n\n{record['note']}")
            self.history_detail.configure(state="disabled")

    def clear_history(self):
        self.run_history.clear()
        self.history_table.delete(*self.history_table.get_children())
        self.history_detail.configure(state="normal")
        self.history_detail.delete("1.0", "end")
        self.history_detail.insert("1.0", "History cleared. Your source code and current results are unchanged.")
        self.history_detail.configure(state="disabled")

    def _build_help(self):
        help_text = ScrolledText(self.guide_tab, width=50, wrap="word", font=("Segoe UI", 11), bg="white", fg="#18243b", relief="flat", padx=22, pady=18)
        help_text.pack(fill="both", expand=True)
        help_text.insert("1.0", """GET STARTED IN THREE STEPS

1. Write code, open a file, or visit Examples.
2. Click Analyze code. This checks both tokens and grammar.
3. Read Summary. If something needs fixing, open Issues and select a row.

WHAT AM I LOOKING AT?

A token is a word or symbol in your code: a name, number, keyword or operator. The token check is also called lexical analysis. The grammar check looks at how those pieces fit together. It is also called parsing. Structure shows the groups found by the parser. The app checks code; it does not execute it or generate an executable.

TRY EXAMPLES

Pick a language, topic and difficulty. Generate another variation, edit the preview if you like, then choose Open in editor or Analyze this example. Each example opens in a new source tab. Your existing code is kept. MiniCalc is a tiny calculator language for trying the app without learning RicePy++ first.

FIX A PROBLEM

Issues shows a short explanation, its line and column, and a suggestion. Select a problem to highlight its location. Jump to problem places the cursor there so you can edit. Analyze again after fixing it. Technical details are optional. The parser stops at its first grammar error, so another error may appear after the first is fixed.

SAVE THE RIGHT THING

Save code writes your source so you can edit it later. Save report (JSON) writes the complete analysis. Save tokens (CSV) creates a table suitable for a spreadsheet. CSV values that could look like formulas are prefixed with an apostrophe; JSON keeps exact values. Analysis results become out of date when you edit code, so analyze again before saving a report.

USE MORE THAN ONE FILE

New and Open create source tabs. Each tab keeps its own code and results. Close asks whether to save modified code. Clear code can be undone with Ctrl+Z. Ctrl+Tab switches source tabs. Statistics always describes the current source tab; History keeps summaries of recent checks for this session.

CUSTOMIZE A LANGUAGE WHEN YOU ARE READY

Open the Language settings tab to customize your language. Customize language and the Tools menu also take you there. You can edit token patterns and grammar rules and save your own language profile. The language is shared by all source tabs. Changing it clears old results, but keeps source code. Use Validate language (F7) there to check the rules themselves.

SHORTCUTS

F5 / Ctrl+Enter — Analyze code
F6 — Check tokens only
Ctrl+N / Ctrl+O — New tab / Open file
Ctrl+S / Ctrl+Shift+S — Save / Save as
Ctrl+W / Ctrl+Tab — Close tab / Next tab
Ctrl+F / F3 — Find / Next match
Tab / Shift+Tab — Indent / Unindent

RICEPY++ QUICK TIPS

End declarations and assignments with ;
End the complete if/elif/else or while block with ; too.
Names start with an English letter, not a digit or underscore.
Write decimal numbers as 2.5, not .5 or 2.
Put text in double quotes on one line.
Use # for a single-line comment and triple double quotes for a multi-line comment.
The original assignment-1 vocabulary is still available through Check tokens only. Some reserved words, such as for, do not have grammar rules in assignment 2.
""")
        help_text.configure(state="disabled")

    def show_language_settings(self):
        self.tabs.add(self.language_tab, text="Language settings")
        self.tabs.select(self.language_tab)

    def _main_tab_changed(self, event=None):
        if self.job is not None:
            return
        selected = self.tabs.select()
        if selected == str(self.examples_tab):
            self._set_banner("Try an example", "Preview code here, then choose Analyze this example. The preview has not been checked yet.")
        elif selected == str(self.guide_tab):
            self._set_banner("A little help goes a long way", "Follow the steps below, or start with a ready-made example.")
        elif self.result is not None:
            summary = report_summary(self.result)
            self._set_banner(summary["title"], self.active_document.title + " · " + summary["detail"], summary["tone"])
        elif selected == str(self.language_tab):
            self._set_banner("Customize your language", "Advanced settings apply to all source tabs. Your code is kept when the rules change.")
        else:
            self._set_banner("Ready when you are", "Write or open code, then choose Analyze code. Examples is a good place to start.")

    def _busy(self, busy):
        if not hasattr(self, "analyze_button"):
            return
        self.analyze_button.configure(text="Checking…" if busy else "Analyze code  F5", state="disabled" if busy else "normal")
        self.tokens_button.configure(state="disabled" if busy else "normal")
        self.cancel_button.configure(state="normal" if busy else "disabled")

    def _friendly_clear(self):
        if not hasattr(self, "summary_title"):
            return
        language = self.name.get().split(" · ")[0] if hasattr(self, "name") else "RicePy++"
        self._set_banner("Ready when you are", f"Using {language}. Write or open code, then choose Analyze code. Examples is a good place to start.")
        self.summary_title.set("Your results will appear here")
        self.summary_text.set("Write code or choose an example, then click Analyze code.\n\nResults stay with this tab until you edit the code or language.")
        self.check_explanation.set("A token is a word or symbol. Grammar describes how those pieces fit together.")
        self.explore_tokens.configure(state="disabled")
        self.explore_structure.configure(state="disabled")
        self.report_button.configure(state="disabled")
        self.csv_button.configure(state="disabled")
        if hasattr(self, "statistics_file"):
            self.statistics_file.set("Analyze this source tab to see its numbers here.")
            self.statistics_timing.set("Timing appears after a check. One millisecond (ms) is 1/1,000 of a second.")
            self._draw_statistics()

    def _friendly_report(self, report, record_history):
        summary = report_summary(report)
        self._set_banner(summary["title"], self.active_document.title + " · " + summary["detail"], summary["tone"])
        self.summary_title.set(summary["title"])
        self.status.set(f"{summary['title']} · {len(report['tokens']):,} tokens · {report['timings']['total_ms']:.1f} ms")
        self.summary_text.set(summary["detail"])
        self.check_explanation.set(f"Words & symbols: {summary['lexer']}\nGrammar: {summary['parser']}\n\n{len(report['tokens']):,} tokens found.")
        self.explore_tokens.configure(state="normal" if report["tokens"] else "disabled")
        self.explore_structure.configure(state="normal" if report["tree"] else "disabled")
        self.metrics["lexer"].set(summary["lexer"])
        self.metrics["parser"].set(summary["parser"])
        self.report_button.configure(state="normal")
        self.csv_button.configure(state="normal")
        self.statistics_file.set(self.active_document.title + " · " + summary["title"])
        timings = report["timings"]
        self.statistics_timing.set("Engine time: " + " · ".join(f"{label}: {timings[key]:.2f} ms" for key, label in
            [("total_ms", "Total"), ("grammar_ms", "Prepare rules"), ("lexer_ms", "Tokens"), ("parser_ms", "Grammar")] if key in timings))
        self._draw_statistics()
        if record_history:
            self.history_serial += 1
            note = "No issues found."
            if report["diagnostics"]:
                note = explain_diagnostic(report["diagnostics"][0], self.source.get("1.0", "end-1c"))[0]
            record = dict(id=self.history_serial, file=self.active_document.title, title=summary["title"],
                          detail=summary["detail"], note=note)
            self.run_history.append(record)
            if len(self.run_history) > 50:
                old = self.run_history.pop(0)
                self.history_table.delete(str(old["id"]))
            mode = {"pipeline": "Tokens + grammar", "lexer": "Tokens only", "validate": "Language rules"}[report["mode"]]
            self.history_table.insert("", 0, iid=str(record["id"]), values=(record["id"], record["file"], mode, summary["title"], len(report["tokens"]), f"{timings['total_ms']:.1f}"))

    def clear_source(self):
        if not self.source.get("1.0", "end-1c"):
            return
        self.source.edit_separator()
        self.source.delete("1.0", "end")
        self.source.edit_separator()
        self._source_changed()
        self.status.set("Code cleared. Undo (Ctrl+Z) restores it.")

    def jump_to_problem(self):
        selected = self.diagnostics.selection()
        if not selected or self.result is None:
            return
        diagnostic = self.result["diagnostics"][int(selected[0])]
        if diagnostic["stage"] == "configuration":
            self.show_language_settings()
            return
        self.tabs.select(self.workbench)
        self._highlight(diagnostic)
        self.source.mark_set("insert", f"1.0+{diagnostic['offset']}c")
        self.source.focus_set()
        self._cursor()
