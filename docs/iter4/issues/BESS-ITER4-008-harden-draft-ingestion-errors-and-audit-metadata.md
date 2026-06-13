# BESS-ITER4-008: Harden Draft Ingestion Errors And Audit Metadata

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

34 through 41, 46, 49, 60

## What to build

Harden the structured editor ingestion path so errors are clear and promoted
versions retain useful input provenance.

The app should distinguish source-file parsing errors, mapping errors, Python
validation errors, Julia validation errors, and execution errors. Promoted
versions should retain enough metadata to audit the source file and mapping used
to generate the immutable `system_case`.

## Acceptance criteria

- [x] CSV parsing errors are shown as source-file errors.
- [x] XLSX parsing errors are shown as source-file errors.
- [x] Missing or invalid mappings are shown as mapping errors.
- [x] Data quality failures are shown as Python validation errors.
- [x] Julia contract failures are shown separately from Python validation
      errors.
- [x] Run execution failures continue to use the Iteration 3 failed-run audit
      path.
- [x] Promoted versions retain source filename, source media type, stored source
      path or safe source identifier, mapping metadata, and generation timestamp.
- [x] Unsafe source-file paths are not exposed through API or UI.
- [x] Tests cover the error categories and version-level audit metadata.

## Implementation notes

- Added structured ingestion error categories for source-file parsing,
  mapping, Python data validation, and Julia contract validation responses.
- Added SSR draft-page labels for source-file and time-series validation error
  categories.
- Added immutable scenario-version generation metadata for editor-promoted
  versions, including source filename, source media type, safe source
  identifier/stored filename, accepted mapping, and generation timestamp.
- Kept promoted-version provenance safe by omitting absolute source paths from
  exposed generation metadata.
- Preserved the existing Iteration 3 run failure audit path for execution
  failures.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web/API/template/results tests: 65 passed.
- Julia package tests: 372 passed.
- Chrome DevTools MCP verified local structured-draft error taxonomy through
  the API and rendered draft page. It confirmed `source_file`, `mapping`, and
  `python_validation` categories and the `Time-Series Validation: Python
  Validation Error` UI label.
- In-app Browser was attempted twice, but the local `node_repl` browser-control
  runtime failed with `windows sandbox failed: spawn setup refresh`.

## Blocked by

BESS-ITER4-005, BESS-ITER4-007
