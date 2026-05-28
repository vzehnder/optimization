# BESS-ITER2-006: Publish Stable Julia API And CLI Contract

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## User stories covered

1, 22, 23, 27

## What to build

Publish the stable system-dispatch integration contract for Julia callers and a future Python backend.

The Julia API should be parallel to the single-BESS MVP API, and the CLI should run a system case JSON as a process-friendly boundary that prints compact JSON to stdout.

## Acceptance criteria

- [ ] Public Julia functions exist for loading a system case, solving system dispatch, and running a system case with persisted outputs.
- [ ] Existing single-BESS public functions remain available and unchanged.
- [ ] A command-line script runs a system case from a JSON file path.
- [ ] The CLI accepts an output root argument.
- [ ] The CLI exits nonzero on validation or solve failure.
- [ ] The CLI prints parseable JSON to stdout on success.
- [ ] The stdout JSON includes case name, run timestamp, output directory, summary path, and termination status.
- [ ] Human-oriented logs do not corrupt stdout JSON.
- [ ] API and CLI usage are documented for a future Python caller.
- [ ] Existing minimal hybrid and single-BESS tests remain green after the slice.

## Verification

Run API tests, parse CLI stdout as JSON in a test, run the minimal system test, and run existing MVP tests.

## Blocked by

BESS-ITER2-001
