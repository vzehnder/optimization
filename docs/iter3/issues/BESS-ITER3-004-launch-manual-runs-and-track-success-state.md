# BESS-ITER3-004: Launch Manual Runs And Track Success State

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

16, 17, 18, 19, 23, 24, 25, 46, 47, 48

## What to build

Build the first successful execution path from a persisted scenario version:
the analyst launches a manual run, the backend records it as queued, a local
runner executes one Julia process at a time, and the run transitions through
running to succeeded with generated output paths recorded.

The UI should expose enough state for an analyst to see that a run was queued,
started, and completed.

## Acceptance criteria

- [ ] A manual run can be created from a saved scenario version.
- [ ] Creating a run returns a run identifier without blocking on Julia solve
      completion.
- [ ] Run records support queued, running, succeeded, and failed states.
- [ ] The local runner processes runs with concurrency one.
- [ ] The runner writes the exact scenario version input snapshot to the run
      workspace before execution.
- [ ] The runner invokes the existing Julia system-dispatch execution boundary.
- [ ] A valid sample case can complete successfully through the backend runner.
- [ ] The runner records created, started, and finished timestamps.
- [ ] The runner records exit code and parses the Julia success payload from
      stdout.
- [ ] A run detail page or endpoint exposes state for polling.
- [ ] Tests cover queued-to-running-to-succeeded behavior and state polling.
- [ ] The Julia regression suite remains green.

## Blocked by

BESS-ITER3-003
