# BESS-TS4-007: Serve Run Tables And Charts From BBDD With Artifact Fallback

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-23
Fecha de termino planificada: 2026-07-24

## User stories covered

13, 21

## What to build

Complete the BBDD-first read path across the run detail: every results
surface (dispatch tables, asset tables, summary and charts) serves from BBDD
whenever indexed data exists and falls back to artifacts otherwise. Historical
runs that were never indexed must keep rendering exactly as today, so no data
is lost and no migration is forced.

Partial indexing must degrade gracefully per surface: if a run has indexed
dispatch series but no indexed KPIs, the tables serve from BBDD while the
summary falls back to artifacts, without failing the whole view. Publications
and dashboards built on run results (iteration 6 client views) must keep
working unchanged, as the first step toward eventually feeding them from BBDD.

## Acceptance criteria

- [x] Run results tables and charts serve from BBDD when indexed data exists.
- [x] Historical runs without indexed results keep rendering from artifacts with no visible regression.
- [x] Partially indexed runs degrade gracefully per surface instead of failing the whole run view.
- [x] Existing publication and dashboard views keep working (regression suite green).
- [x] Tests cover BBDD-served, artifact-fallback and mixed (partially indexed) runs.

## Resolution

`read_run_results` (`app/results.py`) already resolved dispatch, asset
dispatch and summary independently per-surface with BBDD-first/artifact
fallback (from TS4-001/003/004), and every consumer (`/api/runs/{id}/results`,
dashboard-template preview, publication preview/client view) already passed
`store=` through, so charts and publications inherited the same per-surface
resolution automatically. This slice added the missing test coverage proving
the partial-indexing/mixed-source contract end to end and verified it live:

- `tests/test_ts4_result_indexing.py::MixedSurfaceReadPathTests` proves a run
  with dispatch+summary indexed but asset dispatch only on disk serves all
  three surfaces correctly, both via `read_run_results` directly and via
  `/api/runs/{id}/results`.
- `tests/test_iter6_dashboard_templates.py::test_dashboard_template_rendering_mixes_bbdd_dispatch_with_artifact_fallback_surfaces`
  proves the dashboard-template read path renders a mixed BBDD/artifact run
  correctly, including charts built from the resolved tables.
- Live verification against real Postgres (`energy_dispatch`) and a real
  Julia run: Run 26 (fully indexed) rendered identically after temporarily
  removing `dispatch.csv` and `summary.json` from disk (BBDD-first survives
  missing artifacts), and Run 8 (a pre-TS4 run, never indexed) still rendered
  fully from artifacts with no regression. No console errors in either case.

## Blocked by

BESS-TS4-002, BESS-TS4-003, BESS-TS4-004
