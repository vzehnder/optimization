# BESS-TS2-000: Review TS-2 PRD And Series Catalog Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-06
Fecha de termino planificada: 2026-07-06

## User stories covered

1 through 23

## What to build

Review and accept the TS-2 PRD before implementation starts. The review should
confirm the semantic model of the generic time-series catalog:
`TimeSeriesSource -> TimeSeriesSet -> TimeSeriesSetRevision ->
TimeSeriesPeriod -> TimeSeriesSignal -> TimeSeriesValue`, and the boundary
against TS-3 (no case bindings in this iteration).

The outcome should be a short accepted-decision record in the iteration docs,
including any corrections to the PRD if the catalog model, revision semantics,
signal catalog or timezone convention needs adjustment.

## Acceptance criteria

- [ ] The decision that BBDD is the operative source and files are auditable load sources is accepted or corrected.
- [ ] The decision that sets support both multi-signal packages and single-signal sets is accepted.
- [ ] The `version_label` versus `revision_number` semantics are accepted or corrected.
- [ ] The initial canonical signal catalog (allowed `signal_key` values, expected units, validation rules) is agreed.
- [ ] The timezone convention (timestamps as instants plus IANA set timezone, with `America/Santiago` as the key case) is accepted.
- [ ] The manual edit policy (bounded edits creating new revisions with recalculated hashes) is accepted.
- [ ] The out-of-scope list (no case bindings, no result series, no resampling, no complex unit conversion, no hydraulic table migration) is confirmed.
- [ ] Any PRD correction is committed before downstream TS-2 implementation issues begin.

## Blocked by

None - can start immediately.
