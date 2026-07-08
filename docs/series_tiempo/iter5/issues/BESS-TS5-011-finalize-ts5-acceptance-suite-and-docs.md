# BESS-TS5-011: Finalize TS-5 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-08-03
Fecha de termino planificada: 2026-08-03

## User stories covered

1 through 17 (closing proof)

## What to build

Close the iteration with proof and documentation. An acceptance suite tells
the whole TS-5 story in order: old runs remain readable and old scenario
versions immutable; a legacy draft's series extract into the generic catalog
and bind to a variant; legacy hydraulic sets read through the common adapter
while new hydraulic writes go to the generic model; on-demand migration
preserves audit metadata idempotently; stale validation stays fail-closed
across storage origins; permissions hold for analyst, admin and client; and
cleanup removes only rebuildable derived data, provably restorable through
the rebuild path.

Documentation closes the architecture change: a final architecture document
records the settled common model, the adapters, the deprecation paths and the
cardinality outcome so future PRDs do not reopen these decisions; the README
documents the unified model; a manual checklist lands at
`docs/series_tiempo/iter5/pruebas_manuales_ts5.md` (same shape as the TS-1
through TS-4 checklists); and the tracker and issues move to their closed
state.

## Acceptance criteria

- [ ] An acceptance suite proves legacy draft extraction, hydraulic adapter reads, generic-model writes, on-demand migration, stale validation, permissions and cleanup-with-rebuild coexisting with readable old runs and immutable scenario versions.
- [ ] A final architecture document records the settled common model, adapters, deprecations and the cardinality outcome so future PRDs do not reopen these decisions.
- [ ] The README documents the TS-5 unified model and deprecation paths.
- [ ] `docs/series_tiempo/iter5/pruebas_manuales_ts5.md` records the manual verification checklist.
- [ ] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [ ] The TS-5 tracker and all TS-5 issues are in their closed state.

## Blocked by

BESS-TS5-001 through BESS-TS5-010
