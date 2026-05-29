# BESS-ITER2-004: Add Local Load Scenario

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

10, 17, 20, 23, 24, 25, 30

## What to build

Add an end-to-end local load scenario. A `load` asset provides fixed demand by period, validation ensures the series is complete and nonnegative, and the one-bus balance serves that load from grid import, renewable used, or battery discharge.

## Acceptance criteria

- [x] The system JSON contract supports `load` nodes with load demand keyed by load asset ID.
- [x] Missing load demand for a load asset is rejected.
- [x] Negative load demand is rejected.
- [x] Load enters the one-bus balance as fixed consumption.
- [x] A load scenario solves with supply from at least one available source.
- [x] Wide dispatch output reports total load per period.
- [x] Long asset dispatch output reports load demand by load asset ID.
- [x] Existing minimal hybrid, validation, and single-BESS tests remain green after the slice.

## Implementation notes

- Added `load_demand_mw` period input parsing and validation for every `load` asset ID.
- Added `LoadAssetParameters`, normalized load-demand matrices, and public export for the load asset parameter type.
- Added fixed local load to the one-bus balance as consumption and included load in derived finite grid bounds.
- Added `load_demand_mw` to wide dispatch output, long asset dispatch rows, resolved system input, and model metadata asset IDs.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 253 tests, including load validation, solved load-balance scenario, minimal system case, and existing MVP regression tests.

## Blocked by

BESS-ITER2-001, BESS-ITER2-002
