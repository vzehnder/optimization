# BESS-ITER5-003: Harden Hydro Contract Validation And v1 Regression

Status: Done
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

- [x] Validation rejects unsupported schema versions and still accepts `v1` and
      `v2`.
- [x] Validation rejects unknown node types, duplicate IDs, missing bus/PCC,
      multiple bus/PCC nodes, and disconnected hydro assets.
- [x] Validation rejects missing or negative hydro inflow values.
- [x] Validation rejects invalid storage bounds and initial/terminal storage
      outside bounds.
- [x] Validation rejects storage bounds outside the reservoir curve domain.
- [x] Validation rejects invalid terminal condition settings.
- [x] Validation rejects negative spill penalty, terminal water value, minimum
      release, and turbine flow bounds.
- [x] Validation rejects linear mode without required linear coefficient and
      max turbine flow.
- [x] Validation rejects invalid piecewise flow and power breakpoints.
- [x] Validation allows nonconvex and nonmonotone piecewise power breakpoints.
- [x] Validation rejects missing or invalid reservoir curves.
- [x] Existing `v1` sample cases still validate, solve, and write compatible
      outputs.
- [x] Existing Iteration 4 separate-price cases still validate, solve, and
      render results.
- [x] Tests cover error messages at the contract boundary rather than private
      implementation details.

## Implementation notes

- Expanded the Julia contract-boundary validation suite for `v2` hydro invalid
  graph, inflow, storage, terminal, penalty, turbine-flow, linear-generation,
  piecewise-generation, and reservoir-curve cases.
- Kept nonconvex and nonmonotone piecewise power breakpoints accepted by
  loader validation.
- Made reservoir-curve domain errors name the specific offending storage field
  so analysts see the exact invalid bound.
- Re-ran the full Julia optimizer suite and full Python web suite, preserving
  existing `v1` sample, paste/upload, separate-price, result-table, and chart
  regressions.

## Verification

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Julia package tests: 468 passed.
- Python web/API/template/results tests: 67 passed.

## Blocked by

BESS-ITER5-001, BESS-ITER5-002
