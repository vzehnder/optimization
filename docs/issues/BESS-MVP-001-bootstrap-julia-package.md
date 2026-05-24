# BESS-MVP-001: Bootstrap Julia Package With Smoke Test

Status: Done
Type: AFK
Source: `docs/prd_bess_dispatch.md`

## What to build

Create the initial Julia package skeleton for the BESS dispatch project and prove that the package can be loaded and tested from a clean checkout.

This slice should establish the minimum runnable path for future work: package metadata, module entry point, dependency declarations, and a smoke test that imports the package successfully.

## Acceptance criteria

- [x] The repository contains a Julia package skeleton with a module entry point.
- [x] Required MVP dependencies are declared: JuMP, HiGHS, CSV, DataFrames, YAML, JSON3, and Dates.
- [x] A smoke test verifies that the package can be imported.
- [x] The test command is documented in the tracking register or project docs.
- [x] No optimization model behavior is implemented in this issue.

## Verification

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

Result: passed.

## Blocked by

None - can start immediately.
