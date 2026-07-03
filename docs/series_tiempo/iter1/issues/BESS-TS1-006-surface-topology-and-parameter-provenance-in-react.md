# BESS-TS1-006: Surface Topology And Parameter Provenance In React

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-20
Fecha de termino planificada: 2026-07-21

## User stories covered

1, 5, 6, 9 through 12

## What to build

Expose topology and parameter provenance in the React analyst UI without making
the interface feel like a database inspector. Case, scenario version and run
detail views should show concise provenance such as topology label/hash,
parameter label/hash and stale state when applicable.

The feature should help the analyst understand what changed between alternatives
before time-series variants are introduced.

## Acceptance criteria

- [ ] Scenario version detail shows topology provenance when available.
- [ ] Scenario version detail shows parameter provenance when available.
- [ ] Run detail shows the topology and parameter provenance inherited from its scenario version.
- [ ] Case or editor views show current topology/parameter validation state when available.
- [ ] Old versions without provenance render graceful fallback text.
- [ ] Stale topology and stale parameter states are visually distinct enough for analyst action.
- [ ] React tests cover provenance display and fallback behavior.
- [ ] API client types remain in sync with backend responses.

## Blocked by

BESS-TS1-004
