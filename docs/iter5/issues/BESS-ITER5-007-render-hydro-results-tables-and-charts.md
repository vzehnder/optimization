# BESS-ITER5-007: Render Hydro Results Tables And Charts

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

48 through 54

## What to build

Extend the results reader and server-rendered run results view so completed
hydro runs expose hydro tables, summary KPIs, and basic charts from existing
Julia artifacts.

The app should read hydro columns from `dispatch.csv`, `asset_dispatch.csv`,
and `summary.json` without mutating source artifacts. Runs without hydro should
continue to render existing charts and show graceful missing-column fallbacks.

## Acceptance criteria

- [x] Results API returns hydro columns from `dispatch.csv`.
- [x] Results API returns hydro rows from `asset_dispatch.csv`.
- [x] Results API returns hydro KPIs from `summary.json`.
- [x] Result tables display hydro totals and hydro asset rows.
- [x] Charts include hydro power, turbine flow, spill flow, storage, and
      reservoir elevation when columns are present.
- [x] Hydro chart payloads identify source columns and units.
- [x] Runs without hydro still render existing price, grid, renewable, BESS,
      and profit charts.
- [x] Missing hydro columns do not break legacy result pages.
- [x] Artifact contents are not modified by result reading.
- [x] Tests cover API and SSR behavior for hydro and legacy results.

## Blocked by

BESS-ITER5-006

## Implementation notes

Completed on 2026-06-05.

- Extended the result reader chart payload with hydro power, hydro flow,
  hydro storage, and reservoir elevation charts.
- Kept hydro chart series explicit about source artifact columns, source file,
  and units.
- Rendered hydro KPIs from `summary.json` in the server-rendered run page.
- Preserved existing dispatch and asset-dispatch table rendering so hydro
  totals and hydro asset rows appear from the existing CSV artifacts without
  mutating those artifacts.
- Kept legacy result pages working with existing price, grid, renewable, BESS,
  and profit charts plus missing-column fallbacks for absent hydro columns.

## Verification

Passed:

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_results_review -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter3_acceptance -v
.\.venv\Scripts\python.exe -m unittest tests.test_iter4_acceptance -v
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

Results:

- Results review suite: 13 passed.
- Iteration 3 acceptance suite: 2 passed.
- Iteration 4 acceptance suite: 2 passed.
- Full Python web/API/template/results suite: 81 passed.
- Chrome DevTools local verification opened `http://127.0.0.1:8037/runs/1`,
  confirmed Hydro Summary, hydro charts, hydro dispatch tables, HTTP 200 page
  and status polling responses, no console messages, and saved a screenshot to
  `.tmp/iter5-007-hydro-results-devtools.png`.

Browser note: attempted the requested in-app Browser workflow twice, but the
local browser-control runtime failed with `windows sandbox failed: spawn setup
refresh`. Chrome DevTools MCP verification completed successfully.
