# BESS-MVP-009: Prove MVP With Acceptance Scenario Suite

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Add the final MVP verification layer: scenario-based tests and run instructions that prove the implementation satisfies the PRD acceptance criteria end to end.

This slice should make it clear how to run the Julia tests, execute the sample case, and generate the Plotly report.

## Acceptance criteria

- [ ] The test suite covers constant prices with positive degradation and verifies no unnecessary cycling.
- [ ] The test suite covers low-high-low prices and verifies charge/discharge timing when feasible.
- [ ] The test suite verifies `equal_initial` terminal energy within tolerance.
- [ ] The test suite verifies anti-simultaneity within tolerance.
- [ ] The test suite verifies variable duration energy accounting.
- [ ] Project documentation explains how to run tests.
- [ ] Project documentation explains how to run the sample case.
- [ ] Project documentation explains how to generate the Plotly report.

## Blocked by

- BESS-MVP-007
- BESS-MVP-008
