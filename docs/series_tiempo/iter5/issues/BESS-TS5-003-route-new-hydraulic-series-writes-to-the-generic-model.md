# BESS-TS5-003: Route New Hydraulic Series Writes To The Generic Model

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-17
Fecha de inicio real: 2026-07-09
Fecha de termino real: 2026-07-09

## User stories covered

4, 13

## What to build

Per the write strategy accepted in BESS-TS5-000, new hydraulic series data
created or uploaded from the hydro diagram flow is stored in the generic
catalog model instead of growing the legacy hydraulic-specific tables. The
parallel system stops growing: from this slice on, a new inflow or minimum
flow series is a generic set with revisions, periods, signals and values.

The end-to-end proof is a hydro case run: an analyst creates a new hydraulic
series through the hydro flow, binds it, validates, promotes and runs, and the
executable payload delivered to the optimizer is identical to what the legacy
storage would have produced for equivalent data. Pre-existing legacy hydraulic
sets remain readable and usable side by side through the BESS-TS5-002 adapter
during the compatibility window.

## Acceptance criteria

- [x] New hydraulic inflow and minimum-flow series created from the hydro flow are persisted in the generic model, not in the legacy hydraulic tables.
- [x] Case binding, validation, promotion and runs consume the new storage and produce the same executable payload as the legacy path for equivalent data.
- [x] Pre-existing legacy hydraulic sets remain readable and usable side by side with newly written generic sets.
- [x] Regression tests prove the hydro diagram flow (bind, validate, promote, run) stays green with the new write path.

## Implementation notes (2026-07-09)

`case_hydraulic_time_series_bindings.hydraulic_time_series_set_id` is now
nullable, and a new nullable `time_series_set_id` (FK to `time_series_sets`)
was added alongside it, with a `CHECK` requiring exactly one of the two to be
set (SQLite and PostgreSQL migration paths added, following the existing
`_ensure_case_time_series_bindings_entity_scope` rebuild pattern). A binding
row now points at either store, never both, and never a dual write.

New deep-module pair in `app/persistence.py`:
`_resolve_hydraulic_inflow_series_binding` (replaces
`_resolve_hydraulic_inflow_series_set`) decides, per save, whether a series
reference is an *existing* set (looked up in whichever store
`series["origin_kind"]` names -- default is the legacy table, so pre-TS5-003
bindings keep resolving unchanged) or *brand-new points*, which are always
written through `_write_generic_hydraulic_time_series_set` into the generic
catalog (`time_series_sets`/`time_series_set_revisions`/`time_series_signals`/
`time_series_periods`/`time_series_values`, reusing the shared TS-2
`_insert_time_series_signals_periods_values` helper). The legacy
`hydraulic_time_series_sets`/`hydraulic_time_series_points` tables receive no
new rows from this point on. A generic set's `name` is the stable
`hydro_{entity_type}_{entity_id}_{signal_key}` key (the numeric hydraulic
entity id, not its renameable technical/display name) so repeated edits keep
chaining into the same version sequence and content-hash-identical resaves
are a no-op, mirroring the legacy version-chain semantics exactly.

Read side: `_load_bound_hydraulic_points` is a single dispatch point (used by
`_reference_inflow_horizon`, `_validate_reach_controls`,
`_validate_node_inflow_series`, replacing 3x duplicated inline SQL) that reads
from `hydraulic_time_series_points` or, via new
`_load_generic_hydraulic_series_points`, from the generic
periods/values/signals tables -- both return the identical
`{timestamp, duration_hours, value_m3s}` point shape, so `generate_hydraulic_v3_preview`
and the diagram response builder need no further branching.
`_entity_inflow_series_detail` now merges legacy and generic rows for the same
entity+signal into one `available` list, each tagged
`origin: {"kind": "hydraulic_legacy" | "generic"}`; `bound` resolution uses
that tag plus whichever binding column is populated. This origin tag is also
now round-tripped on write: `HydraulicNaturalInflowSeriesRequest` gained an
optional `origin` field, `normalize_hydraulic_natural_inflow_series` carries
it through as `origin_kind`, and the frontend
(`editableHydraulicNodes`/`editableHydraulicReaches` in `Workspace.tsx`, plus
both "select existing version" dropdowns) now forwards `origin` when
re-sending an already-bound series -- without this, resaving a diagram whose
inflow was bound to a generic set (e.g. editing an unrelated field) would
400, since the id would otherwise be looked up in the wrong store by default.
Caught this by tracing the real save path in `Workspace.tsx`, not just the
Python-level tests (which had been passing `origin` explicitly).

Tests: `tests/test_ts5_hydraulic_series_generic_write.py` (4 new: new
node/reach series lands generic and not legacy, identical-points resave is a
no-op, selecting an existing generic version by id reuses it). Updated
`tests/test_ts5_hydraulic_series_catalog_adapter.py` (TS5-002's suite) to seed
legacy fixtures by inserting directly into `hydraulic_time_series_sets`
through the store connection, since the public API can no longer produce
legacy rows going forward -- a genuinely legacy-backed set is now only
pre-existing/seeded data, never something a fresh save creates. Added a new
coexistence test there proving a seeded legacy set and a freshly-saved
generic set for the same node both surface correctly (as two `available`
entries with distinct `origin`, while the case stays bound to whichever one
was actually selected). Full backend suite: 363 tests (2 skipped), up from
358. Frontend: 62 vitest, `tsc -b`, `eslint .`, `api:generate`+`api:check`,
`build` all green.

Chrome + real PostgreSQL (project `TS5-003 Chrome QA`, id 40, scenario 49):
added a reservoir, imported a natural-inflow CSV through the real editor
upload control (not a raw `fetch()`), saved, and confirmed via
`GET /api/projects/40/time-series-sets` that a new generic set
(`hydro_hydraulic_node_122_natural_inflow_m3s`) was created while
`GET .../time-series-sets/hydraulic` stayed empty. Edited an unrelated field
(the node label) and resaved: no error, no duplicate set (same id, same
`content_hash`/timestamps), version stayed `v1` -- this is the exact
resave-preserves-origin path the frontend fix above addresses. Ran
`POST .../hydraulic-diagram/validate`: 200 OK with only the expected
(unrelated) `missing_storage_elevation_curve` error, confirming the inflow
series itself resolved and passed its nonnegative/horizon checks through the
new generic-read path with zero console errors.

Julia regression (`julia --project=. -e "import Pkg; Pkg.test()"`) run per
the tracker's guidance for hydraulic write-path slices: 532/532 tests passed.

## Blocked by

BESS-TS5-002
