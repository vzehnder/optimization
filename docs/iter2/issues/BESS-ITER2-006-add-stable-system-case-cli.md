# BESS-ITER2-006: Add Stable System Case CLI

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter2/prd_bess_system_dispatch.md`

## What to build

Add a stable CLI for running a system case JSON through the Julia optimization engine.

This CLI is the iteration 2 preparation point for a future Python backend. It should be usable by a Python process without depending on Julia internals.

## Acceptance criteria

- [ ] A command-line script runs a system case from a JSON file path.
- [ ] The CLI accepts an output root argument.
- [ ] The CLI exits nonzero on validation or solve failure.
- [ ] The CLI prints parseable JSON to stdout on success.
- [ ] The stdout JSON includes case name, run timestamp, output directory, summary path, and termination status.
- [ ] Human-oriented logs do not corrupt stdout JSON.
- [ ] CLI behavior is documented.

## Verification

Run the CLI from the repository root against the sample system case and parse stdout as JSON in a test.

## Blocked by

BESS-ITER2-005
