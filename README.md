# Compiler Studio

A compiler front end written in Python: a configurable lexer, LALR parser, syntax-tree viewer, and desktop language designer. RicePy++ is the default language, combining the lexical and syntax work from two compiler-design assignments. Define another language without changing Python code.

This replaces the Flex/Bison/C build workflow with Python and Lark. It analyzes source; it does not compile Python programs, execute input, or generate executables.

## Open the app on Windows

1. Open a terminal and activate an existing compatible Python/Conda environment with Lark and Tkinter.
2. Run **run.bat** from that activated terminal. The launcher uses your active environment and never creates an environment or installs packages. Activate an existing environment with Lark and Tkinter first.
3. Click **Analyze code**, or open **Examples**, choose a topic and click **Analyze this example**.

The app starts with four simple lines. No grammar configuration is needed to use the default RicePy++ language. `run.bat --check` verifies the local setup without opening a window. Source files and checks stay local; analysis does not execute the source program.

## Manual setup / CLI

Verified baseline: CPython 3.11.0 on Windows, Tk 8.6, Lark 1.3.1. No C compiler, Flex, Bison, browser, or web server is needed.

```powershell
conda activate base  # Or activate another existing compatible environment.
# Optional dependency setup; requires explicit permission and connectivity.
python -m pip install -r requirements.txt
python -m compiler_studio
```

On Linux/macOS, use Python from an existing compatible environment. The desktop UI needs Tkinter; some Python distributions package Tk separately. CLI analysis works without Tkinter. These platforms have not been verified locally.

```text
python -m compiler_studio examples/ricepy.ricepy
python -m compiler_studio examples/lexical.ricepy --mode lexer
python -m compiler_studio examples/calculator.src --preset calculator
python -m compiler_studio --profile profiles/minicalc.json --mode validate
python -m compiler_studio examples/ricepy.ricepy --json report.json
python -m unittest discover -s tests -v
```

Exit status: `0` valid, `1` analysis errors, `2` file/setup/timeout errors. CLI reports are opt-in and refuse to overwrite existing files; `--json -` writes JSON to stdout. Use `-` as the source path to read stdin. Source files are UTF-8, with optional BOM. CRLF, LF and CR line endings have consistent locations.

## Desktop workflow

- **Analyze:** edit or open files in separate tabs, then choose **Analyze code** for token and grammar checks together. Colored tokens appear immediately after a successful check; Summary explains the result; Issues offers a repair hint and **Jump to problem**. Tokens uses readable names such as "Whole number", with technical names optional. Structure shows expandable grammar branches. Clear is undoable with Ctrl+Z. Report and token export buttons stay visible below all result tabs; the Export menu also provides both formats.
- **Examples:** choose visible topic buttons and difficulty options to generate Variables, Conditions, Loops, Functions, Classes, Arrays & pointers, or a Complete program at Simple, Standard or Advanced difficulty. Preview and edit before opening a new tab. MiniCalc offers small arithmetic examples. Switching an example's language asks before replacing shared settings, and keeps source tabs.
- **Statistics:** counts and a chart describe the active tab's tokens, with honest stage status and measured engine timings. Token-only checks clearly say grammar was not checked.
- **History:** up to 50 check summaries for this session. Selecting a row shows its summary; clearing history keeps source and current results. History does not save source files.
- **Help:** plain-language getting-started steps, common RicePy++ mistakes, save/export guidance and keyboard shortcuts.

**Language settings** is always visible as its own tab; **Customize language** also opens it. The editor supports custom token rules, grammar editing, validation (F7) and saved JSON profiles. Source edits invalidate that document's report; shared language edits invalidate reports in every tab. Analysis remains cancellable and isolated from the UI. An unchecked example preview is never shown as having passed.

Shortcuts: F5 / Ctrl+Enter analyze, F6 tokens only, Ctrl+N new tab, Ctrl+O open, Ctrl+S save, Ctrl+Shift+S save as, Ctrl+W close tab, Ctrl+Tab switch tabs, Ctrl+F/F3 find, Tab/Shift+Tab indent. Modified files and language profiles offer Save/Discard/Cancel protection.

CSV exports prefix spreadsheet formula-like values with an apostrophe. JSON preserves exact lexemes.

## Make your own language

Open **Customize language** and start with the **MiniCalc preset**. Add a token named `MINUS` with regex `\-`, priority `0`, channel `token`; click **Apply**. In the grammar, extend `sum`:

```text
?sum: sum PLUS product -> addition
    | sum MINUS product -> subtraction
    | product
```

Validate, then analyze `9 - 2 * 3`. Save the language as a profile. You can change keywords, identifier/number patterns, comments, operators, precedence and statement structure in the same way. Full example profiles are in `profiles/`.

