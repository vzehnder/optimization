# BESS-TS4-001: Index Core Dispatch Result Series From A Successful Run

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-09
Fecha de termino planificada: 2026-07-10
Fecha de inicio real: 2026-07-07
Fecha de termino real: 2026-07-07

## User stories covered

1, 2, 3, 6, 7, 8, 18

## What to build

The tracer bullet for the result-series workflow: an analyst runs a simple
grid-plus-BESS case to success and, after the run's artifacts are registered,
the system automatically indexes the core `dispatch.csv` series in BBDD tied
to the run and its execution snapshot. When the analyst opens the run's
results table, the backend serves the indexed data from BBDD instead of
re-reading the CSV, falling back to artifacts for runs that have no indexed
results.

The slice cuts through every layer with the thinnest possible path: one
storage model (per the BESS-TS4-000 decision), one artifact parsed
(`dispatch.csv`), one core signal scope (grid import/export power, prices and
market value, BESS charge/discharge and stored energy), one read surface (the
run results table) and an unchanged React rendering. Artifact parsing, result
normalization and BBDD writes live in a deep module testable without UI.
Signal-family breadth, asset-level rows, summary KPIs, full lineage,
idempotency hardening, charts, rebuild and comparison belong to later slices.

## Acceptance criteria

- [x] A successful run automatically indexes its core dispatch series (grid import/export, price and market value, BESS charge/discharge and energy) in BBDD after artifact registration.
- [x] Indexed result records are linked to the run and its execution snapshot.
- [x] Artifacts continue to be produced and registered unchanged; indexing adds a second trail, it does not replace the first.
- [x] The run results table endpoint serves indexed data from BBDD when present and falls back to artifacts otherwise.
- [x] The React results table renders from BBDD-served data without visible regression.
- [x] Artifact parsing, result normalization and BBDD writes live in deep modules testable without UI.
- [x] Runs that predate result indexing keep serving their results from artifacts.

## Resolution

Implemented test-first (RED/GREEN per behavior):

- New deep module `app/result_indexing.py` indexes supported `dispatch.csv`
  artifacts after artifact registration, normalizes the core dispatch fields
  used by the tracer bullet, preserves the original row shape in `row_json`,
  and resolves both absolute and relative artifact paths safely.
- `app/persistence.py` now creates `run_dispatch_result_indexes` and
  `run_dispatch_result_rows`, plus write/read helpers that replace one run's
  indexed dispatch rows atomically at the store level.
- `app/runner.py` now calls the indexer after a run succeeds and its artifacts
  are registered. Indexing is best-effort: artifact production and run status
  stay untouched if indexing fails.
- `app/results.py` and `app/main.py` now prefer indexed dispatch rows from
  BBDD when present and fall back to `dispatch.csv` artifacts otherwise,
  without changing the existing response contract consumed by React.
- `app/database.py` registers the new result-row table in `ID_TABLES` so the
  Postgres path continues to support inserts that need returned ids.

The accepted tracer-bullet scope is the grid-plus-BESS core dispatch signals:
grid import/export, price, market value, BESS charge/discharge and stored
energy. Broader signal families, asset dispatch rows, summary KPIs, full
lineage hardening, rebuild and comparison remain downstream TS-4 issues.

## Verification

- New backend tests:
  `tests/test_ts4_result_indexing.py` covers indexing supported
  `dispatch.csv`, preferring indexed rows in `read_run_results`, API-level
  BBDD-first reads, and relative artifact-path resolution.
- Extended `tests/test_manual_runs.py` with a run-executor regression proving
  a successful run indexes dispatch results after artifact registration.
- Targeted Python verification:
  `python -m unittest tests.test_ts4_result_indexing -v`,
  `python -m unittest tests.test_manual_runs -v`,
  `python -m unittest tests.test_results_review -v`,
  `python -m unittest tests.test_iter3_acceptance -v` all passed.
- Frontend verification:
  `npm test -- --run`, `npx tsc -b`, `npx eslint .`, `npm run api:check` and
  `npm run build` all passed in `frontend/`.
- Real Postgres / live-server verification:
  run `21` was executed successfully, indexed into BBDD, and then its
  registered `dispatch.csv` file was removed from disk to force the BBDD-first
  path. Authenticated `GET /api/runs/21/results` against the live app still
  returned the 6 dispatch rows from BBDD, proving the indexed read path.
- Legacy fallback verification:
  real run `8` has no TS-4 index and still returned its 6 dispatch rows from
  `/api/runs/8/results`, proving artifact fallback for pre-indexing runs.
- Full `python -m unittest discover -s tests -v` reached 299 tests with 2
  unrelated pre-existing Julia validation failures in
  `tests/test_web_validation.py` (`SystemError: longpath: Acceso denegado`).

## Blocked by

BESS-TS4-000
