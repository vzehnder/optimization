# BESS-TS4-009: Compare Two Runs Of The Same Case

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-28
Fecha de termino planificada: 2026-07-29

## User stories covered

15, 16, 17

## What to build

A basic comparison surface for two runs of the same case. The analyst picks a
baseline run and a comparison run (for example "Default" versus "Hidrologia
seca", or "precios v1" versus "precios v2"), and sees the differences in key
KPIs plus period-level differences for a selected result series, all sourced
from the indexed BBDD results. Each compared run's input variant and date
range must be visible so the analyst understands what assumption changed.

This is not a BI tool: two runs, same case, KPI diffs and one selected series
at a time. Comparing a run that has no indexed results must fail gracefully
with a clear message pointing at the rebuild path instead of a blank screen.

## Acceptance criteria

- [ ] Two runs of the same case can be selected and compared from the UI.
- [ ] The comparison shows differences in key KPIs between the two runs.
- [ ] The comparison shows period-level differences for a selected result series.
- [ ] Each compared run's input variant and date range are visible for context.
- [ ] Comparing a non-indexed run fails gracefully with a message pointing at the rebuild path.
- [ ] Tests cover comparing two runs with different input variants or different ranges.

## Blocked by

BESS-TS4-002, BESS-TS4-004
