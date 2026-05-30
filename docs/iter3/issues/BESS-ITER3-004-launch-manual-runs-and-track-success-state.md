# BESS-ITER3-004: Launch Manual Runs And Track Success State

Status: Done
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

- [x] A manual run can be created from a saved scenario version.
- [x] Creating a run returns a run identifier without blocking on Julia solve
      completion.
- [x] Run records support queued, running, succeeded, and failed states.
- [x] The local runner processes runs with concurrency one.
- [x] The runner writes the exact scenario version input snapshot to the run
      workspace before execution.
- [x] The runner invokes the existing Julia system-dispatch execution boundary.
- [x] A valid sample case can complete successfully through the backend runner.
- [x] The runner records created, started, and finished timestamps.
- [x] The runner records exit code and parses the Julia success payload from
      stdout.
- [x] A run detail page or endpoint exposes state for polling.
- [x] Tests cover queued-to-running-to-succeeded behavior and state polling.
- [x] The Julia regression suite remains green.

## Implementation notes

- Added persisted `runs` records linked to immutable scenario versions, with
  `queued`, `running`, `succeeded`, and `failed` states plus timestamps, exit
  code, stdout/stderr, workspace, input snapshot, output directory, summary
  path, and parsed success/error payloads.
- Added a local FIFO run queue with a single background worker, wired into the
  FastAPI app by default and injectable in tests.
- Added `JuliaRunExecutor`, which writes the exact scenario version
  `system_case_json` to a controlled run workspace, invokes
  `scripts/run_system_case.jl`, parses the success JSON printed on stdout, and
  records the completed run state.
- Added API endpoints to create and poll manual runs:
  `/api/scenario-versions/{scenario_version_id}/runs` and `/api/runs/{run_id}`.
- Added server-rendered launch controls on the scenario page and a run detail
  page that polls the run state endpoint.
- Added run tests covering API creation, UI launch, polling through
  `queued -> running -> succeeded`, exact input snapshot writing, Julia command
  invocation, success payload parsing, and queue concurrency one.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Manual backend runner check against
`data/cases/hybrid_system/system_case.json` also passed through
`JuliaRunExecutor`, producing `status = succeeded`, `exit_code = 0`, and
`termination_status = OPTIMAL`.

Results:

- Python web tests: 22 passed.
- Julia package tests: 351 passed.

## Blocked by

BESS-ITER3-003
