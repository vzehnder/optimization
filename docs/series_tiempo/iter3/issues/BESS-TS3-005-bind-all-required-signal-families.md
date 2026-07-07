# BESS-TS3-005: Bind All Required Signal Families

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21

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

- [ ] Load demand signals can be bound per load asset.
- [ ] Renewable availability signals can be bound per renewable asset.
- [ ] Hydraulic inflow signals can be bound per reservoir or junction requiring inflows.
- [ ] Reach minimum-flow signals can be bound when the case activates that constraint, and are not required otherwise.
- [ ] Required-signal discovery covers all families for representative hybrid and hydraulic cases.
- [ ] An end-to-end run from a variant with multi-family bindings materializes the correct series into the snapshot and reaches a terminal state.

## Blocked by

BESS-TS3-002
