# BESS-TS5-011: Finalize TS-5 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-08-03
Fecha de termino planificada: 2026-08-03
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

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

- [x] An acceptance suite proves legacy draft extraction, hydraulic adapter reads, generic-model writes, on-demand migration, stale validation, permissions and cleanup-with-rebuild coexisting with readable old runs and immutable scenario versions.
- [x] A final architecture document records the settled common model, adapters, deprecations and the cardinality outcome so future PRDs do not reopen these decisions.
- [x] The README documents the TS-5 unified model and deprecation paths.
- [x] `docs/series_tiempo/iter5/pruebas_manuales_ts5.md` records the manual verification checklist.
- [x] The full Python and frontend suites, `tsc -b`, `eslint .`, the API drift check and the production build pass.
- [x] The TS-5 tracker and all TS-5 issues are in their closed state.

## Blocked by

BESS-TS5-001 through BESS-TS5-010

## Implementation Notes

Closing proof issue; no production-code hardening was needed because
BESS-TS5-001 through BESS-TS5-010 already implement the TS-5 behavior end to
end. Added `tests.test_ts5_acceptance` (TDD, one behavior at a time) with
nine tests: legacy draft extraction binding to a variant and materializing
the case; the hydraulic legacy adapter and a new generic write coexisting
side by side in the same diagram; on-demand hydraulic migration idempotent
with origin metadata and an untouched legacy row/binding; stale validation
failing closed for both an extracted-series binding and a migrated-hydraulic
binding; the permission matrix holding across catalog, hydraulic adapter and
case-variant surfaces for client/analyst/admin; old runs staying readable via
artifact fallback while cleanup removes only rebuildable result indexes and
rebuild restores them; a historical scenario version's row-level immutability
enforced at the SQLite trigger level; and a closing test asserting the
README, this issue, the tracker and the new manual/architecture docs are all
in their closed/final state. Four of the nine tests failed on first run for
test-fixture reasons only (materialize's return shape nests under
`system_case`, not top-level; `create_scenario_version`'s returned dict omits
the document unless `include_document=True`; two hydraulic test fixtures need
a second reservoir node to avoid a duplicate `case_hydraulic_time_series_bindings`
key when both a generic and a legacy series exist in the same diagram) — no
production code changed to make them pass, confirming BESS-TS5-001 through
BESS-TS5-010 already satisfy the end-to-end TS-5 contract.

Added `docs/series_tiempo/iter5/architecture_ts5_final.md`, the final
architecture document closing Decision Record item 8 (architecture-closure
criteria): the per-path strategy table, adapters and deprecation paths, the
confirmed one-to-one cardinality outcome, the permission matrix and the
retention boundary, all as settled reference for future PRDs (TS-6). Added a
new README section ("TS-5: Migration, Unification And Hardening")
summarizing the same model, the per-path migration strategy, cardinality/
labels, permissions/retention and cross-origin stale validation, plus the
acceptance-verification commands. Added
`docs/series_tiempo/iter5/pruebas_manuales_ts5.md`, a manual checklist
covering extraction, hydraulic adapter/migration, cross-origin staleness, the
permission matrix, cleanup/rebuild and scenario-version immutability,
following the same shape as the TS-1 through TS-4 checklists. Updated
`docs/series_tiempo/iter5/issues/tracker_ts5.md` to mark this issue Done and
record the focused acceptance command in the final verification block.

Backend full suite green: `.\.venv\Scripts\python.exe -m unittest discover -s
tests -v` -> 405 tests, 2 skipped, 0 failures (the acceptance suite's
documentation test is the only one that starts red, and only until this
issue's own doc edits land). Frontend green: `npm test -- --run` (66 tests),
`npx tsc -b`, `npx eslint .`, `npm run api:check` (with
`DATABASE_URL=sqlite:///:memory:` to avoid import-time contention with the
live PostgreSQL dev DB), `npm run build`.

Verified in Chrome against the real PostgreSQL dev DB, reusing existing QA
projects since this issue only adds proof and docs, not new behavior: on
`TS5-002 Chrome QA` (project 39) confirmed the catalog page still separates
the generic and legacy-hydraulic sections correctly; on `TS5-004 Chrome QA`
(project 41) confirmed the previously migrated hydraulic set's detail page
still shows "Ya migrado a" on load with no console errors; on run `28`
(`TS4 Hydro Diagram Project`) confirmed the results page still renders
tables/charts and the "NOMBRE DEL CASO" label (TS5-006/007) with no console
errors. No regressions found.
