# BESS-ITER2-008: Finalize Sample Docs And Acceptance Suite

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

1 through 30

## What to build

Finalize iteration 2 with a complete sample case, run documentation, and acceptance suite proving the full system-dispatch flow from JSON input through validation, normalization, solve, output writing, and CLI execution.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [x] A sample `system_case.json` exists for renewable plus BESS plus grid.
- [x] A sample or test scenario covers local load.
- [x] A sample or test scenario covers renewable curtailment.
- [x] A sample or test scenario covers grid limits and import/export anti-simultaneity.
- [x] The valid hybrid system JSON loads and validates.
- [x] Invalid graph and time-series cases fail before model construction.
- [x] The graph normalizer preserves asset IDs and aligns time-series data.
- [x] The renewable plus BESS plus grid scenario solves to optimality.
- [x] Wide and long dispatch outputs are generated.
- [x] CLI stdout is parseable JSON and points to generated outputs.
- [x] Run documentation shows the Julia API flow.
- [x] Run documentation shows the CLI flow.
- [x] Run documentation explains the output files.
- [x] Existing single-BESS regression tests remain green.

## Implementation notes

- Added `data/cases/hybrid_system/system_case.json` as the stable iteration 2 sample with one bus, renewable, BESS, grid, and local load.
- The sample covers local load, renewable curtailment, grid import/export limits, and default grid import/export anti-simultaneity in one valid JSON contract.
- Added a final acceptance test that loads the real sample JSON, validates and normalizes it, solves it, writes wide and long outputs, and runs the system CLI with parseable stdout.
- Extended README system-dispatch documentation to use the real sample path and explain generated output files and key dispatch columns.

## Verification

Passed:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

with 335 tests.

Also verified:

```powershell
julia --project=. scripts\run_system_case.jl data\cases\hybrid_system\system_case.json --output-root outputs --run-timestamp 2026-01-02T03:04:05
julia --project=. -e "using Dates, BESSDispatch; run_output = BESSDispatch.run_case(ARGS[1]; output_root = ARGS[2], run_timestamp = DateTime(ARGS[3])); println(run_output.output_dir)" data\cases\arbitrage_mvp outputs 2026-01-02T03:04:05
python python\plot_results.py outputs\arbitrage_mvp\20260102T030405000
```

## Blocked by

BESS-ITER2-002, BESS-ITER2-003, BESS-ITER2-004, BESS-ITER2-005, BESS-ITER2-006, BESS-ITER2-007
