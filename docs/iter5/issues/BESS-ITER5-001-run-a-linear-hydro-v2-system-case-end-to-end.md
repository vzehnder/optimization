# BESS-ITER5-001: Run A Linear Hydro v2 System Case End To End

Status: Todo
Type: AFK
Triage: ready-for-agent
Source: `docs/iter5/prd_hydro_simple_dispatch.md`

## User stories covered

1 through 25, 34 through 39, 47 through 52, 57, 61 through 62, 65

## What to build

Add the first complete `bess_system_dispatch.v2` hydro path through the Julia
optimizer using linear hydro generation.

The slice should load a valid `v2` system case with one hydro asset, validate
the hydro node and inflow time series, normalize it into one-bus optimization
data, solve a dispatch with reservoir balance, spill, minimum release, terminal
condition, terminal water value, and write auditable outputs containing hydro
system totals, asset-level hydro rows, summary KPIs, metadata, and the resolved
system case.

## Acceptance criteria

- [ ] `bess_system_dispatch.v2` is accepted by the system-case loader.
- [ ] Legacy `bess_system_dispatch.v1` remains accepted by the loader.
- [ ] A `hydro` node with linear generation can be parsed, validated, and
      normalized.
- [ ] Hydro inflow in `m3/s` is required for every hydro asset and period.
- [ ] The reservoir balance updates storage in `hm3` using duration-based
      flow-to-volume conversion.
- [ ] Storage bounds, initial storage, terminal condition, spill, minimum
      release, spill penalty, and terminal water value are enforced.
- [ ] Linear hydro power equals
      `power_per_flow_mw_per_m3s * turbine_flow_m3s`.
- [ ] Hydro power enters the one-bus balance as supply.
- [ ] `dispatch.csv` includes hydro total columns.
- [ ] `asset_dispatch.csv` includes `asset_type = hydro` rows with hydro
      metrics.
- [ ] `summary.json` includes hydro KPIs by asset and totals.
- [ ] `model_metadata.json` includes `v2`, hydro asset IDs, hydro unit
      conventions, and active hydro constraints.
- [ ] A sample linear hydro `system_case.json` exists under `data/cases` and
      solves through the Julia API and CLI.
- [ ] The full Julia regression suite remains green.

## Blocked by

BESS-ITER5-000
