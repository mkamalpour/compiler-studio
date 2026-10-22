# Compiler Studio

A compiler front end written in Python: a configurable lexer, LALR parser, syntax-tree viewer, and desktop language designer. RicePy++ is the default language, combining the lexical and syntax work from two compiler-design assignments. Define another language without changing Python code.

This replaces the Flex/Bison/C build workflow with Python and Lark. It analyzes source; it does not compile Python programs, execute input, or generate executables.

## Run

Verified baseline: CPython 3.11.0 on Windows, Tk 8.6, Lark 1.3.1. No C compiler, Flex, Bison, browser, or web server is needed.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -r requirements.txt
.venv\Scripts\python -m compiler_studio
```

After setup on Windows, double-click `run.bat` to open the desktop app.

On Linux/macOS, use `.venv/bin/python`. The desktop UI needs Tkinter; some Python distributions package Tk separately. CLI analysis works without Tkinter. These platforms have not been verified locally.

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

- **Workbench:** edit source, run the complete pipeline (F5), or scan tokens only (F6). Inspect tokens, concrete syntax tree and diagnostics. Click an item to highlight its source. Generate sample programs or load/save source files.
- **Language designer:** choose RicePy++ or MiniCalc, edit token rules and the grammar, validate (F7), and save/load JSON profiles. Source and language edits immediately invalidate old results. Analysis is cancellable; reports export to JSON or token CSV.
- **Guide & history:** in-app grammar instructions, scope, limits and recent run summaries. Ctrl+O opens source; Ctrl+S saves; Ctrl+Enter runs the pipeline.

CSV exports prefix spreadsheet formula-like values with an apostrophe. JSON preserves exact lexemes.

## Make your own language

Start with **MiniCalc**. Add a token named `MINUS` with regex `\-`, priority `0`, channel `token`; click **Apply rule**. In the grammar, extend `sum`:

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
compiler_studio/  profile schema, lexer/parser engine, process isolation, CLI, Tk UI
profiles/         editable RicePy++ and MiniCalc definitions
examples/         valid programs, lexical-only vocabulary and invalid input
tests/            engine, custom language, CLI, worker and real Tk workflow checks
```

The source assignments are preserved outside this project. The new repository has no generated C, binaries, private datasets, credentials or copied assignment PDFs. No open-source license has been selected.

Analysis is bounded to 250,000 characters, 40,000 displayed-channel tokens, and 150 tree levels, with a 12-second process timeout. UI tables cap display at 5,000 items; JSON retains the complete permitted result. Lexing reports multiple errors; syntax parsing reports the first unexpected token and expected alternatives. Invalid lexing prevents syntax success. Language validation checks the rule schema and parser construction; regex conflicts and intended language behavior still need example tests.

Context checks are specific to the RicePy tree aliases and should be disabled for unrelated custom profiles. There is no symbol resolution, type checking, constant-assignment enforcement, optimizer, runtime, or machine-code backend. Custom pathological regexes can time out. The timeout isolates a job; it is not an operating-system memory sandbox. Exports contain source lexemes; review them before sharing. See `VERIFICATION.md` for checks actually run.
