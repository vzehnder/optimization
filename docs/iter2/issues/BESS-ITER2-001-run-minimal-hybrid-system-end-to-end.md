# BESS-ITER2-001: Run Minimal Hybrid System End To End

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

1, 2, 3, 9, 10, 11, 12, 14, 18, 19, 20, 21, 23, 25, 27

## What to build

Build the first complete system-dispatch tracer bullet: a versioned JSON case with one bus, one renewable, one battery, and one grid connection can be loaded, validated enough for the happy path, normalized into solver-facing data, solved with a one-bus JuMP model, and written to machine-readable outputs.

This slice should be intentionally narrow. It should prove the full architecture before all edge-case validation and optional scenarios are added.

## Acceptance criteria

- [x] A minimal versioned `system_case` JSON contract exists for bus, renewable, battery, grid, common time series, solver settings, and constraints.
- [x] A valid renewable plus BESS plus grid JSON case loads from disk.
- [x] The loader produces graph-level data with stable asset IDs.
- [x] The normalizer converts the graph case into aligned optimization data without exposing raw JSON to the model builder.
- [x] The one-bus model enforces grid import plus renewable used plus battery discharge equals grid export plus battery charge.
- [x] Renewable availability is split into used and curtailed power.
- [x] Battery energy balance, power bounds, terminal condition, and optional degradation follow the iteration 1 convention.
- [x] The objective maximizes net grid market value minus battery degradation and optional curtailment cost.
- [x] The case solves to optimality with HiGHS.
- [x] A run creates `summary.json`, `model_metadata.json`, resolved system input, wide `dispatch.csv`, and long `asset_dispatch.csv`.
- [x] Output files preserve input asset IDs.
- [x] Existing single-BESS tests remain green after the slice.

## Implementation notes

- Added a parallel system-dispatch API for loading, validating, normalizing, solving, and running a versioned `system_case` JSON.
- Added a one-bus JuMP model for renewable plus BESS plus grid with bus balance, renewable used/curtailed split, battery physics, terminal condition, degradation, net market-value objective, and default grid import/export anti-simultaneity.
- Added machine-readable system outputs: `summary.json`, `model_metadata.json`, `system_case_resolved.json`, wide `dispatch.csv`, and long `asset_dispatch.csv`.
- Preserved the existing single-BESS MVP API and tests.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 222 tests, including the new happy-path system case test and the existing single-BESS regression tests.

## Blocked by

BESS-ITER2-000
