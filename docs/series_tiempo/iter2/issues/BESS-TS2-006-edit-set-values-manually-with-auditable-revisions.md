# BESS-TS2-006: Edit Set Values Manually With Auditable Revisions

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-21
Fecha de termino planificada: 2026-07-22

## User stories covered

8, 9, 10, 19, 22

## What to build

Allow small corrections without rebuilding a file. From the set detail view,
the analyst edits values in a bounded table and saves. Saving creates a new
set revision recording user and timestamp, recalculates the content hash, and
keeps prior revisions and hashes queryable, so corrections are auditable and
anything that froze an earlier hash still points at exactly the data it used.

Manual edits pass through the same centralized validation rules as imports
(nonnumeric values, negative values for nonnegative physical signals), and an
invalid edit is rejected without creating a revision. This is bounded editing
for corrections, not a full spreadsheet inside the browser.

## Acceptance criteria

- [x] Values of a set can be edited in a bounded table in React.
- [x] Saving manual edits creates a new revision with user and timestamp.
- [x] The set content hash is recalculated on each revision.
- [x] Prior revisions and their hashes remain queryable for audit.
- [x] Manual edits are validated with the same centralized rules as imports.
- [x] An invalid edit is rejected without creating a revision or changing values.
- [x] Backend tests prove revision creation, hash updates and validation reuse.

## Blocked by

BESS-TS2-003, BESS-TS2-005
