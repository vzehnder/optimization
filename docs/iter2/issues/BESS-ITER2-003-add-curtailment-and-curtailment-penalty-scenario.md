# BESS-ITER2-003: Add Curtailment And Curtailment Penalty Scenario

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

11, 12, 13, 21, 23, 24, 25

## What to build

Add an end-to-end renewable curtailment scenario where available renewable generation exceeds feasible storage, load, or export. The optimizer must report used and curtailed renewable energy, and it must include optional curtailment penalties in the objective when configured.

## Acceptance criteria

- [x] Renewable assets accept `curtailment_penalty_usd_per_mwh`, defaulting to zero when omitted.
- [x] Negative curtailment penalties are rejected.
- [x] The model enforces available renewable power equals used plus curtailed power in every period.
- [x] A case with excess renewable availability curtails the infeasible excess.
- [x] Curtailment appears in wide system dispatch output.
- [x] Curtailment appears in long asset dispatch output with the renewable asset ID.
- [x] Objective value reflects configured curtailment penalties.
- [x] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Implementation notes

- Added loader-time validation for renewable `curtailment_penalty_usd_per_mwh`, including rejection of negative values.
- Added an end-to-end curtailment scenario where constrained export and limited battery storage force renewable curtailment.
- Verified default zero curtailment penalty, wide dispatch curtailment columns, long renewable asset curtailment rows, and objective impact from configured penalties.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 253 tests, including the curtailment scenario, objective-sign check with positive curtailment penalty, minimal system case, and existing MVP regression tests.

## Blocked by

BESS-ITER2-001
