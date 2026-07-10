# BESS-TS6-010: Finalize TS-6 Acceptance Suite And Docs

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-08-13
Fecha de termino planificada: 2026-08-14

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

- [ ] An acceptance test suite covers every allowlisted transformation as a pure/deep module, lineage, staleness/regeneration, connector ingestion with mocked data, and scheduled plus rolling-horizon automation.
- [ ] Regression tests prove manual variant-driven runs are unchanged, and the full backend and frontend suites are green.
- [ ] No speculative performance tests are added; any added one references a measured bottleneck.
- [ ] `docs/series_tiempo/iter6/pruebas_manuales_ts6.md` exists in the shape of the TS-1 through TS-5 checklists.
- [ ] A final TS-6 architecture note and a README section document the transformation layer, connector boundary and automation semantics as implemented.
- [ ] The tracker register and progress log are in their final state.

## Blocked by

BESS-TS6-001 through BESS-TS6-009
