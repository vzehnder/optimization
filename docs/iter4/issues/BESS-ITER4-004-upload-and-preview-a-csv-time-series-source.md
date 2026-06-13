# BESS-ITER4-004: Upload And Preview A CSV Time-Series Source

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

22, 24, 26 through 29, 34 through 41, 58

## What to build

Add CSV source ingestion for draft time-series data.

An analyst can upload a CSV file, the app stores the original source file under
a controlled input-source area, previews rows and columns, suggests mappings for
common columns, lets the analyst confirm or correct mappings, and validates the
mapped data before it can be used to generate a `system_case`.

## Acceptance criteria

- [x] A draft can receive a CSV source file upload.
- [x] Uploaded CSV source files are stored under a configured safe source-file
      root.
- [x] The app returns preview rows and detected column names for the uploaded
      CSV.
- [x] The app suggests mappings for common columns such as timestamp, duration,
      legacy price, import price, export price, renewable availability, and load
      demand.
- [x] The analyst can save manual mapping corrections.
- [x] Validation catches missing required mappings.
- [x] Validation catches nonnumeric mapped numeric values.
- [x] Validation catches duplicate or unsorted timestamps.
- [x] Validation catches nonpositive durations.
- [x] Validation catches negative renewable availability and load demand.
- [x] Tests cover CSV parsing, preview, source-file safety, mapping suggestions,
      manual overrides, and validation errors.

## Implementation notes

- Added a CSV time-series ingestion module for source-file storage, UTF-8 CSV
  parsing, preview rows, column detection, mapping suggestions, manual mapping
  application, and mapped-row validation.
- Added configurable `INPUT_SOURCE_ROOT` / `input_source_root` support so
  uploaded source files are written under a controlled input-source root with
  path-safe stored filenames.
- Added draft API endpoints for CSV upload and mapping save:
  `/api/scenarios/{scenario_id}/draft/time-series-sources/upload` and
  `/api/scenarios/{scenario_id}/draft/time-series-sources/{source_id}/mapping`.
- Added SSR draft-page upload, preview, mapping, and validation sections that
  use the same backend behavior as the API.
- Stored source metadata, preview rows, mapping suggestions, accepted mapping,
  validation status, and validated normalized rows under the mutable draft
  `time_series` document for the next generated-case slice.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web/API/template tests: 52 passed.
- Julia package tests: 372 passed.
- Chrome DevTools MCP loaded a draft page with a stored CSV source, preview
  table, mapping form, and `Valid mapped rows: 1`; a full-page screenshot was
  saved at `.tmp/iter4_csv_draft_devtools.png`.

Browser note: attempted the requested in-app Browser workflow twice, but the
`node_repl` browser-control runtime failed locally with
`windows sandbox failed: spawn setup refresh`; Chrome DevTools MCP validation
was completed successfully.

## Blocked by

BESS-ITER4-002
