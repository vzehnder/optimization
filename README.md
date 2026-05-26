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
