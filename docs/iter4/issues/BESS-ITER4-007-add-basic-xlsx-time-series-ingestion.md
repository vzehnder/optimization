# BESS-ITER4-007: Add Basic XLSX Time-Series Ingestion

Status: Todo
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

- [ ] A draft can receive a basic `.xlsx` source file upload.
- [ ] The app can read a selected sheet or the first sheet by default.
- [ ] The XLSX path returns preview rows and detected column names.
- [ ] The XLSX path reuses the same mapping model as CSV.
- [ ] The XLSX path reuses the same validation rules as CSV.
- [ ] The XLSX path can generate and validate a `system_case_json` through the
      same draft flow.
- [ ] Unsupported workbook structures fail with clear errors.
- [ ] Tests cover successful XLSX ingestion, sheet selection or defaulting,
      validation errors, and reuse of the generated-case path.

## Blocked by

BESS-ITER4-004, BESS-ITER4-005
