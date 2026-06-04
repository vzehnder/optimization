# BESS-ITER5-007: Render Hydro Results Tables And Charts

Status: Todo
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

- [ ] Results API returns hydro columns from `dispatch.csv`.
- [ ] Results API returns hydro rows from `asset_dispatch.csv`.
- [ ] Results API returns hydro KPIs from `summary.json`.
- [ ] Result tables display hydro totals and hydro asset rows.
- [ ] Charts include hydro power, turbine flow, spill flow, storage, and
      reservoir elevation when columns are present.
- [ ] Hydro chart payloads identify source columns and units.
- [ ] Runs without hydro still render existing price, grid, renewable, BESS,
      and profit charts.
- [ ] Missing hydro columns do not break legacy result pages.
- [ ] Artifact contents are not modified by result reading.
- [ ] Tests cover API and SSR behavior for hydro and legacy results.

## Blocked by

BESS-ITER5-006
