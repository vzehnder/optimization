# BESS-REACT-004: Migrate Time-Series Ingestion And Editing

Status: Todo
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

- [ ] An analyst can upload supported CSV and XLSX files through multipart API
      requests from the draft editor.
- [ ] XLSX uploads support worksheet selection and explain invalid worksheet
      choices.
- [ ] The UI shows source metadata, detected columns, preview rows, and mapping
      suggestions returned by the backend.
- [ ] The analyst can map timestamps, durations, prices, load, renewable
      availability, and hydro inflows to the applicable draft assets.
- [ ] Saved mappings refresh source validation and persisted draft state.
- [ ] The analyst can edit and save source rows through the existing row
      contract.
- [ ] Source, mapping, row, and column errors are presented in actionable
      context without discarding edits.
- [ ] Upload and save progress prevent accidental duplicate submissions.
- [ ] Table rendering remains responsive for the supported realistic data size
      through bounded rendering or virtualization.
- [ ] Unsafe source paths and unsupported files remain rejected by the backend.
- [ ] Keyboard users can navigate mappings and the editable table.
- [ ] Browser acceptance covers one CSV path, one XLSX path, a corrected mapping,
      row editing, and an invalid-data path.
- [ ] Existing CSV, XLSX, mapping, draft generation, and hydro ingestion tests
      remain green.

## Blocked by

- BESS-REACT-003

