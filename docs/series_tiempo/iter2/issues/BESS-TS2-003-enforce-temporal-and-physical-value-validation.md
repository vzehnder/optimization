# BESS-TS2-003: Enforce Temporal And Physical Value Validation

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-13
Fecha de termino planificada: 2026-07-14

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

- [ ] Duplicate timestamps are rejected with row-tied errors.
- [ ] Nonpositive or incoherent durations are rejected.
- [ ] Periods are validated as ordered with coherent start/end timestamps.
- [ ] Nonnumeric values produce row-and-column-tied errors.
- [ ] Negative values are rejected for physically nonnegative signals per catalog rules.
- [ ] A failed import persists no partial periods or values.
- [ ] The set timezone is stored as an IANA identifier and visible via API and React.
- [ ] Validation is centralized so CSV, XLSX and manual edit paths share the same rules.

## Blocked by

BESS-TS2-002
