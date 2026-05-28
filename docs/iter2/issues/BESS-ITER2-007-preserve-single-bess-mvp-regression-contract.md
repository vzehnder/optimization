# BESS-ITER2-007: Preserve Single-BESS MVP Regression Contract

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

18, 26, 27

## What to build

Keep the iteration 1 single-BESS MVP behavior stable while adding system dispatch.

This slice should establish the regression guard used throughout iteration 2. Any refactor needed to reuse battery logic in the system model must preserve the existing public API, input files, outputs, Plotly flow, and acceptance behavior for the original single-BESS case.

## Acceptance criteria

- [x] Existing single-BESS public functions remain available.
- [x] Existing YAML and CSV sample case still loads.
- [x] Existing single-BESS dispatch model still solves.
- [x] Existing output files and columns remain stable.
- [x] Existing Plotly report flow remains stable.
- [x] Existing acceptance scenarios for constant price, low-high-low price, variable duration, terminal condition, degradation, and anti-simultaneity still pass.
- [x] No iteration 2 JSON requirement is imposed on iteration 1 cases.
- [x] The tracker documents that this regression suite must be run with every code-changing iteration 2 slice.

## Implementation notes

- Added an explicit single-BESS MVP public contract test in `test/runtests.jl`.
- The regression guard asserts the existing exported public names remain available.
- The guard proves the original `data/cases/arbitrage_mvp` YAML/CSV case still runs without requiring `system_case.json`.
- The existing suite continues to cover persisted output columns, Plotly report generation, and MVP acceptance scenarios.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 163 tests.

The Plotly report smoke test is part of the Julia suite and generated `plots/dispatch_report.html` from a temporary sample run.

## Blocked by

None - can start immediately.
