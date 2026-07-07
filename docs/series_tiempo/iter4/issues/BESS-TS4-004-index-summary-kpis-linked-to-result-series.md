# BESS-TS4-004: Index Summary KPIs Linked To Result Series

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter4/prd.md`
Fecha de inicio planificada: 2026-07-16
Fecha de termino planificada: 2026-07-16

## User stories covered

12

## What to build

Index the KPIs of `summary.json` (objective value, solver status and the
totals the summary panel consumes) in BBDD, linked to the run and associated
with the run's indexed result series so dashboards can resolve headline
numbers and their backing series together without opening artifacts.

The run summary surface must serve KPIs from BBDD when indexed and fall back
to artifacts for runs without indexed results, rendering identically in both
paths.

## Acceptance criteria

- [ ] Summary KPIs from `summary.json` index in BBDD linked to the run.
- [ ] Indexed KPIs are associated with the run's result series so dashboards can load both quickly.
- [ ] The run summary endpoint serves KPIs from BBDD when indexed, artifacts otherwise.
- [ ] The React summary panel renders identically from indexed KPIs.
- [ ] Tests prove KPI indexing from representative artifacts.

## Blocked by

BESS-TS4-001
