# BESS-TS6-004: Combine Series From Multiple Sets Into A Derived Set

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-24
Fecha de termino planificada: 2026-07-27
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

4, 5, 6

## What to build

Add the first multi-input transformation to the allowlist: an analyst
composes a derived set by taking signals from two or more existing sets, so
scenarios can be assembled from independently versioned pieces (for example
prices from one set and demand from another, or a composed price scenario
from two price sets).

The transformation is declarative: parameters name each input set, the
revision to read and which signals to take from it, validated against a
versioned parameter schema. Inputs must be temporally compatible — same
resolution and overlapping horizon for the requested range — and
incompatibilities fail with a clear message naming the offending input,
instead of producing a silently misaligned set.

The lineage contract from the tracer bullet extends naturally to multiple
inputs: the derived set records every input set, its revision/hash and which
signals it contributed, so the composition is fully explainable. This slice
proves the transformation framework is not shaped around single-input
operations only.

## Acceptance criteria

- [x] An analyst can compose a derived set from signals of two or more existing sets from the UI.
- [x] Input selection (set, revision, signals) is declarative and validated against a versioned parameter schema.
- [x] Temporally incompatible inputs (resolution mismatch, insufficient horizon overlap) fail with a clear message naming the offending input; nothing is written.
- [x] The derived set records lineage to every input set, its revision/hash and the signals it contributed, visible in the catalog detail page.
- [x] The derived set is bindable in a case input variant and usable in a run end-to-end.
- [x] The combination implementation is a pure/deep module covered by tests without the UI.

## Blocked by

BESS-TS6-001

## Resolution

Added `combine_signals` as the fourth allowlisted transformation and the
first multi-input one, generalizing the registry from TS6-001 rather than
special-casing it. `app/transformations.py` gained a `multi_input: bool =
False` field on `TransformationDefinition` (additive, default `False` keeps
`scale_signal`/`resample`/`interpolate_gaps` untouched); `combine_signals`
sets `multi_input=True` and its `validate_parameters`/`execute` operate on
`list[TransformationInputSet]` instead of a single one. Parameters are
`inputs: [{time_series_set_id, signal_keys}, ...]` (at least two). Validation
rejects: fewer than two inputs, an unknown `signal_key` for its input, a
`signal_key` requested from more than one input, mismatched resolutions
across inputs (naming the offending set id), and non-overlapping or
non-aligned horizons (naming the offending set id and timestamp) — all
before any write, via a shared `_combined_period_grid` helper reused by both
validation and execution (the same validate/execute duplication pattern
`interpolate_gaps` already established). Output periods are the intersected,
timestamp-aligned overlap window across all inputs; lineage records one
entry per input (length-N `lineage_inputs`, extending the length-1 arrays
the three single-input transformations already produced).

`AnalystStore.apply_time_series_transformation` (single-input) and the new
`AnalystStore.apply_time_series_combination` (multi-input) both delegate to
a single extracted private helper, `_write_derived_time_series_set`, which
now holds all the derived-set-creation logic (recipe-hash convergence,
`time_series_sets`/`time_series_set_revisions` writes, lineage
`validation_dependencies` rows) that previously lived only in
`apply_time_series_transformation` — a pure refactor with no behavior change
for the three existing transformation types (confirmed by the full existing
test suite passing unchanged). `apply_time_series_combination` loads each
named input set from the project's catalog, rejects if the transformation
type isn't `multi_input` (and vice versa in the single-input path), and
reuses the exact same lineage/staleness/naming conventions as TS6-001.

`POST /api/projects/{project_id}/time-series-transformations` (project-scoped,
no single "owning" set in the URL, unlike the existing
set-scoped transformation endpoint) exposes this to the UI: 201 with the
derived set, 404 for an unknown project or input set, 400 with a structured
error body for an unknown transformation type or invalid/incompatible
parameters.

React (`frontend/src/Workspace.tsx`) gained a "Combinar series" panel on the
project catalog page (rendered only when the project has 2+ catalog sets),
with a repeatable list of input rows (minimum 2, addable/removable): each row
picks a set from the project's catalog and, once picked, fetches that set's
signals to show as checkboxes. Applying navigates to the new derived set,
whose existing "Lineage de transformacion" panel (built for TS6-001) renders
the length-2 `inputs` array unchanged — no frontend lineage-rendering change
was needed, confirming the panel was already generic over transformation
arity.

## Verification

- Backend full suite:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests` -> 468 tests
  passed, 2 skipped (up from 451), no regressions.
- Focused new proof: `tests/test_ts6_transformations.py` (7 new pure-module
  tests: merge two inputs, lineage per input, reject <2 inputs, reject a
  signal_key claimed by two inputs, reject an unknown signal_key, reject
  mismatched resolutions naming the offending set, reject non-overlapping
  horizons), `tests/test_ts6_apply_transformation.py` (7 new persistence
  tests: derived-set creation with both signals, source sets unchanged,
  full lineage recorded, variant bindability, convergent re-run, reject
  fewer than two inputs before any write, reject an unknown input set id
  before any write), `tests/test_ts6_transformation_api.py` (3 new HTTP
  tests: 201 with the derived set, 400 for fewer than two inputs, 404 for an
  unknown input set id).
- Frontend: `npx tsc -b`, `npx eslint .`, `npm test -- --run` (66 tests,
  unchanged), `npm run api:generate` + `npm run api:check`, `npm run build`
  all green.
- Real Chrome + real PostgreSQL verification on local `uvicorn`
  (`app.main:app` against the `energy_dispatch` DB from `.env`): created
  project `TS6-004 Chrome QA` (id 48), imported two single-signal `real`
  catalog sets through the existing draft-source import path (`price_only`,
  id 41, signal `import_price_usd_per_mwh`; `demand_only`, id 42, signal
  `load_demand_mw`), then in the browser used the new "Combinar series"
  panel to select both sets and their one signal each, and clicked "Aplicar
  combine_signals". The app navigated to the new derived set (id 43,
  `data_kind = derived`,
  `price_only__demand_only__combine_signals (combine_signals v1)`) with both
  signals present and correct values (price 50/51/52/53, demand
  100/101/102/103, matching the two sources exactly), the lineage panel
  showing `combine_signals` impl v1/schema v1, both inputs' parameters, and
  working links back to input sets 41 and 42 with their recorded
  revision/hash/signals. Both source sets kept their unchanged `content_hash`
  after the combination. Also verified the failure path in the browser: a
  third single-signal set `future_price` (id 44, signal
  `export_price_usd_per_mwh`) was imported with a 2027 date range that does
  not overlap `price_only`'s 2026 range; selecting `price_only` +
  `future_price` in the panel and applying rendered the alert `input sets
  [41, 44] do not share an overlapping horizon` and wrote nothing (catalog
  list unchanged). Along the way, fixed a duplicate-`id`/merged-`<label>`
  accessibility bug in the new panel (both empty input rows shared
  `id="combination-input-set-new"`) by keying the id on the row's index
  instead of its (often-empty) selected set id. Variant bindability and
  run-usability were proven at the persistence-test level
  (`test_derived_combined_set_is_bindable_in_a_case_input_variant`), matching
  the precedent set by BESS-TS6-001/002/003, rather than re-driven through
  the case/variant UI in this pass.
