# BESS-TS4-004: Index Summary KPIs Linked To Result Series

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-16
Fecha de inicio real: 2026-07-08
Fecha de termino real: 2026-07-08

## User stories covered

12

## What to build

Index the KPIs of `summary.json` (objective value, solver status and the
totals the summary panel consumes) in BBDD, linked to the run and associated
with the run's indexed result series so dashboards can resolve headline
numbers and their backing series together without opening artifacts.

The run summary surface must serve KPIs from BBDD when indexed and fall back
to artifacts for runs without indexed results, rendering identically in both
paths.

## Acceptance criteria

- [x] Summary KPIs from `summary.json` index in BBDD linked to the run.
- [x] Indexed KPIs are associated with the run's result series so dashboards can load both quickly.
- [x] The run summary endpoint serves KPIs from BBDD when indexed, artifacts otherwise.
- [x] The React summary panel renders identically from indexed KPIs.
- [x] Tests prove KPI indexing from representative artifacts.

## Resolution

Implemented test-first (RED/GREEN per behavior):

- Added a dedicated `run_summary_result_indexes` table in `app/persistence.py`
  keyed by `run_id`/`scenario_version_id`, storing the original summary object
  plus typed headline KPIs (`solver_status`, `termination_status`,
  `objective_value_usd`) and `linked_result_surfaces_json` so the summary stays
  associated with the same indexed run-result surfaces.
- Added `index_run_summary_results(...)` in `app/result_indexing.py`. It reads
  `summary.json`, validates that it is a JSON object, and persists it in BBDD
  after checking which run-result surfaces are already indexed for the same run
  (`dispatch_table`, `asset_dispatch_table`).
- `app/results.py` now follows the same TS-4 BBDD-first pattern for the summary
  surface: if a summary index exists for the run, it serves that object from
  BBDD; otherwise it falls back to the registered `summary.json` artifact.
- `app/runner.py` now indexes summary KPIs after dispatch and asset-dispatch
  indexing on successful runs, keeping the same best-effort behavior as the
  earlier TS-4 slices: run success and artifact registration stay untouched even
  if summary indexing fails.
- No React changes were needed. The existing `RunResults` summary panel already
  renders the same JSON shape generically; keeping the summary HTTP contract
  unchanged preserved the UI path.

## Verification

- New backend tests:
  `tests/test_ts4_result_indexing.py` now covers indexing summary JSON into
  BBDD, BBDD-first summary reads in `read_run_results`, and API-level BBDD-first
  summary reads when `summary.json` is absent.
- Extended `tests/test_manual_runs.py` with a runner regression proving a
  successful run indexes summary KPIs after artifacts are registered and still
  serves the summary from BBDD if `summary.json` is removed afterward.
- Targeted Python verification passed:
  `python -m unittest tests.test_ts4_result_indexing tests.test_manual_runs tests.test_results_review -v`.
- Full Python regression passed:
  `python -m unittest discover -s tests -v` -> 311 tests OK, 2 skipped.
- Frontend regression passed in `frontend/`:
  `npm test -- --run` (61 passing), `npx tsc -b`, `npx eslint .`,
  `npm run api:check`.
- Real Postgres verification passed using the credentials from `.env`:
  run `22` (`Multi-family case`) had no prior summary index, was indexed into
  `run_summary_result_indexes`, and stored
  `linked_result_surfaces = ["dispatch_table", "asset_dispatch_table"]`.
- Real API fallback verification passed on a local Uvicorn instance pointed at
  the same Postgres database: after temporarily renaming run `22`'s
  `summary.json` artifact, `GET /api/runs/22/results` still returned
  `termination_status = "OPTIMAL"` and `objective_value_usd = -272.9` from
  BBDD, then the file was restored.
- Real Chrome verification passed with `chrome:control-chrome` on an
  auth-enabled local instance (`http://127.0.0.1:8011/react/runs/22`): after
  logging in with the `.env` test analyst credentials, the Run Results summary
  panel rendered the expected headline KPIs for run `22` (`solver_status`,
  `termination_status`, `objective_value_usd`, etc.) together with the existing
  charts/tables.
- `chrome-devtools` MCP was also attempted for the same verification step, but
  its dedicated automation profile was already locked by another active
  `chrome-devtools-mcp` browser process on this machine, so it could not attach
  without disrupting that separate session.

## Blocked by

BESS-TS4-001
