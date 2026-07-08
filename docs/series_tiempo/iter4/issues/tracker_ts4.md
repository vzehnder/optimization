# BESS TS-4 Issue Tracker

This document is the local tracker for TS-4: run results indexed in BBDD as
result series, artifact fallback and basic run comparison, derived from
`docs/series_tiempo/iter4/prd.md`.

External issue tracker integration has not been configured, so each issue is
stored as a Markdown file in this folder. All issues carry the
`ready-for-agent` triage label.

## Date Policy

All issues generated from this point forward include:

- `Fecha de inicio planificada`
- `Fecha de termino planificada`

Actual start/end dates can be added or corrected by the implementer when work
really begins and ends.

## Status Vocabulary

- `Todo`: not started.
- `In Progress`: actively being implemented.
- `Blocked`: waiting on a dependency or decision.
- `In Review`: implementation is ready for review.
- `Done`: merged or accepted.

## Issue Register

| ID | Title | Type | Triage | Status | Fecha de inicio planificada | Fecha de termino planificada | Blocked by | Issue file |
| --- | --- | --- | --- | --- | --- | --- | --- | --- |
| BESS-TS4-000 | Review TS-4 PRD And Result Series Semantics | HITL | ready-for-agent | Done | 2026-07-08 | 2026-07-08 | None | [BESS-TS4-000-review-ts4-prd-and-result-series-semantics.md](BESS-TS4-000-review-ts4-prd-and-result-series-semantics.md) |
| BESS-TS4-001 | Index Core Dispatch Result Series From A Successful Run | AFK | ready-for-agent | Done | 2026-07-09 | 2026-07-10 | BESS-TS4-000 | [BESS-TS4-001-index-core-dispatch-result-series-from-a-successful-run.md](BESS-TS4-001-index-core-dispatch-result-series-from-a-successful-run.md) |
| BESS-TS4-002 | Extend Result Indexing To All Dispatch Signal Families | AFK | ready-for-agent | Done | 2026-07-13 | 2026-07-14 | BESS-TS4-001 | [BESS-TS4-002-extend-result-indexing-to-all-dispatch-signal-families.md](BESS-TS4-002-extend-result-indexing-to-all-dispatch-signal-families.md) |
| BESS-TS4-003 | Index Asset-Level Dispatch Rows | AFK | ready-for-agent | Done | 2026-07-15 | 2026-07-15 | BESS-TS4-001 | [BESS-TS4-003-index-asset-level-dispatch-rows.md](BESS-TS4-003-index-asset-level-dispatch-rows.md) |
| BESS-TS4-004 | Index Summary KPIs Linked To Result Series | AFK | ready-for-agent | Done | 2026-07-16 | 2026-07-16 | BESS-TS4-001 | [BESS-TS4-004-index-summary-kpis-linked-to-result-series.md](BESS-TS4-004-index-summary-kpis-linked-to-result-series.md) |
| BESS-TS4-005 | Record Full Result Lineage With Drift-Proof Constraints | AFK | ready-for-agent | Done | 2026-07-17 | 2026-07-20 | BESS-TS4-001 | [BESS-TS4-005-record-full-result-lineage-with-drift-proof-constraints.md](BESS-TS4-005-record-full-result-lineage-with-drift-proof-constraints.md) |
| BESS-TS4-006 | Make Result Indexing Idempotent And Failure-Safe | AFK | ready-for-agent | Todo | 2026-07-21 | 2026-07-22 | BESS-TS4-001 | [BESS-TS4-006-make-result-indexing-idempotent-and-failure-safe.md](BESS-TS4-006-make-result-indexing-idempotent-and-failure-safe.md) |
| BESS-TS4-007 | Serve Run Tables And Charts From BBDD With Artifact Fallback | AFK | ready-for-agent | Todo | 2026-07-23 | 2026-07-24 | BESS-TS4-002, BESS-TS4-003, BESS-TS4-004 | [BESS-TS4-007-serve-run-tables-and-charts-from-bbdd-with-artifact-fallback.md](BESS-TS4-007-serve-run-tables-and-charts-from-bbdd-with-artifact-fallback.md) |
| BESS-TS4-008 | Rebuild BBDD Results From Artifacts For Historical Runs | AFK | ready-for-agent | Todo | 2026-07-27 | 2026-07-27 | BESS-TS4-005, BESS-TS4-006 | [BESS-TS4-008-rebuild-bbdd-results-from-artifacts-for-historical-runs.md](BESS-TS4-008-rebuild-bbdd-results-from-artifacts-for-historical-runs.md) |
| BESS-TS4-009 | Compare Two Runs Of The Same Case | AFK | ready-for-agent | Todo | 2026-07-28 | 2026-07-29 | BESS-TS4-002, BESS-TS4-004 | [BESS-TS4-009-compare-two-runs-of-the-same-case.md](BESS-TS4-009-compare-two-runs-of-the-same-case.md) |
| BESS-TS4-010 | Finalize TS-4 Acceptance Suite And Docs | AFK | ready-for-agent | Todo | 2026-07-30 | 2026-07-30 | BESS-TS4-001 through BESS-TS4-009 | [BESS-TS4-010-finalize-ts4-acceptance-suite-and-docs.md](BESS-TS4-010-finalize-ts4-acceptance-suite-and-docs.md) |

