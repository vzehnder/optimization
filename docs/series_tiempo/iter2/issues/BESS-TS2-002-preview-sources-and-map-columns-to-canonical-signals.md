# BESS-TS2-002: Preview Sources And Map Columns To Canonical Signals

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-04
Fecha de termino planificada: 2026-07-04
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

3, 4, 12, 19, 20

## What to build

Make the import flow trustworthy before data lands in BBDD. An uploaded source
can be previewed (columns plus sample rows) so the analyst confirms the file is
correct, and source columns are explicitly mapped to canonical signals from a
signal catalog. The catalog defines the allowed `signal_key` values, expected
units and validation rules, so arbitrary spreadsheet column names never leak
into the model. Mapped signals record origin unit and canonical unit, without
complex conversions.

Mapping problems (unknown columns, missing required mapping, unit mismatch)
must surface as clear errors tied to the offending source column, and the
mapping used by an import must persist on the revision for audit. The signal
catalog and mapping validation live centrally so CSV, XLSX and manual edits can
share the same rules in later slices.

## Acceptance criteria

- [x] An uploaded source can be previewed with columns and sample rows before import.
- [x] A signal catalog defines allowed signal keys, expected units and validation rules.
- [x] Column mapping resolves arbitrary source column names to canonical signal keys.
- [x] Origin unit and canonical unit are recorded on mapped signals, without complex conversion.
- [x] Unmapped or unknown columns produce clear, column-tied errors.
- [x] The mapping used by an import persists on the revision for audit.
- [x] React shows the preview-and-map step before confirming an import.
- [x] Mapping validation is centralized for reuse by later import and edit paths.

## Implementation notes

- The TS-2 deep import module now accepts multiple `signal_mappings` per import
  instead of a single `value_column`/`signal_key` pair.
- Each mapped signal persists `source_column`, `source_unit` and canonical
  `unit` on `time_series_signals`, and the revision audit metadata now exposes
  the full mapping used by the import.
- React now renders a dedicated preview-and-map step with one or more signal
  mappings before import confirmation.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ts2_time_series_catalog`
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests`
- `npm.cmd test`
- `npm.cmd run build`
- `npx.cmd eslint .`
- `npm.cmd run api:generate`
- `npm.cmd run api:check`

## Manual QA note

Attempted Chrome smoke with both `chrome:control-chrome` and
`mcp__chrome_devtools`. Automation connected to the user Chrome session, but
the local PostgreSQL-backed app could not be kept alive from this sandboxed
agent session and Chrome policy then rejected navigation to the temporary local
port used for the retry. Automated coverage above is green; manual Chrome smoke
remains pending review outside the sandbox.

Resolved 2026-07-04: Chrome smoke completed with the `chrome-devtools` MCP
against the PostgreSQL-backed app on `http://127.0.0.1:8000`. The uploaded
dual-price CSV showed the preview (detected columns plus sample rows), the
preview-and-map step auto-suggested `buy_price -> import_price_usd_per_mwh`
and `sell_price -> export_price_usd_per_mwh` with source units, and the import
confirmation listed both canonical signals. Issue closed as Done.

## Blocked by

BESS-TS2-001
