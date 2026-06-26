# BESS-REACT-004: Migrate Time-Series Ingestion And Editing

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/react_migration/prd_react_ui_migration.md`

## User stories covered

35 through 42

## What to build

Add the time-series source workflow to the React draft editor. An analyst can
upload CSV or XLSX data, select a worksheet when needed, inspect detected
columns and preview rows, review or correct mappings, edit bounded row data,
and see actionable validation results tied to the relevant source.

The slice must continue to use the existing safe input-source storage and
backend ingestion rules while keeping realistic tables responsive.

## Acceptance criteria

- [x] An analyst can upload supported CSV and XLSX files through multipart API
      requests from the draft editor.
- [x] XLSX uploads support worksheet selection and explain invalid worksheet
      choices.
- [x] The UI shows source metadata, detected columns, preview rows, and mapping
      suggestions returned by the backend.
- [x] The analyst can map timestamps, durations, prices, load, renewable
      availability, and hydro inflows to the applicable draft assets.
- [x] Saved mappings refresh source validation and persisted draft state.
- [x] The analyst can edit and save source rows through the existing row
      contract.
- [x] Source, mapping, row, and column errors are presented in actionable
      context without discarding edits.
- [x] Upload and save progress prevent accidental duplicate submissions.
- [x] Table rendering remains responsive for the supported realistic data size
      through bounded rendering or virtualization.
- [x] Unsafe source paths and unsupported files remain rejected by the backend.
- [x] Keyboard users can navigate mappings and the editable table.
- [x] Browser acceptance covers one CSV path, one XLSX path, a corrected mapping,
      row editing, and an invalid-data path.
- [x] Existing CSV, XLSX, mapping, draft generation, and hydro ingestion tests
      remain green.

## Verification

- `npm.cmd test`
- `npm.cmd run check`
- `npm.cmd run test:browser`
- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_csv_time_series_ingestion tests.test_draft_generated_system_case tests.test_structured_draft_editor -v`
- Chrome smoke: created a project/scenario/draft in Chrome, added load,
  renewable, and hydro assets, saved the draft, and confirmed the React
  time-series upload controls render with no console errors.

## Blocked by

- BESS-REACT-003
