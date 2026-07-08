# BESS-TS5-009: Add Retention And Cleanup For Rebuildable Derived Data

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-30
Fecha de termino planificada: 2026-07-30

## User stories covered

9

## What to build

Implement the retention rules accepted in BESS-TS5-000 so the database does
not grow without control, while immutable audit data stays untouchable. The
core distinction: derived data that can be rebuilt (run result indexes and
similar) may be cleaned; audit data that cannot (artifacts, scenario version
snapshots, sources, revision history) may not.

An admin can remove rebuildable derived data for a run or a project, and the
system refuses — with a clear reason — to delete immutable audit data through
the cleanup path. The end-to-end proof closes the loop with TS-4: clean a
run's indexed results, verify the run still renders from artifacts, then
rebuild its indexes from artifacts using the existing rebuild path and verify
BBDD-first reads return.

Cleanup decisions live in a deep module testable without the UI, cleanup is
idempotent, and each execution reports removed, kept and failed items stably.
Retention rules are documented for admins.

## Acceptance criteria

- [ ] An admin can remove rebuildable derived data for a run or project without deleting artifacts, snapshots, sources or revision history.
- [ ] Cleaned run results keep rendering from artifacts and can be re-indexed using the existing rebuild path.
- [ ] The cleanup path refuses to remove immutable audit data and reports why.
- [ ] Cleanup is idempotent and reports removed/kept/failed stably across repeated runs.
- [ ] Retention rules are documented for admins.

## Blocked by

BESS-TS5-000
