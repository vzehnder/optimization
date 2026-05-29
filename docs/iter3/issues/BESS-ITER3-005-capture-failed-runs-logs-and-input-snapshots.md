# BESS-ITER3-005: Capture Failed Runs Logs And Input Snapshots

Status: Todo
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

- [ ] Execution revalidates the exact run input snapshot before invoking the
      solver.
- [ ] Failed validation during run execution marks the run failed and records a
      structured error.
- [ ] A nonzero Julia process exit marks the run failed.
- [ ] Complete stdout and stderr are captured as run artifacts or log files.
- [ ] The database stores short structured fields for exit code, error message,
      started timestamp, finished timestamp, and duration.
- [ ] The backend parses structured Julia error payloads from stderr when
      available.
- [ ] The run detail UI/API shows failure status and a useful error message.
- [ ] The input JSON used by the failed run remains available for audit.
- [ ] Tests cover validation failure, process failure, log capture, and error
      display.

## Blocked by

BESS-ITER3-004
