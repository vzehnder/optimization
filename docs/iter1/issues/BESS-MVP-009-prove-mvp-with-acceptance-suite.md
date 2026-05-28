# BESS-MVP-009: Prove MVP With Acceptance Scenario Suite

Status: Done
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Add the final MVP verification layer: scenario-based tests and run instructions that prove the implementation satisfies the PRD acceptance criteria end to end.

This slice should make it clear how to run the Julia tests, execute the sample case, and generate the Plotly report.

## Acceptance criteria

- [x] The test suite covers constant prices with positive degradation and verifies no unnecessary cycling.
- [x] The test suite covers low-high-low prices and verifies charge/discharge timing when feasible.
- [x] The test suite verifies `equal_initial` terminal energy within tolerance.
- [x] The test suite verifies anti-simultaneity within tolerance.
- [x] The test suite verifies variable duration energy accounting.
- [x] Project documentation explains how to run tests.
- [x] Project documentation explains how to run the sample case.
- [x] Project documentation explains how to generate the Plotly report.

## Verification

- `julia --project=. -e "import Pkg; Pkg.test()"` passed with 153 tests.
- Documented sample-case command produced `outputs\arbitrage_mvp\20260526T100855145`.
- `python python/plot_results.py outputs\arbitrage_mvp\20260526T100855145` produced `plots\dispatch_report.html`.

## Blocked by

- BESS-MVP-007
- BESS-MVP-008
