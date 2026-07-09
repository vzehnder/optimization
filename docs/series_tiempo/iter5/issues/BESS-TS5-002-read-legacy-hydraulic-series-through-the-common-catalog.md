# BESS-TS5-002: Read Legacy Hydraulic Series Through The Common Catalog

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15
Fecha de inicio real: 2026-07-09
Fecha de termino real: 2026-07-09

## User stories covered

4, 12, 16

## What to build

Stop hydrology from being a special UX island: legacy hydraulic series sets
created by the hydro diagram editor become visible through the common catalog
semantics via a read adapter, without physically migrating rows.

An analyst browsing the project series catalog sees the legacy hydraulic sets
alongside generic sets, labeled with their hydraulic origin, and can inspect
their signals, periods and values with the same vocabulary used for generic
sets. The hydro diagram editor's existing series screens and case bindings
keep working unchanged — the adapter adds a second read surface, it does not
replace the legacy path yet.

Adapter reads live in a deep module testable without the UI, and coexistence
tests prove the adapter and the legacy read path expose the same values for
the same set, so later write-path and migration slices can build on a proven
equivalence.

## Acceptance criteria

- [x] Legacy hydraulic series sets are listed in the project series catalog alongside generic sets, labeled with their hydraulic origin.
- [x] A legacy hydraulic set's signals, periods and values can be browsed through the common catalog semantics without migrating rows.
- [x] The hydraulic diagram editor's existing series screens and case bindings keep working unchanged.
- [x] Adapter reads live in a deep module testable without the UI.
- [x] Coexistence tests prove the adapter and the legacy read path expose the same values for the same set.

## Implementation notes (2026-07-09)

New deep module `app/hydraulic_time_series_adapter.py` (`build_hydraulic_catalog_summary`,
`build_hydraulic_catalog_detail`) is pure and DB-free: it takes a raw joined row plus a
list of `hydraulic_time_series_points`-shaped dicts and reshapes them into the same
summary/detail vocabulary the generic TS-2 catalog uses (`signals`/`periods`/`values`/
`horizon`), computing `timestamp_end = timestamp_start + duration_hours` exactly like
`app/time_series_catalog.py` does, plus an `origin: {kind: "hydraulic_legacy", ...}`
label. `AnalystStore.list_hydraulic_time_series_sets`/`get_hydraulic_time_series_set`
(`app/persistence.py`) do the DB IO only: a `COALESCE`-based join across
`hydraulic_nodes`/`hydraulic_reaches`/`hydraulic_systems` resolves an entity display
name and system name regardless of whether the set belongs to a node or a reach, then
delegate all shaping to the adapter module. Reused the existing
`_load_inflow_series_points` helper (the same one the legacy hydro-diagram read path
uses) as the single source of truth for point data, so the adapter and the legacy path
can never diverge on what a "point" is. New endpoints
`GET /api/projects/{project_id}/time-series-sets/hydraulic` and
`.../hydraulic/{hydraulic_time_series_set_id}` were added *before* the existing
int-typed `.../time-series-sets/{time_series_set_id}` route in `app/main.py`, since a
literal `hydraulic` path segment would otherwise 422 against that int converter. No
migration, no write path touched — this is a second, additional read surface; the
hydro-diagram editor's own screens and `case_hydraulic_time_series_bindings` are
untouched. Frontend: `TimeSeriesCatalogView` now also queries the new hydraulic list
endpoint and renders it as a separate, clearly labeled "Series hidraulicas (origen
legacy)" section on the same catalog page (not merged into the generic list, since the
two id spaces are independent integer sequences that would otherwise collide); a new
`HydraulicTimeSeriesSetDetailView` route
(`/projects/:projectId/time-series-sets/hydraulic/:hydraulicTimeSeriesSetId`) shows
origin/horizon/signals. Tests: `tests/test_hydraulic_time_series_adapter.py` (pure
adapter, 2 cases, no DB) and `tests/test_ts5_hydraulic_series_catalog_adapter.py` (5
cases: origin-labeled listing, detail-vs-legacy-diagram-read coexistence proof via the
shared `time_series_set_id`, hydro-diagram editor's own read path unchanged, per-project
scoping/404, and a `hydraulic_reach`/`minimum_flow_m3s` case exercising the other half
of the entity join). Backend suite: 358 tests (2 skipped), up from 350. Frontend: 62
vitest (up from 61), `tsc -b`/`eslint .`/`api:generate`+`api:check`/`build` all green.
Chrome + real Postgres verification (project `TS5-002 Chrome QA`, id 39, scenario 48):
created a reservoir node with a `natural_inflow_series` through the real
`PUT /api/scenarios/48/hydraulic-diagram` endpoint (an authenticated `fetch()` from the
browser console, not the canvas UI — driving the drag/drop hydraulic diagram editor
itself is out of this issue's scope and already covered elsewhere), confirmed the new
set (`time_series_set_id` 9) appeared in the project catalog page labeled "Origen
hidraulico" alongside the (empty) generic list, opened its detail page and confirmed
correct signal/unit/entity/horizon/periods, and confirmed the legacy
`GET /api/scenarios/48/hydraulic-diagram` read path still returns the identical
`time_series_set_id` and points afterward (zero console errors either page).

## Blocked by

BESS-TS5-000
