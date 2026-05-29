# BESSDispatch

Julia package for the single-BESS price-taker dispatch MVP. The sample case
lives in `data/cases/arbitrage_mvp` and reads scalar configuration from YAML
plus hourly prices and durations from CSV.

## Run Tests

From the repository root:

```powershell
julia --project=. -e "import Pkg; Pkg.test()"
```

## Run The Sample Case

This command loads `data/cases/arbitrage_mvp`, solves the dispatch model with
HiGHS, and writes a run folder under `outputs/arbitrage_mvp/<run_timestamp>/`.

```powershell
julia --project=. -e "using BESSDispatch; run_output = BESSDispatch.run_case(ARGS[1]); println(run_output.output_dir)" data/cases/arbitrage_mvp
```

Each run folder contains:

- `dispatch.csv`
- `summary.json`
- `config_resolved.yaml`
- `model_metadata.json`

## Run A System Case JSON

Iteration 2 adds a parallel hybrid system-dispatch API for a versioned
`system_case.json` containing graph nodes, edges, common time series, solver
settings, and asset constraints. The sample hybrid case lives at
`data/cases/hybrid_system/system_case.json` and includes one bus, one solar
renewable, one BESS, one grid connection with import/export limits, and one
local load.

Use the Julia API when embedding the optimizer in another Julia caller:

```powershell
julia --project=. -e "using BESSDispatch; system_case = BESSDispatch.load_system_case(ARGS[1]); data = BESSDispatch.normalize_system_case(system_case); result = BESSDispatch.solve_system_dispatch(data); println(result.termination_status)" data/cases/hybrid_system/system_case.json
```

Use `BESSDispatch.run_system_case` to solve and persist machine-readable
outputs:

```powershell
julia --project=. -e "using BESSDispatch; run_output = BESSDispatch.run_system_case(ARGS[1]; output_root = ARGS[2]); println(run_output.output_dir)" data/cases/hybrid_system/system_case.json outputs
```

The process-friendly CLI for a future Python worker is:

```powershell
julia --project=. scripts/run_system_case.jl data/cases/hybrid_system/system_case.json --output-root outputs
```

On success the CLI prints compact JSON to stdout with `case_name`,
`run_timestamp`, `output_dir`, `summary_path`, and `termination_status`. On
validation or solve failure it exits nonzero and writes error JSON to stderr, so
stdout remains parseable by the caller.

Each system run folder contains:

- `dispatch.csv`: one row per period with system totals including
  `grid_import_mw`, `grid_export_mw`, `renewable_curtailed_mw`,
  `load_demand_mw`, battery totals, market value, and period profit.
- `asset_dispatch.csv`: long asset-level rows keyed by `asset_id`, with the
  same grid, renewable, load, and battery dispatch fields for dynamic UI tables.
- `summary.json`: compact run status, objective value, source identifiers, and
  model version.
- `system_case_resolved.json`: normalized copy of the accepted input contract.
- `model_metadata.json`: model name, schema version, bus ID, period count,
  asset IDs, active constraint flags, and unit conventions.

## Generate The Plotly Report

Pass a completed run output folder to the report script:

```powershell
python python/plot_results.py outputs/arbitrage_mvp/<run_timestamp>
```

The script writes:

```text
outputs/arbitrage_mvp/<run_timestamp>/plots/dispatch_report.html
```

The report includes price and dispatch, stored energy, period profit, and
degradation cost traces.
