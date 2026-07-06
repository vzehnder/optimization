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

## Acceptance criteria

- [ ] Load demand signals can be bound per load asset.
- [ ] Renewable availability signals can be bound per renewable asset.
- [ ] Hydraulic inflow signals can be bound per reservoir or junction requiring inflows.
- [ ] Reach minimum-flow signals can be bound when the case activates that constraint, and are not required otherwise.
- [ ] Required-signal discovery covers all families for representative hybrid and hydraulic cases.
- [ ] An end-to-end run from a variant with multi-family bindings materializes the correct series into the snapshot and reaches a terminal state.

## Blocked by

BESS-TS3-002
