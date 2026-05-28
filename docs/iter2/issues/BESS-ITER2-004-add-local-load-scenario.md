# BESS-ITER2-004: Add Local Load Scenario

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

10, 17, 20, 23, 24, 25, 30

## What to build

Add an end-to-end local load scenario. A `load` asset provides fixed demand by period, validation ensures the series is complete and nonnegative, and the one-bus balance serves that load from grid import, renewable used, or battery discharge.

## Acceptance criteria

- [ ] The system JSON contract supports `load` nodes with load demand keyed by load asset ID.
- [ ] Missing load demand for a load asset is rejected.
- [ ] Negative load demand is rejected.
- [ ] Load enters the one-bus balance as fixed consumption.
- [ ] A load scenario solves with supply from at least one available source.
- [ ] Wide dispatch output reports total load per period.
- [ ] Long asset dispatch output reports load demand by load asset ID.
- [ ] Existing minimal hybrid, validation, and single-BESS tests remain green after the slice.

## Verification

Run load validation tests, a solved load-balance scenario, the minimal system test, and existing MVP tests.

## Blocked by

BESS-ITER2-001, BESS-ITER2-002
