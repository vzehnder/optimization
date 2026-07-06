# BESS-TS3-001: Run A Case From Its Default Variant End-To-End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-08
Fecha de termino planificada: 2026-07-09
Fecha de inicio real: 2026-07-06
Fecha de termino real: 2026-07-06

## User stories covered

1, 4, 10, 20

## What to build

The tracer bullet for the case-variant workflow: an analyst opens a case that
already has a default input variant, binds one required price signal to a
catalog set/signal, selects a run date range, and runs. The backend validates
that the binding covers the range with a compatible period, materializes the
`system_case_json` from topology + parameters + variant + range, creates (or
reuses) an immutable technical snapshot and launches it through the existing
manual-run infrastructure.

The slice cuts through every layer with the thinnest possible path: a default
variant per case, one binding for one signal family (grid price), a date-range
picker, snapshot materialization isolated in a deep module testable without
UI, and a minimal React flow to bind, pick a range and launch. Required-signal
discovery breadth, clone/dropdown UX, full validation matrices, stale marking
and lineage polish belong to later slices.

## Acceptance criteria

- [x] Every `OptimizationCase` exposes a default input variant (created automatically when missing).
- [x] The default variant can bind a required price signal to a catalog `TimeSeriesSet`/`TimeSeriesSignal` without copying values.
- [x] A run can be launched from the case by selecting the default variant and an explicit date range.
- [x] The backend materializes the `system_case_json` from topology, parameters, variant bindings and the selected range.
- [x] The run references an immutable technical snapshot created or reused automatically; no manual `ScenarioVersion` step is required.
- [x] Binding resolution, horizon slicing and snapshot generation live in deep modules testable without UI.
- [x] The existing manual-run infrastructure executes the generated snapshot and the run reaches a terminal state.
- [x] A minimal React flow binds the signal, selects the date range and launches the run from the case.

## Resolution

Implemented test-first (RED/GREEN per behavior):

- Schema: new `case_input_variants` (`is_default` + partial unique index per
  case) and `case_time_series_bindings` (`case_input_variant_id`,
  `signal_key`, `time_series_set_id`) tables; registered both in
  `app.database.ID_TABLES` for Postgres `RETURNING id` support.
- New deep module `app/input_variants.py`:
  `resolve_bound_signal_series` (slices one bound signal's periods/values to
  an exact `[range_start, range_end)`, raising `InputVariantRangeError` on
  gaps/mismatches, and normalizes TS-2's offset-qualified instants back to
  the legacy naive-timestamp contract `system_case_json.time_series[]`
  expects) and `materialize_variant_time_series` (merges per-signal rows
  into wide period rows; generic over signal count for future slices).
- `AnalystStore` additions: `get_or_create_case_for_scenario` (generalizes
  the previously hydraulic-only `_get_or_create_optimization_case`),
  `get_or_create_default_input_variant`, `upsert_case_time_series_binding`,
  `list_case_time_series_bindings`, `materialize_system_case_for_variant`
  (builds `system_case_json` from the scenario's structured draft topology/
  parameters plus the variant's resolved bindings, discarding the draft's
  own legacy `time_series` so an unvalidated/unrelated draft source can
  never block generation).
- API: `GET /api/scenarios/{id}/case/default-variant`,
  `POST /api/scenarios/{id}/case/variants/{variant_id}/bindings`,
  `POST /api/scenarios/{id}/case/variants/{variant_id}/run` — the run route
  reuses the existing `save_validated_scenario_version` /
  `create_and_enqueue_run` closures unchanged, and records variant id, date
  range and series lineage (`signal_key`, set id/version/revision/hash) in
  `generation_metadata_json` alongside TS-1's topology/parameter hashes.
- React: `CaseInputVariantPanel` on the scenario page — lists the project's
  time-series sets, binds one to `price_usd_per_mwh`, prefills the date
  range from the chosen set's horizon, and launches the run, navigating to
  `/runs/{id}` on success.

Chrome-devtools + real Postgres + real Julia verification (per user
request) caught two real bugs unit tests missed, both fixed and covered by
new regression tests before re-verifying:

1. `generate_system_case_from_draft` raised on an unvalidated legacy
   time-series source left attached to the draft from the TS-2 catalog
   upload flow, even though TS-3 never reads that path. Fixed by stripping
   the draft's `time_series` before generation in
   `materialize_system_case_for_variant` (regression:
   `test_materializes_even_when_draft_has_an_unvalidated_legacy_source`).
2. TS-2 catalog periods store instants with a UTC offset (e.g.
   `...-03:00`); Julia's `system_case_json.time_series[].timestamp` parser
   rejects offsets and expects a naive local ISO-8601 string. Fixed by
   stripping the offset in `resolve_bound_signal_series` via
   `_naive_iso_timestamp` (regression:
   `test_timezone_offset_periods_produce_naive_timestamps`).

A third finding was a modeling choice, not a bug: the optimizer rejects
`import_price_usd_per_mwh` alone ("must provide both import and export
prices when using separate prices"). The tracer bullet binds the single
legacy `price_usd_per_mwh` signal instead, consistent with "one binding for
one signal family (grid price)" — binding both halves of the asymmetric
pair is TS3-005 scope (bind all required signal families).

## Verification

- `.venv\Scripts\python.exe -m unittest discover -s tests -v` — 252 tests,
  1 skipped (pre-existing Postgres-only skip), all passing.
- `npm test -- --run`, `npx tsc -b`, `npx eslint .`, `npm run api:check`,
  `npm run build` — all clean in `frontend/`.
- Live end-to-end run in Chrome (chrome-devtools MCP) against the real
  `energy_dispatch` Postgres database and real Julia: created project
  "TS3-001 Chrome QA" / scenario "TS3-001 grid battery case" (grid + battery
  only, no load/renewable/hydro, so price is the only required series),
  uploaded a 6-hour price CSV through the existing TS-2 draft-editor import
  flow, bound it to the default variant's `price_usd_per_mwh` signal from
  the new panel, ran with the auto-filled full-horizon range, and watched
  Run 8 reach `succeeded` (HiGHS `OPTIMAL`, exit code 0) with dispatch
  charts/tables showing the uploaded prices driving battery charge/discharge
  as expected.

## Blocked by

BESS-TS3-000
