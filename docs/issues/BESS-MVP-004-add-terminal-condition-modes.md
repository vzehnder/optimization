# BESS-MVP-004: Add Configurable Terminal Condition Modes

Status: Done
Type: AFK
Source: `docs/prd_bess_dispatch.md`, `docs/mathematical_model.md`

## What to build

Add terminal energy behavior controlled by case configuration. The model should support `none`, `equal_initial`, and `min_terminal` modes, with `equal_initial` as the MVP default.

The behavior must be testable from input data through solved results, not only as isolated constraint code.

## Acceptance criteria

- [x] `terminal_condition = none` solves without a final energy constraint.
- [x] `terminal_condition = equal_initial` constrains final energy to initial energy within numerical tolerance.
- [x] `terminal_condition = min_terminal` constrains final energy to the configured minimum.
- [x] Invalid terminal configuration fails during validation before model construction.
- [x] Tests cover all terminal modes.

## Blocked by

- BESS-MVP-003
