# BESS-TS6-003: Interpolate Small Gaps Explicitly And Auditably

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-22
Fecha de termino planificada: 2026-07-23
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

2, 5, 6

## What to build

Add an explicit gap-filling transformation to the allowlist: an analyst takes
a set with small gaps (missing periods inside its horizon) and produces a
derived set where those gaps are filled with a declared method (linear
interpolation first), under a declared maximum gap size.

Missing-data handling must be auditable, never silent: the transformation
parameters declare the method and the maximum gap it may fill, and the
derived set records which periods were filled so a reviewer can distinguish
observed values from interpolated ones. Gaps larger than the declared
maximum cause the transformation to fail with a clear message naming the
signal and the offending range, instead of quietly fabricating data.

As with resampling, this stays a pre-run step: TS-2 import validation and
TS-3 coverage validation keep rejecting incomplete data at their own gates,
and the analyst closes real gaps by producing an explicit derived version and
binding it, so every filled value is traceable to a versioned decision.

## Acceptance criteria

- [x] An analyst can fill small gaps in a catalog set from the UI and obtain a derived set with the method and maximum gap recorded as validated parameters.
- [x] The derived set records which periods were filled, distinguishable from observed values when browsing the set.
- [x] Gaps larger than the declared maximum fail the transformation with a clear message naming the signal and range; no data is written.
- [x] Existing TS-2 import validation and TS-3 range-coverage validation behavior is unchanged.
- [x] The derived set records full lineage and is bindable in a case input variant.
- [x] The interpolation implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001

## Resolution

Added `interpolate_gaps` as the third entry in the allowlist registry
(`app/transformations.py`, impl v1, param schema v1), again reusing
`AnalystStore.apply_time_series_transformation` from BESS-TS6-001 unchanged
except one small additive extension: `TransformationOutput` gained an
optional `execution_metadata: dict[str, Any] = field(default_factory=dict)`
field, merged into the stored `metadata_json.transformation.execution` key
only when non-empty — `scale_signal` and `resample` never set it, so their
stored metadata is byte-for-byte unchanged.

Parameters are `method` (only `"linear"` is allowlisted this iteration) and
`max_gap_hours` (a positive finite float). Gaps are missing *periods*
(timestamps skipped entirely at CSV ingestion, which TS-2 import already
allows), not missing individual signal values, since every mapped signal is
required to have a numeric value on every ingested row. Validation requires
a uniform source period resolution (reusing the same check resample uses),
walks consecutive periods for timestamp discontinuities, rejects any gap
exceeding `max_gap_hours` with a message naming every signal in the set and
the offending `[timestamp_end, timestamp_start)` range, and separately
rejects a gap that is not an integer multiple of the source resolution.

Execution renumbers periods contiguously across observed and synthesized
periods (matching the resample precedent of a fresh 0..N-1 `period_index`),
linearly interpolates every signal's value across each filled gap using its
fractional position between the two boundary values, and records the filled
(renumbered) period indexes in `execution_metadata["filled_period_indexes"]`.
This is fully derivable from the input content plus validated parameters, so
it does not need to enter the recipe-hash convergence check (which still
hashes only `parameters` + `inputs`, unchanged from BESS-TS6-001/002).

React (`frontend/src/Workspace.tsx`) extended the "Transformaciones" panel
with an `interpolate_gaps` option (`linear`-only method selector, a
max-gap-hours input). The "Valores" editor table now reads
`revision_metadata.transformation.execution.filled_period_indexes` and marks
any matching period row with a highlighted background and an "interpolado"
badge next to its timestamp, satisfying "distinguishable from observed
values when browsing the set" without adding a new API field or component.

## Verification

- Backend full suite:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests` -> 451 tests
  passed, 2 skipped, no regressions (438 baseline + 13 new).
- Focused new proof: `tests/test_ts6_transformations.py` (6 new pure-registry
  tests: single-period gap filled with linear interpolation and correctly
  renumbered periods, filled indexes + lineage recorded, a gap larger than
  `max_gap_hours` rejected naming both signals and the timestamp range, an
  unsupported method rejected, a gap misaligned to the source resolution
  rejected, a fully contiguous source producing an empty
  `filled_period_indexes`), `tests/test_ts6_apply_transformation.py` (5 new
  persistence-layer tests: derived set with the gap filled, source set
  unchanged, full lineage plus `execution.filled_period_indexes` in
  `revision_metadata`, variant bindability, a too-large gap rejected before
  any write), `tests/test_ts6_transformation_api.py` (2 new HTTP-layer
  tests: 201 with the filled derived set and its `filled_period_indexes`,
  400 with an "exceeds max_gap_hours" message).
- Frontend: `npx tsc -b`, `npx eslint .`, `npm test -- --run` (66 tests
  passed, no regressions), `npm run api:check` (no drift — the
  transformation endpoint's `parameters` field was already a generic
  `dict`/`Record<string, unknown>`), `npm run build` all green.
- Real Chrome + real PostgreSQL verification on local `uvicorn`
  (`app.main:app` against the `energy_dispatch` DB from `.env`, credentials
  from `MAIL_USUARIO_TEST`/`PASSWORD_MAIL_USUARIO_TEST`): logged in as admin
  (session persisted from a prior browser profile), seeded project
  `TS6-003 Chrome QA` (id 47) and scenario `TS6-003 Chrome QA scenario`
  (id 55) with a 5-period hourly `real` catalog set
  `Demand and price with gap` (id 39) whose CSV import skipped hour 3,
  producing a 1-hour gap between periods `02:00-03:00` and `04:00-05:00`. In
  the browser, selected `interpolate_gaps` in the Transformaciones panel,
  left method `linear`, set `max_gap_hours = 2.0`, and clicked "Aplicar
  interpolate_gaps". The app navigated to the new derived set (id 40,
  `data_kind = derived`,
  `Demand and price with gap__interpolate_gaps (interpolate_gaps v1)`, 6
  periods) whose `03:00` row was highlighted with an "interpolado" badge and
  correctly interpolated values (`load_demand_mw` 102/104 -> 103,
  `import_price_usd_per_mwh` 52/54 -> 53). The lineage panel showed
  `interpolate_gaps` impl v1 / schema v1, parameters
  `max_gap_hours=2, method=linear`, and a working link back to input set 39
  with its recorded revision/hash; set 39 itself stayed at 5 periods with an
  unchanged `content_hash` and no badge. Re-running the same transformation
  on set 39 with `max_gap_hours = 0.5` rendered the alert `gap from
  2026-07-01T03:00:00-04:00 to 2026-07-01T04:00:00-04:00 (1.0 hours) exceeds
  max_gap_hours=0.5 for signal(s) ['import_price_usd_per_mwh',
  'load_demand_mw']` and wrote nothing, proving the fail-closed path end to
  end in the browser.
