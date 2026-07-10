# BESS-TS6-001: Apply One Allowlisted Transformation End-To-End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter6/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-17
Fecha de inicio real: 2026-07-10
Fecha de termino real: 2026-07-10

## User stories covered

3, 5, 6, 14, 15, 16

## What to build

The tracer bullet for the TS-6 transformation layer: an analyst opens a
validated time-series set in the project catalog, chooses the simplest
allowlisted transformation (`scale_signal`), provides declarative parameters
(target signal and scale factor) validated against a versioned parameter
schema, and executes it. The result is a new derived set in the same catalog,
carrying full lineage: input set, input revision and content hash, validated
parameters, parameter schema version and transformation implementation
version.

The derived set behaves like any natively created set: it is listed in the
project catalog, browsable, and bindable in a case input variant. The catalog
detail page shows a lineage section explaining that the set was derived, from
what inputs and with what parameters, so derived data is explainable without
leaving the UI. The source set is never mutated; the transformation only adds
a new object.

The allowlist is enforced end-to-end: a transformation type outside the
allowlist is rejected, no user-provided script is ever stored or executed
from the database, and parameters that fail schema validation produce a clear
error before anything is written. Validation, execution and lineage recording
live in a deep module testable without the UI. Re-running the same
transformation with identical inputs and parameters converges without
duplicate sets or values.

The slice cuts through every layer with the thinnest possible path: one
transformation type, one execution surface in the UI, one lineage panel and
one binding proof in a variant. Resampling, interpolation, multi-set
combination, staleness and automation belong to later slices.

## Acceptance criteria

- [x] An analyst can apply `scale_signal` to a validated catalog set from the UI and obtain a new derived set in the project catalog.
- [x] Transformation types outside the allowlist are rejected, and no user-provided script is stored or executed from the database.
- [x] Parameters are validated against a versioned parameter schema, and invalid parameters produce a clear error before any write.
- [x] The derived set records lineage to the input set, input revision/hash, validated parameters, parameter schema version and implementation version, visible in the catalog detail page.
- [x] The derived set is bindable in a case input variant like any natively created set.
- [x] The source set remains unchanged and readable after the transformation.
- [x] Re-running the transformation with identical inputs and parameters converges without duplicate sets, revisions or values.
- [x] Transformation validation, execution and lineage recording live in a deep module testable without the UI.

## Blocked by

BESS-TS6-000

## Resolution

Added a code-level allowlist registry `app/transformations.py`
(`TRANSFORMATION_REGISTRY`), following the `TIME_SERIES_SIGNAL_CATALOG`
precedent from TS-2: one entry per `transformation_type` with
`implementation_version`, `parameter_schema_version`,
`validate_parameters(raw, input_set)` and `execute(input_set, parameters)`.
Only `scale_signal` is registered this iteration (single input, single
signal, multiplies by a validated finite `scale_factor`; every other signal
in the set passes through unchanged). A type absent from the registry is
rejected in `get_transformation_definition` before anything is validated or
written.

`AnalystStore.apply_time_series_transformation` (`app/persistence.py`) is the
persistence entry point: it loads the source set, runs the registry's
`validate_parameters`/`execute`, computes a deterministic recipe hash over
`(transformation_type, implementation_version, parameter_schema_version,
parameters, inputs)`, and looks up any existing derived set with that same
recipe hash before writing — this is what makes re-running the same
transformation converge without duplicate sets, revisions or values. A new
set follows the existing TS-2 version/revision scheme (new `time_series_sets`
row on first run, `data_kind = "derived"` added additively to
`TIME_SERIES_DATA_KINDS`), and its single revision stores lineage
(`transformation.type/implementation_version/parameter_schema_version/
parameters/inputs`) in the existing `time_series_set_revisions.metadata_json`
column plus rows in the existing `validation_dependencies` table
(`time_series_set` and `transformation_implementation` dependency types) —
no new tables, matching the TS-6 decision record. The source set's signals,
periods, values and content hash are never touched.

`POST /api/projects/{project_id}/time-series-sets/{time_series_set_id}/transformations`
(`app/main.py`) exposes this to the UI, returning 201 with the derived set,
404 for an unknown project/set and 400 with a structured error body for an
unknown transformation type or invalid parameters. The route carries no
extra permission gate beyond the existing internal-analyst/admin middleware,
matching the TS-5 permission-matrix precedent that input-series writes are
analyst+admin, not admin-only.

React (`frontend/src/Workspace.tsx`) gained a "Transformaciones" panel on the
catalog detail page (signal picker, scale factor, optional output
name/version label) that applies `scale_signal` and redirects to the new
derived set, and a "Lineage de transformacion" panel that reads
`revision_metadata.transformation` directly (type, implementation/schema
versions, parameters, and a link to each input set with its recorded
revision/hash/signals) — no extra query needed, per the TS-6 decision
record's lineage-panel contract. Derived sets need no special-casing in the
existing catalog list/detail views: they show up with `data_kind =
"derived"` like any other set, and bind into a case input variant through
the unchanged `case_time_series_bindings` path.

## Verification

- Backend full suite:
  `.\.venv\Scripts\python.exe -m unittest discover -s tests -v` -> 423 tests
  passed, 2 skipped, no regressions.
- Focused new proof: `tests/test_ts6_transformations.py` (6 tests, pure
  registry: unknown type rejected, scale-only-the-target-signal, unknown
  signal_key rejected, non-finite scale_factor rejected, lineage recorded,
  implementation/schema versions exposed),
  `tests/test_ts6_apply_transformation.py` (8 tests, persistence layer:
  derived-set creation, source-set immutability, unknown-type and
  invalid-parameter rejection before any write, full lineage in
  `revision_metadata`, variant bindability, convergent re-run, distinct
  params producing a second derived set), `tests/test_ts6_transformation_api.py`
  (4 tests, HTTP layer: 201 with derived set, 400 for unknown type, 400 for
  invalid parameters with no set created, 404 for unknown set).
- Frontend: `npx tsc -b`, `npx eslint .`, `npm test -- --run` (66 tests
  passed), `npm run api:generate` + `npm run api:check`, `npm run build` all
  green.
- Real Chrome + real PostgreSQL verification on local `uvicorn` (`app.main:app`
  against the `energy_dispatch` DB from `.env`): logged in as admin with the
  `.env` credentials, created project `TS6-001 Chrome QA` (id 45), seeded a
  `real` catalog set `Demand and price QA` (id 35, signals `load_demand_mw`,
  `import_price_usd_per_mwh`) through the existing import path, then in the
  browser set signal `load_demand_mw` and scale factor `2.0` in the new
  Transformaciones panel and clicked "Aplicar scale_signal". The app
  navigated to the new derived set (id 36, `data_kind = derived`,
  `Demand and price QA__scale_signal (scale_signal v1)`) with
  `load_demand_mw` doubled (100/101/102/103 -> 200/202/204/206) and
  `import_price_usd_per_mwh` unchanged (50/51/52/53). The lineage panel
  showed `scale_signal` impl v1 / schema v1, parameters
  `scale_factor=2, signal_key=load_demand_mw`, and a working link back to
  input set 35 with its recorded revision/hash/signals. The catalog list for
  project 45 showed both sets, with set 35's `content_hash` unchanged from
  before the transformation. Variant bindability was proven at the
  persistence-test level (`test_derived_set_is_bindable_in_a_case_input_variant`)
  rather than re-driven through the case/variant UI in this pass.
