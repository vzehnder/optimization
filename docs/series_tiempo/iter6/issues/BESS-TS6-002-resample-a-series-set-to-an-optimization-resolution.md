# BESS-TS6-002: Resample A Series Set To An Optimization Resolution

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

1, 5, 6

## What to build

Add a resampling transformation to the allowlist built in BESS-TS6-001: an
analyst takes a set whose resolution does not match the optimization case
(for example hourly data for a daily model, or sub-hourly measurements for an
hourly model) and produces a derived set aligned to the target resolution.

The transformation is declarative: parameters select the target resolution
and the aggregation or distribution method per signal (for example mean for
prices, sum for energy), validated against a versioned parameter schema.
Methods that make no physical sense for a signal are rejected at validation
time rather than producing silently wrong data.

Resampling stays an explicit pre-run step, never an implicit run-time
behavior: the run pipeline keeps failing with a clear message when bound
series do not match the selected range and resolution, exactly as TS-3
established. The analyst resolves that failure by resampling first and
binding the derived set in the variant, so every resolution change is a
visible, versioned decision with lineage.

The derived set records the same lineage contract as the tracer bullet and is
bindable in a case input variant, closing the loop: resample, bind, run.

## Acceptance criteria

- [x] An analyst can resample a catalog set to a target resolution from the UI and obtain a derived set with the chosen aggregation methods recorded.
- [x] Aggregation/distribution methods are validated per signal against a versioned parameter schema, rejecting physically meaningless combinations.
- [x] The run pipeline still fails clearly when bound series do not match the selected range and resolution; no implicit resampling happens at run time.
- [x] The derived set records full lineage (input set, revision/hash, parameters, schema version, implementation version) and is bindable in a case input variant.
- [x] A case run using the resampled derived set completes end-to-end.
- [x] The resampling implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001

## Resolution

Added `resample` as the second entry in the allowlist registry
(`app/transformations.py`, impl v1, param schema v1), reusing the exact
generic execution path `AnalystStore.apply_time_series_transformation` built
in BESS-TS6-001 unchanged: no persistence, API or lineage code needed to
change, only a new `TransformationDefinition`. Parameters are
`target_resolution_hours` (float) and `signal_methods` (a `signal_key ->
"mean" | "sum"` map covering every signal in the input set). Validation
rejects, before anything is written: a non-positive/non-finite target
resolution, a missing or unknown signal_key in `signal_methods`, a method
outside `{"mean", "sum"}`, a mixed-duration or non-contiguous source horizon,
upsampling (`target_resolution_hours` finer than the source), and a target
resolution that does not evenly divide the source periods.

Physically-meaningless combinations are rejected per signal via a new
additive `resampling_methods: tuple[str, ...] = ("mean",)` field on
`TimeSeriesSignalDefinition` (`app/time_series_catalog.py`). Every signal
currently in `TIME_SERIES_SIGNAL_CATALOG` is a rate/intensive quantity
(price, power, flow), so all of them default to `("mean",)` only — requesting
`sum` for any current signal is rejected with a clear
"not physically meaningful" error. `sum` becomes available the moment a
future extensive/accumulated signal (e.g. an energy-in-MWh signal) lists it
explicitly; the registry does not need a special case.

Execution aggregates uniform-duration, contiguous source periods into
coarser target periods (`groups_per_period = target_resolution_hours /
source_resolution_hours`), computing `mean` or `sum` per signal per group.
Output periods carry the new `duration_hours`; lineage lists every resampled
signal (all of them, since resample always touches the full set), matching
the same `time_series_set_revisions.metadata_json` +
`validation_dependencies` lineage contract from BESS-TS6-001 — no schema
changes.

React (`frontend/src/Workspace.tsx`) extended the existing "Transformaciones"
panel with a transformation-type selector (`scale_signal` | `resample`); the
`resample` branch shows a target-resolution-hours input and one
mean/sum method selector per signal in the set. The lineage panel's
parameter renderer was fixed to `JSON.stringify` nested values (e.g.
`signal_methods`) instead of showing `[object Object]`.

## Verification

- Backend full suite:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests` -> 438 tests
  passed, 2 skipped, no regressions (423 baseline + 15 new).
- Focused new proof: `tests/test_ts6_transformations.py` (7 new pure-registry
  tests: mean aggregation across a coarser resolution, lineage listing every
  resampled signal, `sum` rejected as not physically meaningful for a rate
  signal, upsampling rejected, a non-evenly-dividing target resolution
  rejected, a missing per-signal method rejected, an unknown signal_key in
  `signal_methods` rejected), `tests/test_ts6_apply_transformation.py` (5 new
  persistence-layer tests: derived set at the target resolution, source set
  unchanged, full lineage in `revision_metadata`, variant bindability,
  invalid parameters rejected before any write),
  `tests/test_ts6_transformation_api.py` (2 new HTTP-layer tests: 201 with
  the resampled derived set, 400 with a "not physically meaningful" message
  for `sum` on a rate signal), `tests/test_ts6_002_resample_run_acceptance.py`
  (1 new end-to-end test: binding a raw hourly load series against a 2-hour
  model horizon fails with "horizon incompatible" / "no implicit
  resampling"; resampling it to 2 hours, then binding the derived set in the
  same slot, lets the variant run complete with `201` and the run's
  `generation_metadata.series_bindings` pointing at the resampled set).
- Frontend: `npx tsc -b`, `npx eslint .`, `npm test -- --run` (66 tests
  passed, no new component test added since none existed for this panel
  before TS6-002 either), `npm run api:generate` + `npm run api:check`
  (no drift — the transformation endpoint's `parameters` field was already a
  generic `dict`/`Record<string, unknown>`), `npm run build` all green.
- Real Chrome + real PostgreSQL verification on local `uvicorn`
  (`app.main:app` against the `energy_dispatch` DB from `.env`): logged in
  as admin with the `.env` credentials (session persisted from a prior
  browser profile), created project `TS6-002 Chrome QA` (id 46) and scenario
  `Resample workflow` (id 54), seeded a 24-period hourly `real` catalog set
  `Load hourly TS6-002` (id 37, signal `load_demand_mw`, values 100..123)
  through the existing import path. In the browser, selected `resample` in
  the Transformaciones panel, set resolution to `2` hours (method `mean`,
  the only option shown per signal) and clicked "Aplicar resample". The app
  navigated to the new derived set (id 38, `data_kind = derived`,
  `Load hourly TS6-002__resample (resample v1)`, 12 periods of 2 hours each)
  with correctly averaged values (100/101 -> 100.5, 102/103 -> 102.5, ...,
  122/123 -> 122.5). The lineage panel showed `resample` impl v1 / schema
  v1, parameters `signal_methods={"load_demand_mw":"mean"},
  target_resolution_hours=2` (confirming the nested-object rendering fix),
  and a working link back to input set 37 with its recorded revision/hash.
  The catalog list for project 46 showed both sets, with set 37's
  `content_hash` unchanged from before the transformation. The run-pipeline
  fail-then-succeed proof (mismatched-resolution rejection, then success
  after resampling and rebinding) was driven at the API acceptance-test
  level (`tests/test_ts6_002_resample_run_acceptance.py`) rather than
  re-driven through the case/variant/run UI in this pass, consistent with
  how BESS-TS6-001 proved variant bindability at the test level rather than
  through the UI.
