# Verification — 2026-10-22

Verified locally on Windows with CPython **3.11.0**, Tcl/Tk **8.6.12**, and Lark **1.3.1**, using a fresh project virtual environment.

```text
.venv\Scripts\python -X utf8 -m unittest discover -s tests -v
Ran 29 tests — OK, no skipped tests

.venv\Scripts\python -m pip check
No broken requirements found.

.venv\Scripts\python -m compileall -q compiler_studio tests
Completed successfully.
```

Coverage includes the original assignment-2 sample; 30 seeded RicePy++ programs; assignment-1 token vocabulary; keyword boundaries; malformed numbers, identifiers, strings and comments; CRLF/LF/CR locations; precedence and associativity; empty programs/bodies; pointer/array/function/class syntax; loop/function context; malformed profiles and grammar conflicts; editable custom languages; input/tree limits; stdin and UTF-8 BOM; CLI exit statuses; safe report creation; cancellation and a deliberately pathological regex timing out.

Five tests exercise actual Tk widgets: pipeline/token/tree/source navigation, edit invalidation, custom token and grammar changes, profile save/load, JSON/CSV export, spreadsheet formula protection, file-error preservation, worker cancellation, token reordering, and controls at a 1000×800 window size. Workbench and language-designer windows were also captured and visually inspected at Windows high DPI. Clipped controls and leftover Tk timer callbacks found during checks were corrected. Desktop checks required execution outside the restricted agent sandbox so Tcl/Tk could access its installed scripts.

A representative direct-engine measurement processed **23,000 source characters / 9,000 tokens** (1,000 declarations) in **248 ms** with parser construction and **211 ms** with a cached parser. This is a local measurement, not a performance guarantee; normal GUI/CLI jobs also incur process-start overhead and intentionally do not share the direct-engine cache between jobs.

The original `tamrin1/codes` source files were compared byte-for-byte against their pre-change backup and restored unchanged. The original assignment-2 sources remain in place. Only the new Python project is prepared for publication; no assignment PDFs, credentials, environments, generated C, binaries or personal datasets are included.

Limitations: no executable-code generation, target-language execution, symbol resolution, static type checking or optimizer. RicePy syntax follows assignment 2; some assignment-1 reserved tokens are lexical-only. Parsing stops at the first syntax error. Custom languages must fit the named-token LALR grammar format. Regex conflicts still require example-based checks. Jobs have explicit size/depth/time limits and process cancellation, not an OS memory sandbox. Linux/macOS and other Python versions have not been verified locally.
