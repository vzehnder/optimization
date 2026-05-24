# BESS-MVP-006: Add Linear Delta-SOC Degradation Cost

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Implement the MVP degradation formulation using an auxiliary nonnegative variable for absolute stored-energy movement in each period. The first period must compare against `initial_energy_mwh`; later periods must compare against the previous end-of-period energy.

The degradation term must reduce the objective and be available for reporting.

## Acceptance criteria

- [ ] `delta_soc_abs_mwh` is constrained against the initial energy in the first period.
- [ ] `delta_soc_abs_mwh` is constrained against the previous period energy for all later periods.
- [ ] The objective subtracts `degradation_cost_per_mwh_delta_soc * delta_soc_abs_mwh[t]`.
- [ ] With constant prices and positive degradation cost, the model does not cycle unnecessarily.
- [ ] When degradation is disabled, the model omits the degradation penalty or reports zero degradation consistently.
- [ ] Tests cover enabled and disabled degradation configurations.

## Blocked by

- BESS-MVP-003