Token patterns use Python `re`. At each position, highest priority wins, then longest match, then earliest row. Channels are `token`, `comment` (visible, parser ignores), `skip`, and `error`. Patterns must consume text. Unknown characters always produce diagnostics. Regex matching has Python regex semantics; it does not search all possible matches within an individual pattern.

Grammar rules use [Lark EBNF](https://lark-parser.readthedocs.io/en/stable/grammar.html): lowercase rule names, uppercase token names, `|` alternatives, `?`, `*`, `+` repetition, and `-> alias` tree names. Use named tokens from the rule table rather than inline literals. The start rule is `start`. Grammar imports/directives and Python actions are disabled. Ambiguous grammars may require refactoring for LALR. No profile Python code is executed.

## RicePy++ language

The default syntax follows assignment 2 and the original `parser.y`, with context checks added for loop control and returns:

```text
int function add(a: int, b: int) { return a + b; }
int answer;
answer := add(1, 2);
while (answer < 10) { answer = answer + 1; };
class Counter begin int value = 0; end
```

Supported: decimal/hex/decimal-fraction literals, booleans, strings, comments, declarations, pointers, one-dimensional arrays, `global`, `const`, function definitions/calls, classes, `if/elif/else`, `while`, arithmetic and boolean/comparison precedence. Control blocks require the final semicolon. Empty bodies are accepted. `void` is a function return type, not a variable type. `break/continue` require a loop, and `return` requires a function. Array indexing is one-dimensional.

The original lexer vocabulary also includes `for`, `self`, `derives` and `^`; these remain visible in lexer-only mode but have no default syntax production in assignment 2. `global`, `const`, `function`, `:` and `:=` extend assignment 1 for assignment 2. Conventional less/greater and bracket labels resolve inconsistencies between the original files. This is a combined profile, not a byte-for-byte reproduction of legacy output.

Strings use double quotes, have no embedded double quotes (including escaped quotes), and cannot span lines. Comments are `#` and triple double quotes, not `//`. `.2`, `2.`, `0x`, `0xZZ`, digit-prefixed names, and leading underscores are rejected.

## Structure and verification

```text
compiler_studio/  compiler engine, profiles, worker, CLI, editor, guided UI and example library
profiles/         editable RicePy++ and MiniCalc definitions
examples/         valid programs, lexical-only vocabulary and invalid input
tests/            engine, custom language, CLI, worker and real Tk workflow checks
```

`engine.py` implements analysis; `profiles.py` validates and loads language definitions; `worker.py` isolates cancellable jobs. `gui.py` and `friendly_ui.py` provide the desktop workflows; `editor.py` handles source editing. `presentation.py` translates diagnostics and token names into readable UI text without altering compiler reports. `example_library.py` supplies the guided lessons; `samples.py` generates larger seeded programs used by lessons and regression checks. `__main__.py` provides desktop/CLI entry points; `__init__.py` records the app version.

The JSON profiles are editable language examples, not generated caches. `assignment2.ricepy` preserves the original syntax test; `ricepy.ricepy` demonstrates the combined language; `lexical.ricepy` exercises lexer-only vocabulary; `invalid.ricepy` demonstrates errors; `calculator.src` demonstrates a different language. `requirements.txt` pins the runtime dependency, `run.bat` handles Windows setup/launch, and the Git settings keep line endings consistent and local data out of commits. `VERIFICATION.md` records actual checks and their limits.

The source assignments are preserved outside this project. The new repository has no generated C, binaries, private datasets, credentials or copied assignment PDFs. No open-source license has been selected.

Analysis is bounded to 250,000 characters, 40,000 displayed-channel tokens, and 150 tree levels, with a 12-second process timeout. UI tables cap display at 5,000 items; JSON retains the complete permitted result. Lexing reports multiple errors; syntax parsing reports the first unexpected token and expected alternatives. Invalid lexing prevents syntax success. Language validation checks the rule schema and parser construction; regex conflicts and intended language behavior still need example tests.

The scanner conservatively dispatches rules by required first character while preserving priority, longest-match and row-order semantics. Complex regexes use exhaustive candidate matching. The desktop reuses one isolated worker and its parser cache between completed runs; cancellation or timeout discards that process, and the next run starts a clean one. CLI jobs remain single-use. The local 9,000-token benchmark improved from 206.6 ms to 111.3 ms median total engine time (seven warm runs per version); this is a local measurement, not a universal speed guarantee.

Context checks are specific to the RicePy tree aliases and should be disabled for unrelated custom profiles. There is no symbol resolution, type checking, constant-assignment enforcement, optimizer, runtime, or machine-code backend. Custom pathological regexes can time out. The timeout isolates a job; it is not an operating-system memory sandbox. Exports contain source lexemes; review them before sharing. See `VERIFICATION.md` for checks actually run.
Current lightweight check (Windows, existing Conda base / Python 3.13.5): **49 passed, 0 skipped**. No dependency installs, model downloads, live publishing, or heavy datasets were used. The suite also reports 171 passing subtests.
