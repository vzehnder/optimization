# BESS-HYDRO-DIAGRAM-010: Reject Unsupported Topologies And Stale Promotions

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/hydro_diagram/iter1/prd_hydro_diagram_editor.md`

## User stories covered

16 through 18, 42 through 48, 54, 59, 60, 63 through 67

## What to build

Harden the diagram workflow around unsupported topology and stale validation.
The editor may draw general directed graphs, but promotion and execution must
reject graph shapes outside the MVP solver capability, such as unsupported
cycles, unresolved islands, inactive endpoint references, unsupported routing,
head-dependent generation and stale validation snapshots.

The UI should keep errors actionable by selecting or linking affected diagram
entities.

## Acceptance criteria

- [x] Validation detects unsupported cycles for the MVP solver.
- [x] Validation detects disconnected islands without boundary conditions.
- [x] Validation detects unsupported routing or travel-time settings.
- [x] Validation detects head-dependent, pump-only or reversible unit modes as
      unsupported for the MVP solver.
- [x] Validation detects stale dependencies after topology, parameter, curve or
      time-series edits.
- [x] Promotion is blocked when validation is missing or stale.
- [x] Error payloads include entity references where possible.
- [x] The UI can select or focus affected diagram components from validation
      messages.
- [x] Tests cover each unsupported topology and stale promotion case.
- [x] Existing v1, v2 and valid v3 cases still validate and run.

## Resolution

Topology validation (`AnalystStore._validate_unsupported_topology`) now rejects,
with entity references, unsupported reach routing/travel-time, directed cycles,
disconnected islands without a boundary condition (reservoir or natural inflow),
and head-dependent/pump-only/reversible unit modes. Pure graph helpers
(`hydraulic_first_cycle`, `hydraulic_weakly_connected_components`) implement the
cycle and island detection as a deep module. Reaches persist
`routing_method`/`travel_time_hours`; `hydraulic_units` gains
`operation_mode`/`generation_mode` (default `generation`/`flow_power_curve`).
Stale validation after any topology/parameter/curve/series edit and the
missing/stale promotion block were already enforced and are now covered by
tests. The React validation summary renders each error as a focus button that
selects the affected diagram node or reach.

Verified: `python -m unittest discover tests` (155 ok, 1 skipped), Julia
`Pkg.test()` (532 ok), React `vitest` (26 ok), `tsc`/`eslint`,
`npm run api:generate`+`api:check`, hydraulic Playwright e2e (1 passed) and a
Chrome DevTools MCP smoke against live PostgreSQL (cycle/routing/pump/island
validation plus error-to-component focus).

## Blocked by

BESS-HYDRO-DIAGRAM-008, BESS-HYDRO-DIAGRAM-009

