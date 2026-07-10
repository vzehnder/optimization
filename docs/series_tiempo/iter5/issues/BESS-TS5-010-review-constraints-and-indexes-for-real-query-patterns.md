# BESS-TS5-010: Review Constraints And Indexes For Real Query Patterns

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-31
Fecha de termino planificada: 2026-07-31
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

14, 15

## What to build

Ground performance hardening in the query patterns TS-2 through TS-4 actually
created, not speculation: browsing the project catalog, reading one set's
values by date range, resolving a variant's bound signals, loading a run's
indexed results, comparing two runs, and scanning candidates for rebuild or
cleanup. Inventory those hot paths, review which constraints and indexes
support them, and add the missing ones.

Schema changes ship as idempotent routines that work on both local SQLite and
PostgreSQL, so environments can be repaired safely by re-running them. Guard
tests assert query shapes — the intended access paths and the absence of full
scans on hot paths — rather than exact timings, per the PRD's testing
decision. All existing suites stay green after constraint changes.

## Acceptance criteria

- [x] The main TS-2 through TS-4 query patterns (catalog browse, range reads, variant resolution, run result reads, comparison, rebuild/cleanup scans) are inventoried with their supporting constraints and indexes.
- [x] Missing indexes and constraints are added via idempotent schema routines that work on both SQLite and PostgreSQL.
- [x] Guard tests assert query shapes rather than exact timings.
- [x] The full existing Python suite stays green after constraint and index changes.

## Blocked by

BESS-TS5-001 through BESS-TS5-005

## Resolution

Reviewed the real TS-2 through TS-4 hot paths against the current store SQL and
split them into two groups:

- Already-covered by existing primary-key / unique constraints: catalog browse
  (`time_series_sets`, latest revision lookup, signal/period counts), variant
  bindings and validation dependencies, indexed run-result reads, and
  run-comparison lineage lookups.
- Missing explicit support for scale: value reads filtered by
  `time_series_values.time_series_set_id`, and project rebuild/cleanup scans
  filtering succeeded runs by project/status across
  `runs -> scenario_versions -> scenarios`.

No new integrity constraint was required. The missing hardening was purely
indexing, because the accepted TS-2 through TS-4 uniqueness / foreign-key
contracts already matched the hot queries.

Added idempotent schema routine `AnalystStore._ensure_query_shape_indexes`,
called on every store startup for both SQLite and PostgreSQL. It creates four
explicit indexes:

- `idx_time_series_values_set_period_signal` on
  `time_series_values (time_series_set_id, time_series_period_id, time_series_signal_id)`
- `idx_runs_status_scenario_version` on
  `runs (status, scenario_version_id, id)`
- `idx_scenario_versions_scenario` on
  `scenario_versions (scenario_id, id)`
- `idx_scenarios_project` on `scenarios (project_id, id)`

These close the two previously uncovered access paths while keeping the schema
repair-safe: reopening the same DB reruns the routine and converges cleanly via
`CREATE INDEX IF NOT EXISTS`.

## Verification

- New guard suite: `tests/test_ts5_query_shape_indexes.py` (4 tests).
  It inventories the hot paths with executable `EXPLAIN QUERY PLAN` checks:
  catalog browse, range/value reads, variant resolution, run-result reads,
  run-comparison lineage, and project rebuild/cleanup scans.
- TDD tracer bullets:
  the first red proved `time_series_values` was full-scanned on
  `WHERE time_series_set_id = ?`;
  the second red proved project cleanup/rebuild scans were full-scanning
  `runs`.
- Idempotence proof:
  reopening the same SQLite DB recreates the named indexes safely and leaves
  the expected index set intact.
- Backend full suite:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests -v`
  -> 396 tests passed, 2 skipped.
- Direct PostgreSQL verification with the real dev DB:
  all four named indexes now exist in `pg_indexes`. With `enable_seqscan = off`
  for plan inspection, PostgreSQL uses
  `Bitmap Index Scan on idx_time_series_values_set_period_signal` for the
  filtered set-values query and `Index Only Scan` on
  `idx_scenarios_project`, `idx_scenario_versions_scenario`, and
  `idx_runs_status_scenario_version` for the project-succeeded-runs scan.
  (On this small dev dataset, default-cost planning may still choose a seq scan;
  the point of the issue is that the correct access paths now exist for scale.)
- Real browser smoke on local `uvicorn` + real PostgreSQL using
  `chrome:control-chrome`:
  logged in as admin with the `.env` credentials and loaded these routes with
  zero console warnings/errors:
  `/react/projects/24/time-series-sets`,
  `/react/projects/24/time-series-sets/18`,
  `/react/scenarios/33`,
  `/react/scenarios/33/runs/compare`,
  `/react/runs/26`.
  The expected headings / key content rendered on each page
  (`Catalogo de series de tiempo`, `price (v1)`, `Multi-family case`,
  `Comparar corridas`, `Run 26`).
