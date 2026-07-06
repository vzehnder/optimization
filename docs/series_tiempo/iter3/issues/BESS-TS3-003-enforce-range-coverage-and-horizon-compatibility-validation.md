# BESS-TS3-003: Enforce Range Coverage And Horizon Compatibility Validation

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/series_tiempo/iter3/prd.md`
Fecha de inicio planificada: 2026-07-14
Fecha de termino planificada: 2026-07-15

## User stories covered

11, 12, 19

## What to build

Harden variant validation against the selected date range. Before a run is
launched, the backend verifies that every bound set covers the requested range
with no missing dates and that all bound sets share exactly compatible
periods; mixed resolutions fail with explicit errors because TS-3 does no
implicit resampling. A successful validation records the exact set revisions
and content hashes it validated against, so later stale detection and run
lineage have a fixed reference.

Coverage and horizon-compatibility logic lives in the same deep validation
module as binding resolution. React shows the validation outcome states
(valid, incomplete coverage, mismatched periods) with actionable messages.

## Acceptance criteria

- [ ] Range coverage validation rejects a run whose bindings do not cover the requested dates, naming the failing binding and the missing span.
- [ ] Horizon compatibility validation rejects mixed or incompatible period resolutions with explicit errors; no implicit resampling occurs.
- [ ] A successful validation records the bound set revisions and content hashes it validated against.
- [ ] Backend tests cover complete, incomplete and mismatched-period scenarios per binding.
- [ ] The React run flow surfaces validation states (valid, incomplete coverage, mismatched periods) before launch.

## Blocked by

BESS-TS3-002
