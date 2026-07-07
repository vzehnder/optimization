# BESS-TS4-000: Review TS-4 PRD And Result Series Semantics

Status: Done
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-08
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

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

- [x] The storage model decision (reuse `time_series_sets` with `data_kind = simulated` versus a dedicated result-series layer) is made and recorded with its rationale.
- [x] The initial indexed scope (which `dispatch.csv`, `asset_dispatch.csv` and `summary.json` columns feed existing UI tables and charts) is agreed.
- [x] The exact lineage fields (run, execution snapshot, case, topology hash, parameter hash, input variant, date range, input series hashes) are agreed.
- [x] The write timing (after run success and after artifact registration, with artifacts as the rebuild source when indexing fails) is accepted.
- [x] The idempotency requirement for result indexing is accepted.
- [x] The read policy (prefer BBDD when indexed data exists, fall back to artifacts otherwise) is accepted.
- [x] The comparison scope (two runs of the same case, KPI diffs plus period-level diffs for selected series) is accepted.
- [x] The out-of-scope list (no artifact removal, no full BI or multi-run analytics, no transformations or resampling, no reuse of outputs as inputs yet) is confirmed.
- [x] Any PRD correction is committed before downstream TS-4 implementation issues begin.

## Resolution

Accepted the TS-4 result semantics in
`docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md`.

The review confirms:

1. TS-4 result indexing should use a dedicated run-result layer rooted at the
   run, not reuse the editable TS-2 `time_series_sets` catalog.
2. The tracer bullet is intentionally narrow: only the run results dispatch
   table reads indexed core `dispatch.csv` rows at first; asset dispatch,
   summary KPIs, broader signal families, rebuild and comparison remain
   downstream issues.
3. Indexing happens only after a run succeeds and its artifacts are already
   registered; artifacts remain the durable audit record and rebuild source.
4. The accepted read policy is BBDD-first per surface with artifact fallback,
   not an all-or-nothing migration.
5. Full TS-4 lineage will come from the frozen run snapshot
   (`scenario_version` plus its topology/parameter/variant/range/series
   provenance), never from mutable live case state; TS4-005 hardens that full
   contract.
6. Re-indexing must converge without duplicates; TS4-001 establishes the
   replace-on-write pattern and TS4-006 hardens failure recovery.
7. Comparison scope is limited to two runs of the same case, with KPI diffs
   and period-level diffs for selected series.
8. The out-of-scope list is confirmed as written.

The PRD was corrected accordingly: the accepted storage model is now the
dedicated run-result layer, and the first indexed slice is core dispatch only
for the run results table.

## Verification

- Added `docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md`
  capturing the accepted storage model, scope, lineage, read policy and
  downstream boundaries.
- Updated `docs/series_tiempo/iter4/prd.md` so its implementation decisions
  match the accepted semantics before downstream implementation proceeds.
- Re-checked `app/results.py`, `app/main.py`, `app/runner.py` and
  `app/persistence.py` to ground the accepted decisions in the real artifact
  registration, result reading and run lineage flow already present in code.

## Blocked by

None - can start immediately.
