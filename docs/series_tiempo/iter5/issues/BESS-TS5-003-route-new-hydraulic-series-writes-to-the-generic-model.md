# BESS-TS5-003: Route New Hydraulic Series Writes To The Generic Model

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter5/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-17

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

- [ ] New hydraulic inflow and minimum-flow series created from the hydro flow are persisted in the generic model, not in the legacy hydraulic tables.
- [ ] Case binding, validation, promotion and runs consume the new storage and produce the same executable payload as the legacy path for equivalent data.
- [ ] Pre-existing legacy hydraulic sets remain readable and usable side by side with newly written generic sets.
- [ ] Regression tests prove the hydro diagram flow (bind, validate, promote, run) stays green with the new write path.

## Blocked by

BESS-TS5-002
