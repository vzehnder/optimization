# BESS-TS1-000: Review TS-1 PRD And Hierarchy Semantics

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/series_tiempo/iter1/prd.md`
Fecha de inicio planificada: 2026-07-03
Fecha de termino planificada: 2026-07-03

## User stories covered

1 through 20

## What to build

Review and accept the TS-1 PRD before implementation starts. The review should
confirm the semantic boundary between `Scenario`, `OptimizationCase`,
`TopologyVersion`, `CaseParameterVersion`, `ScenarioVersion` and `Run`.

The outcome should be a short accepted-decision record in the iteration docs,
including any corrections to the PRD if the hierarchy, scope or compatibility
plan needs adjustment.

## Acceptance criteria

- [ ] The distinction between topology, parameters and execution snapshots is reviewed.
- [ ] The decision about keeping `ScenarioVersion` as technical immutable snapshot is accepted or corrected.
- [ ] The decision about whether TS-1 changes `Scenario` to `OptimizationCase` cardinality is accepted or deferred explicitly.
- [ ] The treatment of curves as parameter-version selections is accepted or corrected.
- [ ] The compatibility expectation for current structured draft and hydraulic diagram flows is accepted.
- [ ] Any PRD correction is committed before downstream TS-1 implementation issues begin.

## Blocked by

None - can start immediately.
