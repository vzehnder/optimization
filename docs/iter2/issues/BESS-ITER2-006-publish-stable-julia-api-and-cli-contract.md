# BESS-ITER2-006: Publish Stable Julia API And CLI Contract

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

1, 22, 23, 27

## What to build

Publish the stable system-dispatch integration contract for Julia callers and a future Python backend.

The Julia API should be parallel to the single-BESS MVP API, and the CLI should run a system case JSON as a process-friendly boundary that prints compact JSON to stdout.

## Acceptance criteria

- [x] Public Julia functions exist for loading a system case, solving system dispatch, and running a system case with persisted outputs.
- [x] Existing single-BESS public functions remain available and unchanged.
- [x] A command-line script runs a system case from a JSON file path.
- [x] The CLI accepts an output root argument.
- [x] The CLI exits nonzero on validation or solve failure.
- [x] The CLI prints parseable JSON to stdout on success.
- [x] The stdout JSON includes case name, run timestamp, output directory, summary path, and termination status.
- [x] Human-oriented logs do not corrupt stdout JSON.
- [x] API and CLI usage are documented for a future Python caller.
- [x] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Implementation notes

- Added an explicit system-dispatch public API regression test for `load_system_case`, `normalize_system_case`, `build_system_dispatch_model`, `solve_system_dispatch`, `run_system_case`, and `write_system_run_outputs`.
- Added `scripts/run_system_case.jl` as the stable process boundary for a future Python worker.
- The CLI accepts a `system_case.json` path, `--output-root`, and an optional `--run-timestamp` for deterministic runs.
- On success the CLI prints compact JSON to stdout with `case_name`, `run_timestamp`, `output_dir`, `summary_path`, and `termination_status`.
- On validation or solve failure the CLI exits nonzero and writes error JSON to stderr, leaving stdout empty and parseable for success-only callers.
- Updated `README.md` with the Julia API flow, CLI command, stdout contract, failure behavior, and generated system output files.

## Verification

Passed `julia --project=. -e "import Pkg; Pkg.test()"` with 299 tests, including API export checks, parseable CLI stdout, CLI nonzero validation failure, minimal hybrid, and existing MVP regression tests.

## Blocked by

BESS-ITER2-001
