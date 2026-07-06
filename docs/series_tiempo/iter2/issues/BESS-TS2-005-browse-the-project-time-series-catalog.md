# BESS-TS2-005: Browse The Project Time-Series Catalog

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter2/prd.md`
Fecha de inicio planificada: 2026-07-17
Fecha de termino planificada: 2026-07-20
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

16, 17, 18

## What to build

Make the series library visible as business objects. A project catalog lists
its time-series sets with name, version label, data kind, status, timezone,
current revision and content hash, so the analyst can recognize packages like
`hidrologia_seca_v2` or `precios_enero_2026_v1`. A set detail view shows the
signals it contains (canonical keys, units, entity metadata when known), a
horizon summary (period count, start, end) and the provenance of the current
revision, so it is clear whether a set holds prices, demand, renewables or
inflows and where the data came from.

Catalog and detail reads come from BBDD, never from reopening source files.
This slice is read-oriented: manual editing and file replacement arrive in the
following slices.

## Acceptance criteria

- [x] A project catalog lists its time-series sets with name, version label, data kind, status and timezone.
- [x] The catalog shows current revision number and content hash per set.
- [x] A set detail view shows signals with canonical keys, units and entity metadata when known.
- [x] The detail view shows a horizon summary with period count, start and end.
- [x] Source provenance of the current revision (file name, sheet when applicable) is visible.
- [x] Catalog and detail reads come from BBDD, not from reopening source files.
- [x] Backend tests cover list and detail behavior at the API boundary.

## Blocked by

BESS-TS2-001

## Implementation notes

- `app/persistence.py`: added `AnalystStore.list_time_series_sets(project_id)`,
  a project-scoped query that joins each `time_series_sets` row to its latest
  `time_series_set_revisions` row (via a correlated `MAX(revision_number)`
  subquery) plus `COUNT(*)` subqueries for signal and period counts, ordered by
  `name`/`version_number`. `get_time_series_set` gained a `horizon` summary
  (`period_count`, `start` from the first period's `timestamp_start`, `end`
  from the last period's `timestamp_end`) alongside the existing full
  `periods`/`signals`/`values` arrays.
- `app/main.py`: added `GET /api/projects/{project_id}/time-series-sets`
  returning `{"time_series_sets": [...]}`, 404 for an unknown project, reusing
  the existing detail endpoint's error handling pattern.
- `frontend/src/api/client.ts`: added `ProjectTimeSeriesSetSummary` and
  `ProjectTimeSeriesSetHorizon` types plus `listProjectTimeSeriesSets` and
  `getProjectTimeSeriesSet` client functions.
- `frontend/src/Workspace.tsx`: added `TimeSeriesCatalogView` (renders the
  catalog as a linked list with data_kind/status/timezone/revision/hash/signal
  and period counts) and `TimeSeriesSetDetailView` (revision + hash, horizon
  summary, signals with canonical key/unit/entity label defaulting to
  "Global", and source provenance including the XLSX sheet when present).
  `ProjectDetailView` gained a link to the catalog page.
- `frontend/src/App.tsx`: added routes
  `projects/:projectId/time-series-sets` and
  `projects/:projectId/time-series-sets/:timeSeriesSetId`.

## Verification

- `.\.venv\Scripts\python.exe -m unittest tests.test_ts2_time_series_catalog -v`
  (20 ok): 4 new tests cover catalog summary fields ordered by name,
  project isolation (a second project's catalog only lists its own sets),
  404 for an unknown project, and the detail endpoint's `horizon` summary.
- `.\.venv\Scripts\python.exe -m unittest discover tests` (207 ok, 1 skipped).
- `npm test` (49 ok, +1 new test exercising catalog browse -> set detail
  through the full app router and fetch mocks), `npx tsc -b`, `npx eslint .`,
  `npm run api:generate`, `npm run api:check`, `npm run build` all green.
- Chrome (`chrome-devtools` MCP, PostgreSQL-backed app on
  `http://127.0.0.1:8000`, existing admin session): navigated to the already
  seeded projects "TS2 Chrome QA 002" (`ts2_qa_dual_price` v1, 2 signals, 3
  periods) and "TS2 Chrome QA 004" (`ts2_qa_prices` v1, XLSX). Each project's
  catalog page listed only its own set with the correct
  data_kind/status/timezone/revision/hash/signal_count/period_count. Each
  detail page showed the correct signal canonical keys/units/`Global` entity,
  horizon (period count plus start/end instants) and source provenance,
  including `selected_sheet = 'Prices'` for the XLSX set. No console errors.
