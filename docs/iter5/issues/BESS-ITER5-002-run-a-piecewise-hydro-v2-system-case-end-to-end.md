# BESS-ITER5-002: Run A Piecewise Hydro v2 System Case End To End

Status: Done
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

- [x] `PiecewiseLinearOpt` is added as an explicit Julia dependency.
- [x] Piecewise generation uses `PiecewiseLinearOpt.piecewiselinear` with the
      package default method.
- [x] Generation breakpoints are accepted as explicit `(flow_m3s, power_mw)`
      pairs.
- [x] Flow breakpoints must be strictly increasing and nonnegative.
- [x] Power breakpoints must be finite and nonnegative.
- [x] Nonconvex and nonmonotone power breakpoints are accepted.
- [x] Optional turbine flow min/max limits must stay inside the breakpoint
      domain.
- [x] Optional `power_max_mw` is enforced in piecewise mode.
- [x] Reservoir storage-elevation breakpoints are modeled/reported with
      `PiecewiseLinearOpt.piecewiselinear`.
- [x] A sample piecewise hydro case validates, solves, and writes outputs.
- [x] Tests prove the piecewise hydro path and the linear hydro path both keep
      working.
- [x] The full Julia regression suite remains green.

## Verification

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Result: 444 Julia tests passed.

## Blocked by

BESS-ITER5-001
