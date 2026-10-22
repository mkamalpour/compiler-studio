# Verification — 2026-10-22

Verified locally on Windows with CPython **3.11.0**, Tcl/Tk **8.6.12**, and Lark **1.3.1**, using the isolated project virtual environment.

```text
.venv\Scripts\python -X utf8 -m unittest discover -s tests -v
Ran 40 tests — OK, no skipped tests

.venv\Scripts\python -m pip check
No broken requirements found.

.venv\Scripts\python -m compileall -q compiler_studio tests
Completed successfully.
```

Coverage includes the original assignment-2 sample; 30 seeded RicePy++ programs; assignment-1 token vocabulary; keyword boundaries; malformed numbers, identifiers, strings and comments; CRLF/LF/CR locations; precedence and associativity; empty programs/bodies; pointer/array/function/class syntax; loop/function context; malformed profiles and grammar conflicts; editable custom languages; input/tree limits; stdin and UTF-8 BOM; CLI exit statuses; safe report creation; cancellation and a deliberately pathological regex timing out.

Twelve tests exercise actual Tk widgets: pipeline/token/tree/source navigation, edit invalidation, custom token and grammar changes, profile save/load, JSON/CSV export, spreadsheet formula protection, file-error preservation, worker cancellation, token reordering, controls at a 1000×800 window size, independent source tabs and reports, Save/Discard/Cancel behavior, duplicate-file protection, search and token filtering, lazy tree expansion, error repair details, and selection-aware block indentation, fresh undo stacks for loaded documents, cancellation on tab switching, and profile save-dialog cancellation. Workbench and language-designer windows were also captured and visually inspected at Windows high DPI. Clipped controls and leftover Tk timer callbacks found during checks were corrected. Desktop checks required execution outside the restricted agent sandbox so Tcl/Tk could access its installed scripts.

The update was compared against commit `4ef2c39` on the same runtime using 1,000 declarations (23,000 characters / 9,000 tokens), seven warm runs per implementation:

| Median engine time | Previous | Updated |
| --- | ---: | ---: |
| Lexing | 142.069 ms | 43.982 ms |
| Complete pipeline | 206.590 ms | 111.255 ms |

This is about 3.2x faster lexing and 1.9x faster total analysis for this input, not a general performance guarantee. The desktop also reuses its isolated worker and compiled-parser cache between completed jobs; cancellation and timeout kill the process. Tests verify that a subsequent job restarts cleanly. CLI jobs remain single-use and incur process-start overhead.

Scanner-equivalence tests compare optimized and exhaustive matching on generated programs, 100 deterministic randomized inputs, and custom optional/alternating/flag/backreference patterns. Both token streams and diagnostics must match. Additional checks cover reusable-worker caching/restart, structured parser repair hints, and custom-grammar context-check mismatch diagnostics.

The original `tamrin1/codes` source files were compared byte-for-byte against their pre-change backup and restored unchanged. The original assignment-2 sources remain in place. Only the new Python project is prepared for publication; no assignment PDFs, credentials, environments, generated C, binaries or personal datasets are included.

Limitations: no executable-code generation, target-language execution, symbol resolution, static type checking or optimizer. RicePy syntax follows assignment 2; some assignment-1 reserved tokens are lexical-only. Parsing stops at the first syntax error. Custom languages must fit the named-token LALR grammar format. Regex conflicts still require example-based checks. Jobs have explicit size/depth/time limits and process cancellation, not an OS memory sandbox. Linux/macOS and other Python versions have not been verified locally.
