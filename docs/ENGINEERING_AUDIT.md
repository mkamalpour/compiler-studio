# Engineering audit — 2026-10-26

Purpose: Compiler-design assignments integrated into a language-analysis desktop tool.

Classification: **C** (application and separate coursework).
Final structure: compiler_studio/ for the app; profiles/, examples/ for assignment languages; tests/. Existing capabilities and source material were retained.

| Assessment | Result |
| --- | --- |
| Idea strength | 6/10 |
| Implementation strength | 8/10 |
| Core strength | Editable language profiles, parse diagnostics and workflow tests. |
| Main limitation | Small educational grammars do not demonstrate a production compiler. |
| Readiness | Local prototype/tool with the verified baseline below; no production certification |

Scores are subjective engineering estimates, not measured product or model quality.

## Delivered

Added a repo-local run.cmd that activates the assigned existing environment, checks actual startup imports and forwards application arguments. README setup now uses this local launcher.

Assigned environment: **base**. Run `.\run.cmd --check`, then `.\run.cmd`.
The launcher installs nothing and preserves its child exit status. On this workstation
it selects the assigned interpreter; standalone clones fall back to active Python.
VS Code's local interpreter settings were aligned with the same assignment.

## Verification

- **Automated tests:** 52 passed. 1 GUI test skipped.
- **Startup check:** `run.cmd --check` passed from outside the repository;
  required startup modules were imported in the assigned environment.
- **Tested runtime:** Windows; Conda base; Python 3.13.5.
- **Data handling:** tests used temporary/synthetic fixtures. No live transactions,
  provider generation, deployment, new model downloads or package installs were performed.
- **Repository check:** origin/main fetched before publication; no pre-existing local
  changes were present. A tracked-file scan found no matches for the high-confidence
  credential patterns checked. That scan is not a guarantee that all personal data
  or arbitrary secret formats are absent. Ignored local data was not staged.
- **Limits:** optional external workflows, representative real-data quality and all
  possible platform/version combinations remain unverified.

Test command from the repository root:

```powershell
conda activate base
python -m pytest tests -q -p no:cacheprovider
```

## Next three upgrades

1. More minimal error examples.
2. Exportable parse-session traces.
3. Grammar fuzzing fixtures.

Expected benefit: clearer decisions, more reproducible workflows and stronger evidence
for quality. These are proposed upgrades, not implemented features or measured speedups.

External assets: No external models or datasets are needed; code generation is outside current scope.

No root license file is set. No license was selected or changed.
