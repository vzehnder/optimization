# BESS-ITER3-007: Review Run Summary And Result Tables

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

34, 35, 36

## What to build

Add basic browser review of completed run results. The UI/API should read the
existing Julia output artifacts and present the run summary, system dispatch
table, and asset dispatch table without modifying the source files.

This is the first results-review slice and should remain table-focused.

## Acceptance criteria

- [x] A completed run detail page shows key fields from `summary.json`.
- [x] The API exposes parsed summary data for a completed run.
- [x] The UI can show `dispatch.csv` as a period-level table.
- [x] The UI can show `asset_dispatch.csv` as an asset-level table.
- [x] Table rendering handles the current Iteration 2 output columns.
- [x] Missing or malformed result artifacts surface clear errors.
- [x] The results reader does not mutate artifact files.
- [x] Tests cover summary parsing, dispatch table parsing, asset table parsing,
      API responses, and template smoke rendering.

## Implementation notes

- Added an artifact-backed results reader that parses `summary.json`,
  `dispatch.csv`, and `asset_dispatch.csv` from registered run artifacts under
  the configured artifact root.
- Added `GET /api/runs/{run_id}/results` with parsed summary and table payloads
  plus clear responses for unavailable, missing, unsafe, or malformed result
  artifacts.
- Extended the completed run detail page to show summary fields and horizontal
  tables for system-level and asset-level dispatch results.
- Kept result files read-only; tests assert artifact contents and timestamps
  are not changed by result parsing.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web tests: 35 passed.
- Julia package tests: 351 passed.
- Local app verification: started the FastAPI app on
  `http://127.0.0.1:8017`, seeded a completed run with registered result
  artifacts, confirmed `/api/runs/3/results` returned parsed summary and both
  tables, and confirmed `/runs/3` rendered `Run Summary`, `System Dispatch`,
  and `Asset Dispatch`.

Browser note: attempted the requested in-app Browser workflow three times, but
the `node_repl` browser-control runtime failed to start with
`windows sandbox failed: spawn setup refresh`. The local server/UI was verified
through the same HTTP surface after the Browser-control retry failed.

## Blocked by

BESS-ITER3-006
