# BESS-TS2-008: Harden Bulk Import Performance And Audit Metadata

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-27
Fecha de termino planificada: 2026-07-28
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

12, 21, 22

## What to build

Make the catalog dependable at realistic scale and fully auditable. Value
persistence must use bulk insert behavior so files with realistic horizons
(for example a year of hourly periods with several signals) import efficiently
instead of row by row. Error reporting is hardened across every path: any
validation failure names the source, sheet when applicable, column and row
that caused it, consistently for CSV, XLSX, replacement and manual edits.

Revision audit metadata is completed and verified end to end: every revision
records author, date, originating source and which revision it superseded, and
that trail survives file replacement and manual edits. No new user-facing
features beyond better errors; this slice closes the robustness gaps before
the acceptance suite.

## Acceptance criteria

- [x] Value persistence uses bulk insert behavior suitable for realistic file sizes.
- [x] A realistic-size import (a year of hourly periods, several signals) completes without row-by-row inserts.
- [x] Validation errors consistently report source, sheet, column and row across CSV and XLSX paths.
- [x] Every revision records author, date, originating source and superseded revision.
- [x] Audit metadata survives file replacement and manual edits.
- [x] Backend tests cover these behaviors at API/domain boundaries, not table implementation details.

## Blocked by

BESS-TS2-006, BESS-TS2-007
