# BESS-MVP-001: Bootstrap Julia Package With Smoke Test

Status: Todo
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Create the initial Julia package skeleton for the BESS dispatch project and prove that the package can be loaded and tested from a clean checkout.

This slice should establish the minimum runnable path for future work: package metadata, module entry point, dependency declarations, and a smoke test that imports the package successfully.

## Acceptance criteria

- [ ] The repository contains a Julia package skeleton with a module entry point.
- [ ] Required MVP dependencies are declared: JuMP, HiGHS, CSV, DataFrames, YAML, JSON3, and Dates.
- [ ] A smoke test verifies that the package can be imported.
- [ ] The test command is documented in the tracking register or project docs.
- [ ] No optimization model behavior is implemented in this issue.

## Blocked by

None - can start immediately.
