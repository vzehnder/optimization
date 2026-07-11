# BESS-TS6-010: Finalize TS-6 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-08-13
Fecha de termino planificada: 2026-08-14
Fecha de inicio real: 2026-07-11
Fecha de termino real: 2026-07-11

## User stories covered

1 through 18

## What to build

Close the iteration by proving TS-6's contract end-to-end and leaving the
documentation in its final state, following the pattern of the TS-1 through
TS-5 closing issues.

The acceptance suite must cover the testing decisions the PRD fixes: each
allowlisted transformation proven as a pure/deep module; lineage proofs that
derived sets record inputs, revisions, parameters, schema versions and
implementation versions; stale proofs that source changes affect derived
outputs and that regeneration preserves history; connector proofs with mocked
external data landing through the common source/set path; automation proofs
that scheduled and rolling-horizon runs create the same kind of snapshots and
indexed results as manual runs; and regression proofs that manual
variant-driven runs still work unchanged. Performance tests are added only
for measured bottlenecks, per the PRD — none speculatively.

The docs close the loop: a manual test checklist
(`pruebas_manuales_ts6.md`) in the shape of the TS-1 through TS-5 ones, a
final architecture note describing the transformation layer, connector
boundary and automation semantics as implemented, a README section for TS-6,
and the tracker updated to its final state.

## Acceptance criteria

- [x] An acceptance test suite covers every allowlisted transformation as a pure/deep module, lineage, staleness/regeneration, connector ingestion with mocked data, and scheduled plus rolling-horizon automation.
- [x] Regression tests prove manual variant-driven runs are unchanged, and the full backend and frontend suites are green.
- [x] No speculative performance tests are added; any added one references a measured bottleneck.
- [x] `docs/series_tiempo/iter6/pruebas_manuales_ts6.md` exists in the shape of the TS-1 through TS-5 checklists.
- [x] A final TS-6 architecture note and a README section document the transformation layer, connector boundary and automation semantics as implemented.
- [x] The tracker register and progress log are in their final state.

## Blocked by

BESS-TS6-001 through BESS-TS6-009

## Implementation Notes

Closing proof issue; no production code changed because BESS-TS6-001 through
BESS-TS6-009 already implement the TS-6 behavior end to end. Added
`tests.test_ts6_acceptance` (TDD, one behavior at a time) with eight tests
telling one continuous story: the allowlist registry covers exactly the four
accepted transformations and rejects unknown types (pure and store level)
before anything is written; every allowlisted transformation derives a set
with full lineage (revision metadata plus generic `validation_dependencies`
rows, sources untouched, spot-checked values per type); a source edit marks
derived sets Layer-1 stale, fail-closes bound variants for materialization
AND revalidation, and regeneration appends revision 2 while revision 1 keeps
its content hash; mocked connector data lands through the common source/set
path with created/converged/new-revision semantics and per-revision program
metadata preserved across reissues; scheduled runs produce the same snapshot
contract as manual runs (identical kind/input_variant/date_range/
series_bindings, plus an automation block only on the scheduled one) and
index through the same TS-4 rebuild path; rolling schedules resolve per-tick
ranges recorded in tick and snapshot, keeping gate failures visible without
deactivating; manual variant-driven runs are unchanged while derived sets,
regenerations and schedules coexist in the same project; and a closing test
asserts the README, this issue, the tracker and the new manual/architecture
docs are in their final state. Two fixture-only fixes during TDD (seeding a
real set before the store-level allowlist rejection, and the
`validation_dependencies` helper exposing `hash` instead of
`recorded_hash`) — no production code changed to make any test pass. No
performance tests were added: no bottleneck was measured during TS-6.

Added `docs/series_tiempo/iter6/pruebas_manuales_ts6.md` (manual checklist in
the TS-1 through TS-5 shape: transformations, derived staleness/regeneration,
connector forecast/programmed, fixed and rolling schedules, manual
regression, visual review) and
`docs/series_tiempo/iter6/architecture_ts6_final.md` (final architecture
note: transformation layer and registry, two-layer staleness, connector
boundary, automation semantics, out-of-scope confirmations, closing proof).
Added the README section "TS-6: Transformations, Connectors And Automation"
with the acceptance-verification commands. Updated
`docs/series_tiempo/iter6/issues/tracker_ts6.md` to its final state.

Backend full suite green: 547 tests, 2 skipped, 0 failures. Frontend green:
`npm test -- --run` (66 tests), `npx tsc -b`, `npx eslint .`,
`npm run api:check`, `npm run build`. Julia not required: no artifact,
`system_case_json` contract or optimizer change.

Verified in Chrome against the real PostgreSQL dev DB, reusing existing QA
projects since this issue only adds proof and docs, not new behavior: on
`TS6-005 Chrome QA` (project 49) the catalog still lists the source and
derived sets correctly and the derived set's detail renders the full lineage
panel (scale_signal impl v1, schema v1, parameters, input set 45 revision 2
with hash) plus a revision history where revision 1 keeps its original
content hash after the regeneration; on `TS6-007 Chrome QA` (project 51) the
programmed set still shows the "Programa oficial" section, the connector
origin and both program versions (original and reissue) in the revision
history with the same content hash; and the admin Schedules section renders
the fixed and rolling schedules with their tick histories, visible failures
(`missing coverage`, Julia validation error), linked runs 29/30 and all
schedules still active. No console errors on any page.
