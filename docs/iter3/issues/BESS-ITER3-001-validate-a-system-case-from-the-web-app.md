# BESS-ITER3-001: Validate A System Case From The Web App

Status: Done
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

- [x] A minimal FastAPI application can serve an internal validation page or
      endpoint.
- [x] A user can paste a candidate `system_case_json` into the validation flow.
- [x] Malformed JSON fails before Julia is invoked and returns a clear syntax
      error.
- [x] A valid Iteration 2 sample system case validates successfully through
      Julia without solving.
- [x] An invalid system case returns a clear Julia validation error to the API
      and UI.
- [x] The Julia validation command prints parseable success JSON on stdout.
- [x] The Julia validation command exits nonzero and emits structured error
      data on failure.
- [x] The existing Julia execution CLI remains compatible.
- [x] The Julia regression suite remains green.
- [x] Backend tests cover success, malformed JSON, and Julia validation failure.

## Implementation notes

- Added `scripts/validate_system_case.jl` as a process-friendly validation CLI.
  It loads and normalizes a `system_case.json` through the existing Julia
  authority and does not build or solve the optimization model.
- Added a minimal FastAPI app in `app/main.py` with an internal validation page
  at `/system-cases/validate` and a JSON endpoint at
  `/api/system-cases/validate`.
- Added `app/validation.py` to parse malformed JSON in Python before invoking
  Julia, call the validation CLI for syntactically valid candidates, and return
  clear success or error results.
- Added Python backend/API/template tests covering valid sample validation,
  malformed JSON, Julia validation failure, API success/failure, and UI error
  rendering.
- Added Julia regression coverage for the validation CLI success contract,
  structured failure contract, and a structurally valid but infeasible case to
  prove validation does not solve.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web validation tests: 7 passed.
- Julia package tests: 351 passed.

## Blocked by

BESS-ITER3-000
