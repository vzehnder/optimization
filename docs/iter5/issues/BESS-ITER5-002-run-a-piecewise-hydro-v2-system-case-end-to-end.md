# BESS-ITER5-002: Run A Piecewise Hydro v2 System Case End To End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

26 through 33, 57 through 60, 67

## What to build

Extend the Julia hydro path so a `bess_system_dispatch.v2` hydro asset can use
piecewise-linear generation and reservoir elevation curves through
`PiecewiseLinearOpt.piecewiselinear`.

The slice should prove a valid nonconvex or nonmonotone power-flow breakpoint
curve can validate, solve, produce hydro power from turbine flow, report
reservoir elevation from storage, and write the same auditable outputs as the
linear hydro path.

## Acceptance criteria

- [ ] `PiecewiseLinearOpt` is added as an explicit Julia dependency.
- [ ] Piecewise generation uses `PiecewiseLinearOpt.piecewiselinear` with the
      package default method.
- [ ] Generation breakpoints are accepted as explicit `(flow_m3s, power_mw)`
      pairs.
- [ ] Flow breakpoints must be strictly increasing and nonnegative.
- [ ] Power breakpoints must be finite and nonnegative.
- [ ] Nonconvex and nonmonotone power breakpoints are accepted.
- [ ] Optional turbine flow min/max limits must stay inside the breakpoint
      domain.
- [ ] Optional `power_max_mw` is enforced in piecewise mode.
- [ ] Reservoir storage-elevation breakpoints are modeled/reported with
      `PiecewiseLinearOpt.piecewiselinear`.
- [ ] A sample piecewise hydro case validates, solves, and writes outputs.
- [ ] Tests prove the piecewise hydro path and the linear hydro path both keep
      working.
- [ ] The full Julia regression suite remains green.

## Blocked by

BESS-ITER5-001
