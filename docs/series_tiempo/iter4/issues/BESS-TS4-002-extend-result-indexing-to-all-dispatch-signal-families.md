# BESS-TS4-002: Extend Result Indexing To All Dispatch Signal Families

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-13
Fecha de termino planificada: 2026-07-14

## User stories covered

7, 9, 10

## What to build

Extend the tracer-bullet indexer so every `dispatch.csv` signal family that
feeds existing tables and charts is stored in BBDD: load demand, renewable
used and curtailed power, hydro generation, turbined flow, spill and storage
(covering both one-bus hydro and hydraulic-diagram cases), and the main
economics columns (profit, costs, revenues) where the UI consumes them.

Indexing must adapt to the case type: a column that does not exist for a given
case is simply absent from the indexed results, never an error and never a
fabricated zero series. Indexed series must map to canonical signal keys
rather than raw CSV column names, so downstream read, comparison and
publication surfaces do not depend on artifact column spelling.

## Acceptance criteria

- [ ] Load demand and renewable used/curtailed series index for hybrid cases.
- [ ] Hydro generation, turbined flow, spill and storage series index for hydro cases (one-bus and diagram).
- [ ] The economics columns used by existing UI (profit, costs, revenues) index when present.
- [ ] Case types missing a signal family index cleanly without spurious records or errors.
- [ ] Indexed series are identified by canonical signal keys, not raw CSV column names.
- [ ] Tests index representative artifacts from at least one hybrid run and one hydro run.

## Blocked by

BESS-TS4-001
