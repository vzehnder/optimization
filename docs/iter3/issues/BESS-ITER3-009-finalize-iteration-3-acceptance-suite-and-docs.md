# BESS-ITER3-009: Finalize Iteration 3 Acceptance Suite And Docs

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

41 through 54

## What to build

Finalize Iteration 3 with an acceptance suite and documentation proving the
complete private analyst flow from project creation through scenario versioning,
manual execution, artifact persistence, result review, and downloads.

This is the closing proof issue, not the first implementation of core behavior.

## Acceptance criteria

- [x] Documentation explains how to configure the app locally.
- [x] Documentation explains the database configuration approach and the
      PostgreSQL/Supabase-compatible direction without requiring Supabase.
- [x] Documentation explains how to run the internal web app.
- [x] Documentation explains how to validate and save a `system_case_json`.
- [x] Documentation explains how to launch a manual run and inspect status.
- [x] Documentation explains where artifacts are stored and how downloads map
      to Julia output files.
- [x] A final acceptance test covers project creation, scenario creation,
      scenario version creation, Julia validation, manual run launch, successful
      completion, artifact registration, summary/table review, chart data, and
      download behavior.
- [x] Failure-path acceptance coverage proves invalid inputs and failed Julia
      runs are persisted with useful errors and logs.
- [x] Backend/API tests, template smoke tests, and results reader tests pass.
- [x] The Julia regression suite remains green.
- [x] The tracker is updated with verification instructions for Iteration 3.

## Implementation notes

- Added `tests/test_iter3_acceptance.py` as the final Iteration 3 acceptance
  suite. It exercises the API-visible analyst flow from project creation
  through scenario creation, validated scenario version save, manual run launch,
  successful run completion, artifact registration, results API/table/chart
  payloads, HTML run detail rendering, artifact downloads, malformed JSON
  rejection, and a failed Julia process with persisted stdout/stderr logs.
- Extended `README.md` with local FastAPI setup, `DATABASE_URL` and
  `ARTIFACT_ROOT` configuration, the SQLite local store and
  PostgreSQL/Supabase-compatible direction, internal app startup, scenario
  validation/save workflow, manual run/status workflow, artifact storage, and
  final verification commands.
- Added final Iteration 3 verification instructions to this tracker so future
  slices have a single local checklist for the Python web suite and Julia
  optimizer regression suite.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter3_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Final Iteration 3 acceptance tests: 2 passed.
- Python web/API/template/results tests: 40 passed.
- Julia package tests: 351 passed.
- Local HTTP verification: started the FastAPI app on
  `http://127.0.0.1:8020` and confirmed `/projects`,
  `/system-cases/validate`, and `/api/projects` returned successful responses.

Browser note: attempted the requested in-app Browser workflow three times,
including one runtime reset, but the `node_repl` browser-control runtime failed
to start with `windows sandbox failed: spawn setup refresh`. The local server/UI
was verified through the same HTTP surface after the Browser-control retries
failed.

## Blocked by

BESS-ITER3-001, BESS-ITER3-002, BESS-ITER3-003, BESS-ITER3-004, BESS-ITER3-005, BESS-ITER3-006, BESS-ITER3-007, BESS-ITER3-008
