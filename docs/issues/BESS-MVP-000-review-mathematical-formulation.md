# BESS-MVP-000: Review Mathematical Formulation Before Implementation

Status: Todo
Type: HITL
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Review the PRD and mathematical model as the implementation contract for the MVP. Confirm that the objective, units, time convention, energy balance, terminal modes, anti-simultaneity approach, and delta-SOC degradation formulation are coherent before model implementation starts.

This issue is complete when the modeling contract is either approved as-is or updated with explicit corrections.

## Acceptance criteria

- [ ] The PRD and mathematical model are reviewed together.
- [ ] Any required modeling corrections are documented and applied before implementation.
- [ ] The chosen MVP defaults are confirmed: HiGHS, full horizon, one BESS, `equal_initial` terminal mode, binary anti-simultaneity, and delta-SOC degradation.
- [ ] The tracking register records the review outcome and date.

## Blocked by

None - can start immediately.
