# BESS-ITER3-005: Capture Failed Runs Logs And Input Snapshots

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

20, 21, 22, 23, 24, 26, 33

## What to build

Complete the failed-run path. When validation or Julia execution fails, the
backend must preserve the exact input snapshot, captured stdout and stderr,
process exit code, timestamps, and a structured error summary for the UI/API.

This slice should make failures auditable instead of transient process output.

## Acceptance criteria

- [x] Execution revalidates the exact run input snapshot before invoking the
      solver.
- [x] Failed validation during run execution marks the run failed and records a
      structured error.
- [x] A nonzero Julia process exit marks the run failed.
- [x] Complete stdout and stderr are captured as run artifacts or log files.
- [x] The database stores short structured fields for exit code, error message,
      started timestamp, finished timestamp, and duration.
- [x] The backend parses structured Julia error payloads from stderr when
      available.
- [x] The run detail UI/API shows failure status and a useful error message.
- [x] The input JSON used by the failed run remains available for audit.
- [x] Tests cover validation failure, process failure, log capture, and error
      display.

## Implementation notes

- Added execution-time revalidation of the exact `system_case.json` input
  snapshot before invoking the solve CLI.
- Failed execution validation now marks the run `failed`, preserves stdout,
  stderr, exit code, structured error payload, and the input snapshot path.
- Nonzero Julia process exits now persist a short `error_message`, parse
  structured stderr JSON when available, and keep complete stdout/stderr in the
  database.
- Added `stdout.log` and `stderr.log` files under each run workspace for
  auditable failed-run logs.
- Extended persisted run records with `error_message`, `stdout_log_path`, and
  `stderr_log_path`, including lightweight SQLite migration for existing local
  databases.
- Updated the run detail API and page polling UI to expose the failure message.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web tests: 25 passed.
- Julia package tests: 351 passed.
- Browser verification: run detail page at `/runs/1` showed `failed`, exit code
  `23`, and `optimization failed before solve`.

## Blocked by

BESS-ITER3-004
