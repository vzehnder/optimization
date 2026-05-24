# BESS-MVP-005: Add Binary Anti-Simultaneity Dispatch Mode

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Implement the configurable binary formulation that prevents simultaneous charge and discharge in the same period. When enabled, the model should be a MILP with one binary mode variable per period. When disabled, the model should not require that binary variable.

This slice should verify the physical behavior through solved dispatch results.

## Acceptance criteria

- [ ] When enabled, charge power is allowed only in charging mode.
- [ ] When enabled, discharge power is allowed only in non-charging mode.
- [ ] Solved results never contain charge and discharge above tolerance in the same period when the flag is enabled.
- [ ] When disabled, the model can be built without the anti-simultaneity binary variable.
- [ ] Tests cover enabled and disabled configurations.

## Blocked by

- BESS-MVP-003
