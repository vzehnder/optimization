# BESS-TS3-005: Bind All Required Signal Families

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21
Fecha de termino real: 2026-07-07

## User stories covered

5, 6, 7, 8

## What to build

Extend variant bindings beyond grid prices to every signal family a case can
require: load demand per load asset, renewable availability per renewable
asset, hydraulic inflows per reservoir or junction, and reach minimum flows
when the constraint is active. Bindings are entity-scoped, so the same
canonical signal kind can be bound to different sets for different assets.

Required-signal discovery from BESS-TS3-002 must cover all families for
representative cases (hybrid one-bus and hydraulic-diagram cases), and a run
from a variant with multi-family bindings must materialize and execute end to
end.

BESS-TS3-002's Chrome verification already found the concrete blocker: once a
variant binds an entity-scoped signal (`load_demand_mw`,
`renewable_available_power_mw`, `hydro_inflow_m3s`) alongside price and runs,
Julia rejects it with `ArgumentError: <signal> for asset <id> is required at
time_series[i]`. `resolve_bound_signal_series`/`materialize_variant_time_series`
(`app/input_variants.py`, TS3-001) write every bound signal as a flat scalar
column, but `generate_system_case_from_draft`'s legacy contract expects
entity-scoped signals as a `{asset_id: value}` map per period (see
`draft_editor._period_from_validated_row`). This slice needs to make bindings
entity-scoped (so `case_time_series_bindings` records which asset a binding
applies to) and fix materialization to emit the map shape for those signal
families.

## Acceptance criteria

- [x] Load demand signals can be bound per load asset.
- [x] Renewable availability signals can be bound per renewable asset.
- [x] Hydraulic inflow signals can be bound per reservoir or junction requiring inflows.
- [x] Reach minimum-flow signals can be bound when the case activates that constraint, and are not required otherwise.
- [x] Required-signal discovery covers all families for representative hybrid and hydraulic cases.
- [x] An end-to-end run from a variant with multi-family bindings materializes the correct series into the snapshot and reaches a terminal state.

## Resolution

Entity-scoped bindings implemented: `case_time_series_bindings` gained
nullable `entity_type`/`entity_id` columns (migrated on both SQLite and
PostgreSQL), scoped by a unique `(variant, signal_key, entity_type,
entity_id)` constraint so the same canonical signal can bind different sets
per asset. `discover_required_signals` (`app/required_signals.py`) now walks
both the one-bus `nodes` list (grid/load/renewable/hydro) and the
hydraulic-diagram `hydraulic_network.required_time_series` /
`reaches[].flow_min_source == "series"` shapes to enumerate every
entity-scoped requirement; `evaluate_variant_completeness` matches bindings
to requirements by exact entity, falling back to the legacy unscoped-price
path only for the grid family. `materialize_variant_time_series`
(`app/input_variants.py`) now keys bound signals by
`(signal_key, entity_type, entity_id)` and, for any signal whose TS-2 catalog
definition carries an `entity_type`, writes it into the snapshot as an
`{asset_id: value}` map instead of a flat scalar, matching
`generate_system_case_from_draft`'s legacy contract. The React case panel
(`CaseInputVariantBindingEditor` in `frontend/src/Workspace.tsx`) renders one
series-select per required signal, keyed by entity, and binds/runs all of
them before launching.

Verification: Python suite 276 passed / 2 skipped (the 2 skips are the
Postgres-only integration tests, gated behind `POSTGRES_TEST_DATABASE_URL`);
frontend suite 56 passed plus `tsc -b`, `eslint .`, `api:check`, and `build`.

Chrome-devtools MCP against real PostgreSQL (project `TS3-005 Chrome QA`,
scenario `Multi-family case`, a hybrid one-bus case with grid + load_1 +
solar_1 + battery_1) found a real bug: binding the unscoped price signal
(`entity_type`/`entity_id` both `NULL`) 500'd with
`psycopg.errors.IndeterminateDatatype: could not determine data type of
parameter $3` from `upsert_case_time_series_binding`'s existence-check query
-- PostgreSQL cannot infer a parameter's type from a bare `? IS NULL`
comparison with no other typed context in the same statement, so SQLite
(used by the rest of the test suite) never caught it. Fixed by casting those
parameters explicitly (`CAST(? AS TEXT) IS NULL`) in `app/persistence.py`.
Added a regression test in `tests/test_postgres_persistence.py`
(`test_upsert_case_time_series_binding_handles_null_and_scoped_entity_columns`),
confirmed RED against the real database with the old query and GREEN with
the fix. After the fix, binding price (unscoped) + `load_demand_mw` for
`load_1` + `renewable_available_power_mw` for `solar_1` and running reached
Run 11 `succeeded` (HiGHS `OPTIMAL`, objective `-272.9`); the run detail's
asset dispatch table confirmed the per-asset `load_demand_mw` (2.5/3.1/2.8)
and `renewable_used_mw` (0/1.2/1.8) values matched the bound CSVs exactly,
proving entity-scoped materialization reached Julia correctly end to end.

## Blocked by

BESS-TS3-002
