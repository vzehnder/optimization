# BESS-ITER5-000: Review Hydro PRD And Mathematical Formulation

Status: Done
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

- [x] The decision to model one `hydro` node as one independent reservoir plus
      one associated plant is accepted.
- [x] The decision to exclude hydraulic cascades, hydraulic networks, and
      travel-time delays is accepted.
- [x] The units are accepted: storage in `hm3`, operational flows in `m3/s`,
      power in `MW`, duration in hours, and economics in USD.
- [x] The reservoir balance and flow-to-volume conversion are accepted.
- [x] The linear generation mode is accepted.
- [x] The piecewise generation mode using `PiecewiseLinearOpt.piecewiselinear`
      with the package default method is accepted.
- [x] The decision to allow nonconvex and nonmonotone power-flow breakpoints is
      accepted.
- [x] The mandatory storage-elevation reservoir curve and reporting-only use
      are accepted.
- [x] The spill penalty, minimum release, terminal storage condition, and
      terminal water value behavior are accepted.
- [x] The decision to introduce `bess_system_dispatch.v2` while preserving `v1`
      compatibility is accepted.
- [x] The structured editor, CSV/XLSX ingestion, result rendering, and
      acceptance-test scope are accepted.

## Review outcome

Reviewed on 2026-06-03 against `docs/final/objetivo_final.md`, the completed
Iteration 2 one-bus optimizer contract, the completed Iteration 3 analyst web
workflow, the completed Iteration 4 structured editor and ingestion workflow,
and `docs/iter5/mathematical_model.md`.

Accepted the PRD and mathematical formulation as the Iteration 5 implementation
contract. No corrections were required before starting downstream hydro
implementation.

## Accepted decisions

- Accepted one `hydro` node as one independent reservoir plus one associated
  plant, with multiple hydro nodes allowed only as independent one-bus assets.
- Accepted excluding hydraulic cascades, hydraulic networks, travel-time
  delays, pumped storage, and generation dependence on reservoir elevation from
  Iteration 5.
- Accepted the unit conventions: storage in `hm3`, operational flows in
  `m3/s`, power in `MW`, period duration in hours, prices in `USD/MWh`, and
  hydro economics in `USD/hm3`.
- Accepted the reservoir balance and the explicit `m3/s` to `hm3` conversion
  using `flow_m3s * duration_hours * 3600 / 1_000_000`.
- Accepted both linear hydro generation and piecewise hydro generation through
  `PiecewiseLinearOpt.piecewiselinear` with the package default method.
- Accepted nonconvex and nonmonotone power-flow breakpoints, with strictly
  increasing nonnegative flow breakpoints and nonnegative finite power values.
- Accepted the mandatory storage-elevation curve as a validation and reporting
  feature that does not affect generation in Iteration 5.
- Accepted spill penalty, optional minimum release, terminal storage modes, and
  terminal water value as scoped hydro behaviors.
- Accepted introducing `bess_system_dispatch.v2` for hydro while preserving
  `bess_system_dispatch.v1` paste/upload, CLI, result, and regression
  compatibility.
- Accepted structured editor hydro support, CSV/XLSX hydro inflow mapping,
  hydro result tables/charts, and Iteration 5 acceptance coverage as downstream
  implementation scope.

## Verification

Documentation review only. No executable code changed, so no automated test
command was required for this issue.

TDD note: this HITL gate has no public runtime interface change; the acceptance
criteria above served as the behavior checklist for the documentation review.

## Blocked by

None - can start immediately
