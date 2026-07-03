# BESS-TS1-000: Review TS-1 PRD And Hierarchy Semantics

Status: Done
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

- [x] The distinction between topology, parameters and execution snapshots is reviewed.
- [x] The decision about keeping `ScenarioVersion` as technical immutable snapshot is accepted or corrected.
- [x] The decision about whether TS-1 changes `Scenario` to `OptimizationCase` cardinality is accepted or deferred explicitly.
- [x] The treatment of curves as parameter-version selections is accepted or corrected.
- [x] The compatibility expectation for current structured draft and hydraulic diagram flows is accepted.
- [x] Any PRD correction is committed before downstream TS-1 implementation issues begin.

## Resolution

Accepted the TS-1 hierarchy semantics in
`docs/series_tiempo/iter1/decision_record_ts1_hierarchy.md`.

The review confirms:

1. `OptimizationCase` is the editable modeling object for this semantic area.
2. `ScenarioVersion` remains the immutable executable snapshot referenced by
   runs.
3. Topology covers structure and connectivity; layout-only state is excluded.
4. Parameters cover executable assumptions and concrete curve-version
   selections.
5. TS-1 defers any `Scenario -> OptimizationCase` cardinality migration.
6. Current structured draft, paste/upload JSON, hydraulic diagram, manual run,
   artifact, result and publication flows must remain compatible.

No PRD text correction is required before downstream TS-1 implementation.

## Verification

- `rg -n "TS-1 Hierarchy Semantics Decision Record|Status: Accepted|ScenarioVersion.*immutable executable snapshot|Cardinality migration is deferred|Curve treatment|Curves as parameter-version selections" docs\series_tiempo\iter1\decision_record_ts1_hierarchy.md`
  passed after adding the decision record.
- Chrome plugin connected successfully. Opening the local Markdown via `file://`
  was blocked by the browser URL policy, so no browser workaround was used.

## Blocked by

None - can start immediately.
