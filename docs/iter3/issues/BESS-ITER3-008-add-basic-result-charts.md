# BESS-ITER3-008: Add Basic Result Charts

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter3/prd_analyst_web_flow.md`

## User stories covered

37, 38, 39, 40

## What to build

Add a minimal internal chart view for completed runs using the existing parsed
results. The charts should help an analyst inspect grid interaction, renewable
curtailment, battery behavior, and period economics without creating a
configurable dashboard system.

The charts must be derived from `dispatch.csv` and `asset_dispatch.csv`.

## Acceptance criteria

- [x] The run results view includes a grid import/export chart.
- [x] The run results view includes a renewable used/curtailed chart.
- [x] The run results view includes a BESS charge/discharge/SOC chart when
      battery columns are available.
- [x] The run results view includes a period profit chart.
- [x] Charts use the same artifact-derived data exposed by the results reader.
- [x] The UI handles missing optional chart columns gracefully.
- [x] No configurable dashboard or saved dashboard template behavior is added.
- [x] Tests or template smoke checks verify that chart data is present for a
      completed sample run.

## Implementation notes

- Added chart payloads to the artifact-backed results reader for grid
  import/export, renewable used/curtailed, BESS charge/discharge/SOC, and
  period profit.
- Extended `/api/runs/{run_id}/results` to include chart data alongside the
  existing summary and table payloads.
- Added server-rendered SVG chart panels to the completed run detail page with
  stable responsive dimensions and simple legends.
- Missing optional chart columns now render as unavailable chart panels with a
  clear missing-column message instead of failing the results view.
- Kept scope to fixed basic charts only; no configurable dashboards or saved
  dashboard templates were added.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
julia --project=. -e "import Pkg; Pkg.test()"
```

Results:

- Python web tests: 38 passed.
- Julia package tests: 351 passed.
- Local HTTP verification: started the FastAPI app on
  `http://127.0.0.1:8018`, seeded a completed run with registered result
  artifacts, confirmed `/api/runs/1/results` returned all four chart payloads,
  and confirmed `/runs/1` rendered the four SVG chart panels.

Browser note: attempted the requested in-app Browser workflow twice, but the
`node_repl` browser-control runtime failed to start with
`windows sandbox failed: spawn setup refresh`. The local server/UI was verified
through the same HTTP surface after the Browser-control retries failed.

## Blocked by

BESS-ITER3-007
