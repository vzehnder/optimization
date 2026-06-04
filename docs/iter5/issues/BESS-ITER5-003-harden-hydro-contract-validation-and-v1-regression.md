# BESS-ITER5-003: Harden Hydro Contract Validation And v1 Regression

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

28 through 42, 55 through 56, 62

## What to build

Harden the `v2` hydro contract so invalid hydro data fails before model
construction with explicit errors, and prove that legacy `v1` behavior remains
stable.

This slice should focus on invalid schemas, graph validation, hydro parameter
validation, hydro time-series validation, curve domain validation, infeasible or
unbounded configuration guards where possible, and compatibility for existing
single-price and separate-price non-hydro cases.

## Acceptance criteria

- [ ] Validation rejects unsupported schema versions and still accepts `v1` and
      `v2`.
- [ ] Validation rejects unknown node types, duplicate IDs, missing bus/PCC,
      multiple bus/PCC nodes, and disconnected hydro assets.
- [ ] Validation rejects missing or negative hydro inflow values.
- [ ] Validation rejects invalid storage bounds and initial/terminal storage
      outside bounds.
- [ ] Validation rejects storage bounds outside the reservoir curve domain.
- [ ] Validation rejects invalid terminal condition settings.
- [ ] Validation rejects negative spill penalty, terminal water value, minimum
      release, and turbine flow bounds.
- [ ] Validation rejects linear mode without required linear coefficient and
      max turbine flow.
- [ ] Validation rejects invalid piecewise flow and power breakpoints.
- [ ] Validation allows nonconvex and nonmonotone piecewise power breakpoints.
- [ ] Validation rejects missing or invalid reservoir curves.
- [ ] Existing `v1` sample cases still validate, solve, and write compatible
      outputs.
- [ ] Existing Iteration 4 separate-price cases still validate, solve, and
      render results.
- [ ] Tests cover error messages at the contract boundary rather than private
      implementation details.

## Blocked by

BESS-ITER5-001, BESS-ITER5-002
