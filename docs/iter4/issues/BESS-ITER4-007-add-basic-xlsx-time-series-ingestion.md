# BESS-ITER4-007: Add Basic XLSX Time-Series Ingestion

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter4/prd_structured_editor_flow.md`

## User stories covered

23, 25, 34 through 41

## What to build

Add basic XLSX ingestion to the same draft source-file, preview, mapping, and
validation flow used by CSV.

The XLSX path should support a selected sheet or first-sheet default. It should
not attempt formulas, named ranges, complex multi-table sheets, unit conversion,
or advanced ETL.

## Acceptance criteria

- [x] A draft can receive a basic `.xlsx` source file upload.
- [x] The app can read a selected sheet or the first sheet by default.
- [x] The XLSX path returns preview rows and detected column names.
- [x] The XLSX path reuses the same mapping model as CSV.
- [x] The XLSX path reuses the same validation rules as CSV.
- [x] The XLSX path can generate and validate a `system_case_json` through the
      same draft flow.
- [x] Unsupported workbook structures fail with clear errors.
- [x] Tests cover successful XLSX ingestion, sheet selection or defaulting,
      validation errors, and reuse of the generated-case path.

## Implementation notes

- Added `openpyxl` as the basic XLSX parser dependency for the Python web app.
- Added a shared time-series source ingestion entry point that dispatches CSV
  and XLSX uploads through the same draft source-file contract.
- XLSX uploads store the original workbook under the configured input-source
  root, read the first sheet by default, and can read a selected sheet from the
  upload form/API field.
- XLSX preview rows, columns, mapping suggestions, manual mapping saves,
  mapped-row validation, and generated-case conversion reuse the existing CSV
  mapping and validation model.
- Unsupported formulas, merged cells, Excel tables, missing sheets, empty
  headers, and duplicate headers fail with explicit ingestion errors.
- The draft page now accepts `.csv` and `.xlsx` files and shows the selected
  XLSX sheet for uploaded workbook sources.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_csv_time_series_ingestion tests.test_draft_generated_system_case -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Focused CSV/XLSX ingestion and generated-case tests: 15 passed.
- Full Python web/API/template/results tests: 63 passed.
- Julia package tests: 372 passed.
- Chrome DevTools MCP loaded a seeded draft page at
  `http://127.0.0.1:8027/scenarios/1/draft`, confirmed the XLSX source,
  selected sheet, preview rows, mapped-row validation, and generated-case
  preview, found no console messages, and saw the document request return HTTP
  200.

Browser note: attempted the requested in-app Browser workflow twice, including a
runtime reset, but the `node_repl` browser-control runtime failed locally with
`windows sandbox failed: spawn setup refresh`. Chrome DevTools MCP verification
completed successfully.

## Blocked by

BESS-ITER4-004, BESS-ITER4-005
