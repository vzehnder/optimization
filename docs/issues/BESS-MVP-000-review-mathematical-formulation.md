# BESS-MVP-000: Review Mathematical Formulation Before Implementation

Status: Done
Type: HITL
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Review the PRD and mathematical model as the implementation contract for the MVP. Confirm that the objective, units, time convention, energy balance, terminal modes, anti-simultaneity approach, and delta-SOC degradation formulation are coherent before model implementation starts.

This issue is complete when the modeling contract is either approved as-is or updated with explicit corrections.

## Review outcome

Reviewed on 2026-05-24.

The PRD and mathematical model are approved as the MVP implementation contract after applying these clarifications:

- `terminal_energy_min_mwh` is part of `ConstraintConfig`, required only for `terminal_condition = min_terminal`, and must be within BESS energy bounds.
- Core physical constraints (`energy_balance`, `soc_bounds`, `power_bounds`) are mandatory in standard MVP runs and are not exposed as configurable fields.
- `p_charge_mw` and `p_discharge_mw` are grid-side average power variables, so charging and discharging efficiencies map between grid energy and stored energy.
- If linear delta-SOC degradation is disabled in a future run mode, the objective omits the degradation term and reported `delta_soc_abs_mwh` values should be zero.

Confirmed MVP defaults:

- Solver: HiGHS.
- Horizon: full horizon.
- Assets: one BESS.
- Terminal condition: `equal_initial`.
- Anti-simultaneity: binary charge/discharge mode enabled.
- Degradation: linear delta-SOC degradation enabled.

## Acceptance criteria

- [x] The PRD and mathematical model are reviewed together.
- [x] Any required modeling corrections are documented and applied before implementation.
- [x] The chosen MVP defaults are confirmed: HiGHS, full horizon, one BESS, `equal_initial` terminal mode, binary anti-simultaneity, and delta-SOC degradation.
- [x] The tracking register records the review outcome and date.

## Blocked by

None - can start immediately.
