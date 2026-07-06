# BESS-TS2-004: Add XLSX Import With Sheet Selection

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-15
Fecha de termino planificada: 2026-07-16
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

2, 3, 12, 19

## What to build

Keep Excel workflows supported as a load mechanism. An analyst uploads an XLSX
as a time-series source, chooses a sheet, and the chosen sheet flows through
the same preview, mapping and validation pipeline as CSV before values land in
BBDD. Source provenance records the sheet name alongside file name, media type
and checksum.

Failure paths must be clean: choosing an invalid sheet produces a clear error,
and unsupported workbook features fail with actionable messages instead of
crashes. Tests must prove CSV and XLSX share the same centralized validation
rules rather than duplicating them.

## Acceptance criteria

- [x] An XLSX upload lists available sheets and lets the analyst choose one.
- [x] The chosen sheet flows through the same preview, mapping and validation as CSV.
- [x] Invalid sheet selection produces a clear error.
- [x] Unsupported workbook features fail with actionable messages, not crashes.
- [x] Source provenance records the sheet name alongside file metadata.
- [x] Tests prove CSV and XLSX imports share the same centralized validation rules.
- [x] React supports the sheet-selection step in the import flow.

## Implementation notes

- `app/time_series_ingestion.py`: `parse_xlsx_rows`/`parse_xlsx_preview` now also
  return the workbook's full `available_sheets` list; `ingest_xlsx_source`
  stores it on the source dict alongside the existing `selected_sheet`. An
  unknown `sheet_name` now raises a `TimeSeriesIngestionError` that names the
  requested sheet and lists the available ones, so the error is actionable
  without opening the file. Merged-cell and Excel-table workbooks already
  raised clear errors; both now have locking tests.
- No new endpoint was needed: the existing
  `POST /api/scenarios/{id}/draft/time-series-sources/upload` endpoint already
  accepted an optional `sheet_name` form field and already fed rows from any
  source kind through the same `get_time_series_source_rows` ->
  `prepare_time_series_catalog_import` pipeline used by TS2-001/002/003 for
  CSV. XLSX therefore reuses the identical centralized validation, mapping and
  catalog-import path as CSV with no duplicated logic.
- `frontend/src/DraftEditor.tsx`: replaced the pre-upload free-text "XLSX
  sheet" field with a post-upload "Sheet" `<select>` that lists
  `source.available_sheets` and defaults to `source.selected_sheet`. Changing
  the selection re-uploads the same `File` object (still referenced by the
  file input) with the newly chosen `sheet_name`, which re-parses the workbook
  and refreshes preview/mapping/validation for that sheet. This removes the
  need for an analyst to already know a sheet's exact name before uploading.
- `frontend/src/api/client.ts`: added `available_sheets?: string[]` to
  `TimeSeriesSource`.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_csv_time_series_ingestion tests.test_ts2_time_series_catalog -v`
  (15 + 16 ok): new tests cover `available_sheets` on upload, unknown sheet
  name rejection listing available sheets, merged-cell and Excel-table
  rejection, an XLSX source imported into the catalog from a non-default
  sheet, and an XLSX source triggering the same duplicate-timestamp rejection
  as CSV (proving shared centralized validation).
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests` (203 ok, 1 skipped).
- `npm test` (48 ok, +1 new test covering the sheet dropdown and re-upload
  flow), `npx tsc -b --pretty false`, `npx eslint .`, `npm run api:generate`,
  `npm run api:check`, `npm run build` all green.
- Chrome (`chrome-devtools` MCP, PostgreSQL-backed app, project "TS2 Chrome QA
  004"): uploaded a two-sheet XLSX (`Notes`, `Prices`); the "Sheet" dropdown
  listed both with `Notes` selected by default; selecting `Prices` refreshed
  the preview to that sheet's columns/rows; importing to the catalog created
  set `ts2_qa_prices` v1. PostgreSQL confirms
  `time_series_sources.selected_sheet = 'Prices'` and the 3 persisted periods
  match the `Prices` sheet content, not the default `Notes` sheet.

## Blocked by

BESS-TS2-003
