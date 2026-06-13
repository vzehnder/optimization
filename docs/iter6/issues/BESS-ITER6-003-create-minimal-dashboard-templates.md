# BESS-ITER6-003: Create Minimal Dashboard Templates

Status: Done
Type: AFK
Triage: ready-for-agent
Source: `docs/iter6/prd_client_publication_portal.md`

## User stories covered

23 through 37

## What to build

Add project-scoped dashboard templates that configure which existing result
sections can be shown in a client-facing publication. Templates should reuse
the current result readers and chart payloads for prices, grid, renewables,
BESS, hydro, profit, summary, and limited table previews.

This is not a custom dashboard builder. It is a simple curation layer over
standard result sections already produced by the application.

## Acceptance criteria

- [x] Internal users can create a dashboard template under a project.
- [x] Dashboard templates have a human-readable name.
- [x] Dashboard templates can enable or disable standard chart sections for
      price, grid, renewable, BESS, hydro, and period profit.
- [x] Dashboard templates can enable or disable summary display.
- [x] Dashboard templates can enable or disable system dispatch table preview.
- [x] Dashboard templates can enable or disable asset dispatch table preview.
- [x] Table preview limits are controlled by template defaults or a simple
      template setting.
- [x] Dashboard templates can be updated without changing scenario versions,
      runs, or artifacts.
- [x] Template rendering reuses existing result-reader behavior.
- [x] Templates degrade gracefully when selected sections are not available in a
      run's artifacts.
- [x] Legacy single-price runs render without separate-price assumptions.
- [x] Runs without hydro columns render without hydro chart failures.
- [x] Templates remain scoped to their project.

## Implementation notes

Completed on 2026-06-12.

- Added project-scoped `dashboard_templates` persistence with section toggles,
  human-readable names, audit metadata, and configurable table preview limits.
- Added internal dashboard-template APIs for create, list, read, update, and
  template-filtered run-result rendering.
- Added project-page SSR controls for creating and editing minimal dashboard
  templates without exposing them to client users.
- Added a result filtering layer that reuses `read_run_results`, selects chart
  groups by template settings, limits table preview rows, and preserves missing
  chart fallback payloads for legacy and non-hydro runs.
- Kept templates separate from scenario versions, runs, and run artifacts.

## Verification

```powershell
.\.venv\Scripts\python.exe -m unittest tests.test_iter6_dashboard_templates -v
.\.venv\Scripts\python.exe -m unittest tests.test_results_review tests.test_iter6_project_access tests.test_iter6_auth -v
```

## Blocked by

BESS-ITER6-001
