# BESS-MVP-003: Solve Core Full-Horizon Arbitrage Model

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Build the first solvable JuMP model from validated `CaseData`. The model should cover the core continuous BESS arbitrage path: charge, discharge, end-of-period energy, energy balance, energy bounds, power bounds, and price-taker market value.

This slice should produce an optimization result in memory that can be inspected by tests. Optional terminal modes, binary anti-simultaneity, and degradation can be added in later slices.

## Acceptance criteria

- [ ] A validated sample case can be converted into a JuMP model.
- [ ] The model includes period-indexed `duration_hours`.
- [ ] The model enforces energy balance using end-of-period energy.
- [ ] The model enforces energy and power bounds.
- [ ] The objective maximizes price-taker arbitrage value before degradation.
- [ ] The model solves with HiGHS.
- [ ] Tests verify that a low-high-low price shape produces economically sensible dispatch when physically feasible.
- [ ] Tests verify that variable period duration changes energy according to `MW * hours = MWh`.

## Blocked by

- BESS-MVP-000
- BESS-MVP-002