## Recommended Execution Order

1. BESS-TS4-000 closes the PRD review and the result-series semantics decision record (storage model, indexed scope, lineage fields, comparison scope).
2. BESS-TS4-001 is the tracer bullet: a successful run indexes its core dispatch series and the run results table reads from BBDD with artifact fallback.
3. BESS-TS4-002 extends indexing to every dispatch signal family (demand, renewable, hydro, economics) across case types.
4. BESS-TS4-003 indexes per-asset dispatch rows from `asset_dispatch.csv`.
5. BESS-TS4-004 indexes summary KPIs linked to the run's result series.
6. BESS-TS4-005 completes result lineage (variant, range, topology/parameter hashes, input series hashes) with drift-proof constraints.
7. BESS-TS4-006 makes indexing idempotent and safe on partial failure; indexing failures never damage a successful run.
8. BESS-TS4-007 completes the BBDD-first read path for tables and charts with artifact fallback and publication/dashboard regression.
9. BESS-TS4-008 adds the rebuild path so historical successful runs can populate BBDD results from artifacts.
10. BESS-TS4-009 adds the basic two-run comparison (KPI diffs plus period-level diffs) for runs of the same case.
11. BESS-TS4-010 closes the iteration with acceptance coverage and docs.

## Progress Log

| Date | Issue | Status change | Notes |
| --- | --- | --- | --- |
| 2026-07-07 | All | Created | Initial local issue set generated from the TS-4 PRD (`docs/series_tiempo/iter4/prd.md`) and the series hierarchy roadmap. |
| 2026-07-07 | BESS-TS4-000 | Done | Accepted the dedicated run-result storage model in `docs/series_tiempo/iter4/decision_record_ts4_result_semantics.md` and corrected the TS-4 PRD before implementation. |
| 2026-07-07 | BESS-TS4-001 | Done | Added post-run core `dispatch.csv` indexing, BBDD-first results-table reads with artifact fallback, focused backend/frontend coverage, and live verification with run `21` indexed and run `8` falling back to artifacts. |
| 2026-07-07 | BESS-TS4-002 | Done | Extended the indexing gate to also accept hydraulic-diagram-only `dispatch.csv` (no grid/battery/price columns), added a canonical `signal_keys` catalog/mapping for demand, renewable, hydro and economics families stored in a new `signal_keys_json` column, and verified against real Postgres by indexing production run `19` (`hybrid_system`). |
| 2026-07-07 | BESS-TS4-003 | Done | Added asset-level dispatch indexing (`run_asset_dispatch_result_indexes`/`run_asset_dispatch_result_rows`, `index_run_asset_dispatch_results`) with the same run/snapshot linkage and BBDD-first/artifact-fallback pattern as core dispatch; verified against real Postgres and a fresh real Julia run (Run 22, multi-asset grid+load+renewable+battery case) that BBDD rows are populated correctly and the Asset Dispatch table renders identically with the CSV artifact temporarily removed. |
| 2026-07-08 | BESS-TS4-004 | Done | Added `run_summary_result_indexes` plus `index_run_summary_results`, switched the summary surface to BBDD-first/artifact-fallback, kept the React summary contract unchanged, and verified against real Postgres with run `22` indexed plus a forced `summary.json` removal fallback on a local Uvicorn instance. |
| 2026-07-08 | BESS-TS4-005 | Done | Added frozen `lineage_json` persistence for dispatch/asset-dispatch/summary indexes, derived only from the immutable `scenario_version` snapshot plus case row metadata, covered legacy no-variant lineage and drift-after-live-edits tests, and verified against real Postgres with a smoke indexed run. |

## Final TS-4 Verification

Run before considering TS-4 closed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

```powershell
cd frontend
npm test -- --run
npx tsc -b
npx eslint .
npm run api:check
npm run build
```

Julia regression is only required if a TS-4 slice changes artifact formats,
the generated `system_case_json` contract or optimizer behavior; TS-4 as
scoped only reads artifacts after the run:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Regression Guard

Every slice that changes backend persistence must keep the existing Python
suite green: scenario versions, structured drafts, hydraulic diagrams, manual
runs, TS-1 hierarchy provenance, TS-2 catalog and TS-3 variant tests.

Slices changing React should run the relevant frontend unit tests, `tsc -b`
and `eslint .`.

Artifacts remain the durable audit record. TS-4 must not change how artifacts
are produced or registered, and must not remove the artifact read path:
historical runs without indexed results keep rendering from artifacts, and
publications/dashboards built on run results must keep working.

Result indexing must never affect run execution outcomes: a run that succeeded
stays succeeded even if indexing fails, with artifacts as the rebuild source.
