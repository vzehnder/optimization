# BESS-ITER6-003: Create Minimal Dashboard Templates

Status: Todo
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

- [ ] Internal users can create a dashboard template under a project.
- [ ] Dashboard templates have a human-readable name.
- [ ] Dashboard templates can enable or disable standard chart sections for
      price, grid, renewable, BESS, hydro, and period profit.
- [ ] Dashboard templates can enable or disable summary display.
- [ ] Dashboard templates can enable or disable system dispatch table preview.
- [ ] Dashboard templates can enable or disable asset dispatch table preview.
- [ ] Table preview limits are controlled by template defaults or a simple
      template setting.
- [ ] Dashboard templates can be updated without changing scenario versions,
      runs, or artifacts.
- [ ] Template rendering reuses existing result-reader behavior.
- [ ] Templates degrade gracefully when selected sections are not available in a
      run's artifacts.
- [ ] Legacy single-price runs render without separate-price assumptions.
- [ ] Runs without hydro columns render without hydro chart failures.
- [ ] Templates remain scoped to their project.

## Blocked by

BESS-ITER6-001

