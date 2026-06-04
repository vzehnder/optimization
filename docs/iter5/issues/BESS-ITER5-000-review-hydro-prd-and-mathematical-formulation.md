# BESS-ITER5-000: Review Hydro PRD And Mathematical Formulation

Status: Todo
Type: HITL
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

1 through 68

## What to build

Review the Iteration 5 PRD and mathematical model against the final product
objective, completed one-bus optimizer contract, and completed structured editor
workflow.

The review should confirm that Iteration 5 is correctly scoped around simple
reservoir hydropower, contract `v2`, linear and piecewise generation, editor
support, ingestion, and hydro results while keeping cascades, delays,
dashboard publishing, scheduling, auth, and client portal work out of scope.

## Acceptance criteria

- [ ] The decision to model one `hydro` node as one independent reservoir plus
      one associated plant is accepted.
- [ ] The decision to exclude hydraulic cascades, hydraulic networks, and
      travel-time delays is accepted.
- [ ] The units are accepted: storage in `hm3`, operational flows in `m3/s`,
      power in `MW`, duration in hours, and economics in USD.
- [ ] The reservoir balance and flow-to-volume conversion are accepted.
- [ ] The linear generation mode is accepted.
- [ ] The piecewise generation mode using `PiecewiseLinearOpt.piecewiselinear`
      with the package default method is accepted.
- [ ] The decision to allow nonconvex and nonmonotone power-flow breakpoints is
      accepted.
- [ ] The mandatory storage-elevation reservoir curve and reporting-only use
      are accepted.
- [ ] The spill penalty, minimum release, terminal storage condition, and
      terminal water value behavior are accepted.
- [ ] The decision to introduce `bess_system_dispatch.v2` while preserving `v1`
      compatibility is accepted.
- [ ] The structured editor, CSV/XLSX ingestion, result rendering, and
      acceptance-test scope are accepted.

## Blocked by

None - can start immediately
