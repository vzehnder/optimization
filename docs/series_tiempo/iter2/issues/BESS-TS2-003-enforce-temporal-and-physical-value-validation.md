# BESS-TS2-003: Enforce Temporal And Physical Value Validation

Status: In Review
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-13
Fecha de termino planificada: 2026-07-14
Fecha de inicio real: 2026-07-04
Fecha de termino real: 2026-07-04

## User stories covered

12 through 16, 19

## What to build

Make imports strict enough to trust the catalog. Temporal validation must
reject duplicate timestamps, nonpositive or incoherent durations and unordered
periods, so horizons are unambiguous. Value validation must reject nonnumeric
entries and negative values for physically nonnegative signals, driven by the
signal catalog rules. Every rejection points at the source row and column that
caused it, so the analyst can fix the file quickly.

The set timezone is stored as an IANA identifier and surfaced through API and
React, with `America/Santiago` and Chile DST as the key interpretation case.
Validation lives in the centralized rules introduced with the signal catalog,
so CSV today and XLSX plus manual edits later share exactly the same behavior.
A failed import must not persist partial values.

## Acceptance criteria

- [x] Duplicate timestamps are rejected with row-tied errors.
- [x] Nonpositive or incoherent durations are rejected.
- [x] Periods are validated as ordered with coherent start/end timestamps.
- [x] Nonnumeric values produce row-and-column-tied errors.
- [x] Negative values are rejected for physically nonnegative signals per catalog rules.
- [x] A failed import persists no partial periods or values.
- [x] The set timezone is stored as an IANA identifier and visible via API and React.
- [x] Validation is centralized so CSV, XLSX and manual edit paths share the same rules.

## Implementation notes

- Temporal validation in `app/time_series_catalog.py` now rejects duplicate
  timestamps (`row N: duplicate timestamp ... already used by row M`),
  unordered timestamps, and periods that start before the previous period ends
  (incoherent duration), all tied to source rows. Malformed timestamps also
  carry the source row.
- Nonnumeric values, nonpositive durations and negative values for
  physically nonnegative signals were already rejected by the centralized
  rules; acceptance tests now lock those behaviors.
- All validation runs in `prepare_time_series_catalog_import` before any
  persistence, so a failed import writes nothing. As extra hardening for the
  autocommit PostgreSQL backend, `import_time_series_catalog_set` now deletes
  the newly created set row (cascading revisions/signals/periods/values) if an
  unexpected error interrupts child-row inserts mid-import.
- The set timezone remains an IANA identifier validated with `zoneinfo`; the
  React import confirmation now displays `<timezone> (IANA)`.

## Verification

- `.\\.venv\\Scripts\\python.exe -m unittest tests.test_ts2_time_series_catalog` (14 tests)
- `.\\.venv\\Scripts\\python.exe -m unittest discover tests` (198 ok, 1 skipped)
- `npm.cmd test` (47 ok), `npx.cmd eslint .`, `npm.cmd run build`, `npm.cmd run api:check`
- Chrome (`chrome-devtools` MCP, PostgreSQL-backed app): a duplicate-timestamp
  CSV import surfaced the alert `row 3: duplicate timestamp
  '2026-01-01T00:00:00' (already used by row 2)` and PostgreSQL kept no
  partial set; the valid import confirmation shows `America/Santiago (IANA)`.

## Blocked by

BESS-TS2-002
