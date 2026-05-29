# BESS-ITER3-001: Validate A System Case From The Web App

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

10, 11, 12, 49, 50, 51, 52

## What to build

Build the first web-to-Julia integration slice: an internal web/API path accepts
a candidate `system_case_json`, performs lightweight JSON parsing, delegates
contract validation to Julia without solving, and returns a clear success or
error response to the analyst.

The Julia validation path should load and normalize the system case using the
same authority as execution, but it must not run the optimization model.

## Acceptance criteria

- [ ] A minimal FastAPI application can serve an internal validation page or
      endpoint.
- [ ] A user can paste a candidate `system_case_json` into the validation flow.
- [ ] Malformed JSON fails before Julia is invoked and returns a clear syntax
      error.
- [ ] A valid Iteration 2 sample system case validates successfully through
      Julia without solving.
- [ ] An invalid system case returns a clear Julia validation error to the API
      and UI.
- [ ] The Julia validation command prints parseable success JSON on stdout.
- [ ] The Julia validation command exits nonzero and emits structured error
      data on failure.
- [ ] The existing Julia execution CLI remains compatible.
- [ ] The Julia regression suite remains green.
- [ ] Backend tests cover success, malformed JSON, and Julia validation failure.

## Blocked by

BESS-ITER3-000
