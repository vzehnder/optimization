# BESS-TS4-000: Review TS-4 PRD And Result Series Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-08

## User stories covered

1 through 21

## What to build

Review and accept the TS-4 PRD before implementation starts. The review should
confirm the semantic model for result series: after a run succeeds and its
artifacts are registered, the main outputs of `dispatch.csv`,
`asset_dispatch.csv` and `summary.json` are additionally indexed in BBDD as
queryable result series tied to the run and its full lineage, without removing
artifacts as the durable audit record.

The central open decision is the storage model: reuse the generic TS-2 catalog
(`time_series_sets` already accepts `data_kind = simulated`) or introduce a
dedicated result-series layer. Reuse reduces duplication and keeps the door
open to using outputs as future inputs; a dedicated layer can be clearer for
lineage and permissions. The review must also fix the initial indexed column
scope, the exact lineage fields, the write timing, the idempotency
requirement, the BBDD-first read policy with artifact fallback, and the
comparison scope.

The outcome should be a short accepted-decision record in the iteration docs
at `docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md`,
including any corrections to the PRD if the result model, lineage fields,
indexing timing or comparison scope needs adjustment.

## Acceptance criteria

- [ ] The storage model decision (reuse `time_series_sets` with `data_kind = simulated` versus a dedicated result-series layer) is made and recorded with its rationale.
- [ ] The initial indexed scope (which `dispatch.csv`, `asset_dispatch.csv` and `summary.json` columns feed existing UI tables and charts) is agreed.
- [ ] The exact lineage fields (run, execution snapshot, case, topology hash, parameter hash, input variant, date range, input series hashes) are agreed.
- [ ] The write timing (after run success and after artifact registration, with artifacts as the rebuild source when indexing fails) is accepted.
- [ ] The idempotency requirement for result indexing is accepted.
- [ ] The read policy (prefer BBDD when indexed data exists, fall back to artifacts otherwise) is accepted.
- [ ] The comparison scope (two runs of the same case, KPI diffs plus period-level diffs for selected series) is accepted.
- [ ] The out-of-scope list (no artifact removal, no full BI or multi-run analytics, no transformations or resampling, no reuse of outputs as inputs yet) is confirmed.
- [ ] Any PRD correction is committed before downstream TS-4 implementation issues begin.

## Blocked by

None - can start immediately.
